"""Deterministic training and evaluation utilities for CVB behavior models."""
from __future__ import annotations
import argparse, csv, json, math, os, random, tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader
from .dataset import CvbClipDataset
from .model import save_behavior_checkpoint

@dataclass(frozen=True)
class TrainingConfig:
    epochs:int=30; batch_size:int=4; accumulation_steps:int=4; lr:float=3e-4
    weight_decay:float=1e-4; patience:int=6; workers:int=2; seed:int=20260814
    amp:bool=True; freeze_backbone_epochs:int=2
    def __post_init__(self):
        for n in ('epochs','batch_size','accumulation_steps','patience'):
            if type(getattr(self,n)) is not int or getattr(self,n)<=0: raise ValueError(f'{n} must be positive')
        if type(self.workers) is not int or self.workers<0: raise ValueError('workers must be nonnegative')
        if type(self.seed) is not int or self.seed<0: raise ValueError('seed must be nonnegative')
        if not math.isfinite(self.lr) or self.lr<=0 or not math.isfinite(self.weight_decay) or self.weight_decay<0: raise ValueError('invalid optimizer settings')
        if self.freeze_backbone_epochs<0 or self.freeze_backbone_epochs>self.epochs: raise ValueError('invalid freeze_backbone_epochs')

def seed_everything(seed):
    if type(seed) is not int or seed<0: raise ValueError('seed must be nonnegative')
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    if torch.cuda.is_available(): torch.cuda.manual_seed_all(seed)

def _worker_seed(worker_id):
    s=torch.initial_seed()%2**32; random.seed(s); np.random.seed(s)

def make_class_weights(counts):
    if len(counts)!=12: raise ValueError('exactly 12 class counts required')
    x=torch.as_tensor(list(counts),dtype=torch.float32)
    if not torch.isfinite(x).all() or (x<=0).any(): raise ValueError('class counts must be finite and positive')
    w=x.reciprocal(); return w/w.mean()

def compute_metrics(y_true,y_pred,class_count=12):
    a,b=list(y_true),list(y_pred)
    if not a or len(a)!=len(b) or type(class_count) is not int or class_count<=0: raise ValueError('invalid labels')
    if any(type(x) is not int or x<0 or x>=class_count for x in a+b): raise ValueError('labels out of range')
    cm=[[0]*class_count for _ in range(class_count)]
    for x,y in zip(a,b): cm[x][y]+=1
    per=[]
    for i in range(class_count):
        tp=cm[i][i]; fp=sum(r[i] for r in cm)-tp; fn=sum(cm[i])-tp
        p=tp/(tp+fp) if tp+fp else 0.; r=tp/(tp+fn) if tp+fn else 0.; f=2*p*r/(p+r) if p+r else 0.
        per.append({'class_id':i,'precision':p,'recall':r,'f1':f,'support':sum(cm[i])})
    return {'accuracy':sum(cm[i][i] for i in range(class_count))/len(a),'macro_f1':sum(x['f1'] for x in per)/class_count,'per_class':per,'confusion_matrix':cm}

def make_loaders(index_root,source_data_root,config,mode='train'):
    root=Path(index_root); g=torch.Generator().manual_seed(config.seed); out={}
    splits=('train','val','test') if mode=='train' else ('val','test')
    for split in splits:
        ds=CvbClipDataset(root/f'{split}.csv',source_data_root,training=split=='train',seed=config.seed)
        out[split]=DataLoader(ds,batch_size=config.batch_size,shuffle=split=='train',num_workers=config.workers,worker_init_fn=_worker_seed,generator=g)
    return out

def train_epoch(model,loader,optimizer,device,config,class_weights=None,scheduler=None,scaler=None,max_steps=None):
    model.train(); device=torch.device(device); amp=config.amp and device.type=='cuda'; scaler=scaler or torch.amp.GradScaler('cuda',enabled=amp)
    lossfn=nn.CrossEntropyLoss(weight=None if class_weights is None else class_weights.to(device)); optimizer.zero_grad(set_to_none=True)
    total=0.; n=0; yt=[]; yp=[]; steps=0
    for i,(x,y) in enumerate(loader):
        x,y=x.to(device),y.to(device)
        with torch.amp.autocast(device_type=device.type,enabled=amp): loss=lossfn(model(x),y)
        if not torch.isfinite(loss): raise FloatingPointError('non-finite loss')
        scaler.scale(loss/config.accumulation_steps).backward(); total+=loss.item()*len(y); n+=len(y)
        with torch.no_grad(): pred=model(x).argmax(1) if False else None
        boundary=(i+1)%config.accumulation_steps==0 or i+1==len(loader)
        if boundary:
            scaler.unscale_(optimizer); torch.nn.utils.clip_grad_norm_(model.parameters(),5); scaler.step(optimizer); scaler.update(); optimizer.zero_grad(set_to_none=True); steps+=1
            if scheduler: scheduler.step()
            if max_steps and steps>=max_steps: break
        yt.extend(y.cpu().tolist()); yp.extend([] if pred is None else pred.cpu().tolist())
    return {'loss':total/n,'optimizer_steps':steps,'y_true':yt,'y_pred':yp}

@torch.inference_mode()
def evaluate(model,loader,device,class_weights=None):
    model.eval(); fn=nn.CrossEntropyLoss(weight=None if class_weights is None else class_weights.to(device)); total=n=0; a=[]; b=[]
    for x,y in loader:
        x,y=x.to(device),y.to(device); z=model(x); loss=fn(z,y)
        if not torch.isfinite(loss): raise FloatingPointError('non-finite loss')
        total+=loss.item()*len(y); n+=len(y); a+=y.cpu().tolist(); b+=z.argmax(1).cpu().tolist()
    m=compute_metrics(a,b,z.shape[1]); m['loss']=total/n; return m

def set_backbone_frozen(model,frozen=True):
    classifier=getattr(getattr(model,'blocks',[]) [-1],'proj',None)
    if classifier is None: classifier=getattr(model,'classifier',None)
    if classifier is None: raise ValueError('classifier not found')
    for p in model.parameters(): p.requires_grad=not frozen
    for p in classifier.parameters(): p.requires_grad=True

def _atomic_torch_save(payload,path):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True); fd,tmp=tempfile.mkstemp(dir=path.parent,suffix='.tmp'); os.close(fd)
    try: torch.save(payload,tmp); os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def save_training_state(path,epoch,model,optimizer,scheduler,scaler,best_f1,patience,history,config):
    _atomic_torch_save({'schema':1,'epoch':epoch,'model':model.state_dict(),'optimizer':optimizer.state_dict(),'scheduler':scheduler.state_dict(),'scaler':scaler.state_dict(),'best_f1':best_f1,'patience':patience,'history':history,'config':asdict(config),'rng':{'python':random.getstate(),'numpy':np.random.get_state(),'torch':torch.get_rng_state()}},path)

def load_training_state(path,model,optimizer,scheduler,scaler):
    p=torch.load(path,map_location='cpu',weights_only=False)
    required={'schema','epoch','model','optimizer','scheduler','scaler','best_f1','patience','history','config','rng'}
    if not isinstance(p,dict) or set(p)!=required or p['schema']!=1: raise ValueError('invalid training checkpoint schema')
    model.load_state_dict(p['model']); optimizer.load_state_dict(p['optimizer']); scheduler.load_state_dict(p['scheduler']); scaler.load_state_dict(p['scaler']); random.setstate(p['rng']['python']); np.random.set_state(p['rng']['numpy']); torch.set_rng_state(p['rng']['torch']); return p

def build_parser():
    p=argparse.ArgumentParser(); p.add_argument('--mode',choices=['smoke','train','evaluate'],required=True)
    for x in ('index-root','source-data-root','output-root','model-root'): p.add_argument('--'+x,required=True)
    p.add_argument('--checkpoint'); p.add_argument('--split',choices=['val','test'],default='test'); p.add_argument('--resume'); p.add_argument('--device',default='cuda' if torch.cuda.is_available() else 'cpu'); p.add_argument('--seed',type=int,default=20260814); return p

def main(argv=None):
    args=build_parser().parse_args(argv)
    if args.mode=='evaluate' and not args.checkpoint: raise SystemExit('--checkpoint is required for evaluate')

if __name__=='__main__': main()

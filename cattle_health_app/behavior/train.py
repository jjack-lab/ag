"""Reproducible core training primitives for CVB behavior classification."""
from __future__ import annotations
import inspect, math, os, random, tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader
from .dataset import CvbClipDataset

@dataclass(frozen=True)
class TrainingConfig:
    epochs:int=30; batch_size:int=4; accumulation_steps:int=4; lr:float=3e-4
    weight_decay:float=1e-4; patience:int=6; workers:int=2; seed:int=20260814
    amp:bool=True; freeze_backbone_epochs:int=2
    def __post_init__(self):
        for name in ('epochs','batch_size','accumulation_steps','patience'):
            if type(getattr(self,name)) is not int or getattr(self,name)<=0: raise ValueError(f'{name} must be a positive integer')
        if type(self.workers) is not int or self.workers<0: raise ValueError('workers must be a nonnegative integer')
        if type(self.seed) is not int or self.seed<0: raise ValueError('seed must be a nonnegative integer')
        if type(self.amp) is not bool: raise ValueError('amp must be boolean')
        if type(self.freeze_backbone_epochs) is not int or not 0<=self.freeze_backbone_epochs<=self.epochs: raise ValueError('freeze_backbone_epochs must be in [0, epochs]')
        if isinstance(self.lr,bool) or not math.isfinite(self.lr) or self.lr<=0: raise ValueError('lr must be finite and positive')
        if isinstance(self.weight_decay,bool) or not math.isfinite(self.weight_decay) or self.weight_decay<0: raise ValueError('weight_decay must be finite and nonnegative')

@dataclass(frozen=True)
class EpochResult:
    loss:float; y_true:list[int]; y_pred:list[int]; metrics:dict; optimizer_steps:int=0

def seed_everything(seed):
    if type(seed) is not int or seed<0: raise ValueError('seed must be a nonnegative integer')
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    if torch.cuda.is_available(): torch.cuda.manual_seed_all(seed)

def _seed_worker(_worker_id):
    seed=torch.initial_seed()%2**32; random.seed(seed); np.random.seed(seed)

def make_class_weights(counts):
    try: values=list(counts)
    except TypeError as exc: raise ValueError('counts must be iterable') from exc
    if len(values)!=12: raise ValueError('exactly 12 class counts required')
    weights=torch.as_tensor(values,dtype=torch.float32)
    if weights.ndim!=1 or not torch.isfinite(weights).all() or (weights<=0).any(): raise ValueError('class counts must be finite and positive')
    weights=weights.reciprocal(); return weights/weights.mean()

def compute_metrics(y_true,y_pred,class_count=12):
    true,pred=list(y_true),list(y_pred)
    if type(class_count) is not int or class_count<=0: raise ValueError('class_count must be positive')
    if not true or len(true)!=len(pred): raise ValueError('labels must be nonempty and equal length')
    if any(type(v) is not int or not 0<=v<class_count for v in true+pred): raise ValueError('labels must be integers in range')
    cm=[[0 for _ in range(class_count)] for _ in range(class_count)]
    for actual,guess in zip(true,pred): cm[actual][guess]+=1
    per=[]
    for i in range(class_count):
        tp=cm[i][i]; support=sum(cm[i]); fp=sum(row[i] for row in cm)-tp
        precision=tp/(tp+fp) if tp+fp else 0.; recall=tp/support if support else 0.
        f1=2*precision*recall/(precision+recall) if precision+recall else 0.
        per.append({'class_id':i,'precision':precision,'recall':recall,'f1':f1,'support':support})
    return {'accuracy':sum(cm[i][i] for i in range(class_count))/len(true),'macro_f1':sum(v['f1'] for v in per)/class_count,'per_class':per,'confusion_matrix':cm}

def make_loaders(index_root,source_data_root,config,mode='train'):
    if mode not in ('train','evaluate'): raise ValueError("mode must be 'train' or 'evaluate'")
    generator=torch.Generator().manual_seed(config.seed); result={}
    for split in (('train','val','test') if mode=='train' else ('val','test')):
        dataset=CvbClipDataset(Path(index_root)/f'{split}.csv',source_data_root,training=split=='train',seed=config.seed)
        result[split]=DataLoader(dataset,batch_size=config.batch_size,shuffle=split=='train',num_workers=config.workers,worker_init_fn=_seed_worker,generator=generator)
    return result

def _scaler(enabled):
    try: return torch.amp.GradScaler('cuda',enabled=enabled)
    except (AttributeError,TypeError): return torch.cuda.amp.GradScaler(enabled=enabled)

def train_epoch(model,loader,optimizer,device,config,class_weights=None,scheduler=None,scaler=None,max_steps=None):
    device=torch.device(device); amp=bool(config.amp and device.type=='cuda'); scaler=scaler or _scaler(amp)
    model.train(); criterion=nn.CrossEntropyLoss(weight=None if class_weights is None else class_weights.to(device)); optimizer.zero_grad(set_to_none=True)
    total=0.; count=0; true=[]; pred=[]; steps=0
    for index,(inputs,targets) in enumerate(loader):
        inputs,targets=inputs.to(device),targets.to(device)
        with torch.amp.autocast(device_type=device.type,enabled=amp):
            logits=model(inputs); loss=criterion(logits,targets)
        if not torch.isfinite(loss): raise FloatingPointError('non-finite training loss')
        scaler.scale(loss/config.accumulation_steps).backward()
        total+=float(loss.detach())*targets.numel(); count+=targets.numel(); true.extend(targets.cpu().tolist()); pred.extend(logits.detach().argmax(1).cpu().tolist())
        boundary=(index+1)%config.accumulation_steps==0 or index+1==len(loader)
        if boundary:
            scaler.unscale_(optimizer); nn.utils.clip_grad_norm_(model.parameters(),5.0); scaler.step(optimizer); scaler.update(); optimizer.zero_grad(set_to_none=True); steps+=1
            if scheduler is not None: scheduler.step()
            if max_steps is not None and steps>=max_steps: break
    if not count: raise ValueError('loader must not be empty')
    metrics=compute_metrics(true,pred,logits.shape[1])
    return EpochResult(total/count,true,pred,metrics,steps)

@torch.inference_mode()
def evaluate(model,loader,device,class_weights=None):
    device=torch.device(device); model.eval(); criterion=nn.CrossEntropyLoss(weight=None if class_weights is None else class_weights.to(device)); total=0.; count=0; true=[]; pred=[]; classes=None
    for inputs,targets in loader:
        logits=model(inputs.to(device)); targets=targets.to(device); loss=criterion(logits,targets)
        if not torch.isfinite(loss): raise FloatingPointError('non-finite evaluation loss')
        total+=float(loss)*targets.numel(); count+=targets.numel(); classes=logits.shape[1]; true.extend(targets.cpu().tolist()); pred.extend(logits.argmax(1).cpu().tolist())
    if not count: raise ValueError('loader must not be empty')
    return EpochResult(total/count,true,pred,compute_metrics(true,pred,classes),0)

def find_classifier(model):
    blocks=getattr(model,'blocks',None)
    classifier=getattr(blocks[-1],'proj',None) if blocks is not None and len(blocks) else getattr(model,'classifier',None)
    if not isinstance(classifier,nn.Module): raise ValueError('supported classifier head not found')
    return classifier

def set_backbone_frozen(model,frozen=True):
    if type(frozen) is not bool: raise ValueError('frozen must be boolean')
    classifier=find_classifier(model)
    for parameter in model.parameters(): parameter.requires_grad=not frozen
    for parameter in classifier.parameters(): parameter.requires_grad=True
    return classifier

def _atomic_save(payload,path):
    destination=Path(path); destination.parent.mkdir(parents=True,exist_ok=True); handle=tempfile.NamedTemporaryFile(dir=destination.parent,prefix='.'+destination.name,suffix='.tmp',delete=False); temporary=Path(handle.name)
    try:
        with handle: torch.save(payload,handle); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary,destination)
    finally:
        if temporary.exists(): temporary.unlink()

def save_training_state(path,epoch,model,optimizer,scheduler,scaler,best_f1,patience,history,config):
    if type(epoch) is not int or epoch<0 or type(patience) is not int or patience<0: raise ValueError('invalid training state counters')
    payload={'schema':1,'epoch':epoch,'model':{k:v.detach().cpu() for k,v in model.state_dict().items()},'optimizer':optimizer.state_dict(),'scheduler':scheduler.state_dict(),'scaler':scaler.state_dict(),'best_f1':float(best_f1),'patience':patience,'history':history,'config':asdict(config),'rng':{'python':random.getstate(),'numpy_state':np.random.get_state()[1].tolist(),'numpy_pos':np.random.get_state()[2],'numpy_has_gauss':np.random.get_state()[3],'numpy_cached_gaussian':np.random.get_state()[4],'torch':torch.get_rng_state(),'cuda':[x.cpu() for x in torch.cuda.get_rng_state_all()] if torch.cuda.is_available() else []}}
    _atomic_save(payload,path)

def _safe_load(path):
    if 'weights_only' not in inspect.signature(torch.load).parameters: raise RuntimeError('safe checkpoint loading requires weights_only support')
    return torch.load(Path(path),map_location='cpu',weights_only=True)

def load_training_state(path,model,optimizer,scheduler,scaler):
    payload=_safe_load(path); required={'schema','epoch','model','optimizer','scheduler','scaler','best_f1','patience','history','config','rng'}
    if not isinstance(payload,dict) or set(payload)!=required or payload['schema']!=1: raise ValueError('invalid training checkpoint schema')
    if type(payload['epoch']) is not int or payload['epoch']<0 or type(payload['patience']) is not int or payload['patience']<0 or not isinstance(payload['history'],list) or not isinstance(payload['config'],dict): raise ValueError('invalid training checkpoint field types')
    model.load_state_dict(payload['model']); optimizer.load_state_dict(payload['optimizer']); scheduler.load_state_dict(payload['scheduler']); scaler.load_state_dict(payload['scaler'])
    rng=payload['rng']; random.setstate(tuple(rng['python'])); np.random.set_state(('MT19937',np.asarray(rng['numpy_state'],dtype=np.uint32),rng['numpy_pos'],rng['numpy_has_gauss'],rng['numpy_cached_gaussian'])); torch.set_rng_state(rng['torch'])
    if torch.cuda.is_available() and rng['cuda']: torch.cuda.set_rng_state_all(rng['cuda'])
    return payload

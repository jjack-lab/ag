"""Reproducible core training primitives for CVB behavior classification."""
from __future__ import annotations
import argparse, csv, inspect, json, math, os, platform, random, tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset, Subset
from .dataset import CvbClipDataset
from .model import build_x3d, load_behavior_checkpoint, save_behavior_checkpoint

@dataclass(frozen=True)
class TrainingConfig:
    epochs:int=30; batch_size:int=4; accumulation_steps:int=4; learning_rate:float=3e-4
    weight_decay:float=1e-4; patience:int=6; workers:int=2; seed:int=20260814
    amp:bool=True; freeze_backbone_epochs:int=2
    def __post_init__(self):
        for name in ('epochs','batch_size','accumulation_steps','patience'):
            if type(getattr(self,name)) is not int or getattr(self,name)<=0: raise ValueError(f'{name} must be a positive integer')
        if type(self.workers) is not int or self.workers<0: raise ValueError('workers must be a nonnegative integer')
        if type(self.seed) is not int or self.seed<0: raise ValueError('seed must be a nonnegative integer')
        if type(self.amp) is not bool: raise ValueError('amp must be boolean')
        if type(self.freeze_backbone_epochs) is not int or not 0<=self.freeze_backbone_epochs<=self.epochs: raise ValueError('freeze_backbone_epochs must be in [0, epochs]')
        if isinstance(self.learning_rate,bool) or not math.isfinite(self.learning_rate) or self.learning_rate<=0: raise ValueError('learning_rate must be finite and positive')
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

class EpochSeededDataset(Dataset):
    """Derive augmentation RNG from seed, epoch and sample index across worker counts."""
    def __init__(self,dataset,seed): self.dataset=dataset; self.seed=seed; self.epoch=0
    @property
    def samples(self): return self.dataset.samples
    def __len__(self): return len(self.dataset)
    def set_epoch(self,epoch): self.epoch=int(epoch)
    def __getitem__(self,index):
        augmentation=getattr(self.dataset,'_augmentation_rng',None)
        if augmentation is None: return self.dataset[index]
        derived=(self.seed*1000003+self.epoch*9176+int(index))%(2**63-1)
        self.dataset._augmentation_rng=lambda: random.Random(derived)
        try: return self.dataset[index]
        finally: self.dataset._augmentation_rng=augmentation


def _set_loader_epoch(loader,epoch,seed):
    generator=getattr(loader,'generator',None)
    if generator is not None: generator.manual_seed(seed+epoch)
    dataset=getattr(loader,'dataset',None)
    while isinstance(dataset,Subset): dataset=dataset.dataset
    setter=getattr(dataset,'set_epoch',None)
    if setter is not None: setter(epoch)
def make_loaders(index_root,source_data_root,config,mode='train'):
    if mode not in ('train','evaluate'): raise ValueError("mode must be 'train' or 'evaluate'")
    generator=torch.Generator().manual_seed(config.seed); result={}
    for split in (('train','val','test') if mode=='train' else ('val','test')):
        dataset=EpochSeededDataset(CvbClipDataset(Path(index_root)/f'{split}.csv',source_data_root,training=split=='train',seed=config.seed),config.seed)
        result[split]=DataLoader(dataset,batch_size=config.batch_size,shuffle=split=='train',num_workers=config.workers,worker_init_fn=_seed_worker,generator=generator)
    return result

def _scaler(enabled):
    try: return torch.amp.GradScaler('cuda',enabled=enabled)
    except (AttributeError,TypeError): return torch.cuda.amp.GradScaler(enabled=enabled)

def train_epoch(model,loader,optimizer,device,config,class_weights=None,scheduler=None,scaler=None,max_steps=None):
    device=torch.device(device); amp=bool(config.amp and device.type=='cuda'); scaler=scaler or _scaler(amp)
    model.train(); criterion=nn.CrossEntropyLoss(weight=None if class_weights is None else class_weights.to(device)); optimizer.zero_grad(set_to_none=True)
    total=0.; count=0; true=[]; pred=[]; steps=0; group_samples=0
    for index,(inputs,targets) in enumerate(loader):
        inputs,targets=inputs.to(device),targets.to(device)
        with torch.amp.autocast(device_type=device.type,enabled=amp): logits=model(inputs); loss=criterion(logits,targets)
        if not torch.isfinite(loss): raise FloatingPointError('non-finite training loss')
        size=targets.numel(); scaler.scale(loss*size).backward(); group_samples+=size; total+=float(loss.detach())*size; count+=size; true.extend(targets.cpu().tolist()); pred.extend(logits.detach().argmax(1).cpu().tolist())
        boundary=(index+1)%config.accumulation_steps==0 or index+1==len(loader)
        if boundary:
            scaler.unscale_(optimizer)
            for parameter in model.parameters():
                if parameter.grad is not None: parameter.grad.div_(group_samples)
            group_samples=0
            nn.utils.clip_grad_norm_(model.parameters(),5.0); scaler.step(optimizer); scaler.update(); optimizer.zero_grad(set_to_none=True); steps+=1
            if scheduler is not None: scheduler.step()
            if max_steps is not None and steps>=max_steps: break
    if not count: raise ValueError('loader must not be empty')
    metrics=compute_metrics(true,pred,logits.shape[1]); return EpochResult(total/count,true,pred,metrics,steps)

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

def _valid_state_tree(value):
    if value is None or isinstance(value,(bool,str,int)): return True
    if isinstance(value,float): return math.isfinite(value)
    if isinstance(value,torch.Tensor): return bool(torch.isfinite(value).all())
    if isinstance(value,dict): return all(isinstance(k,(str,int)) and _valid_state_tree(v) for k,v in value.items())
    if isinstance(value,(list,tuple)): return all(_valid_state_tree(v) for v in value)
    return False
def load_training_state(path,model,optimizer,scheduler,scaler,expected_config=None):
    payload=_safe_load(path); required={'schema','epoch','model','optimizer','scheduler','scaler','best_f1','patience','history','config','rng'}
    if not isinstance(payload,dict) or set(payload)!=required or payload['schema']!=1: raise ValueError('invalid training checkpoint schema')
    saved_config=payload.get('config')
    if isinstance(saved_config,dict) and 'lr' in saved_config and 'learning_rate' not in saved_config: saved_config=dict(saved_config); saved_config['learning_rate']=saved_config.pop('lr'); payload['config']=saved_config
    if expected_config is not None:
        current=asdict(expected_config); incompatible=[key for key in current if key!='epochs' and saved_config.get(key)!=current[key]]
        if saved_config.get('epochs')!=current['epochs'] or incompatible or current['epochs']<=payload['epoch']: raise ValueError('incompatible resume configuration: '+str((['epochs'] if saved_config.get('epochs')!=current['epochs'] else [])+incompatible))
    if type(payload['epoch']) is not int or payload['epoch']<0 or type(payload['patience']) is not int or payload['patience']<0 or not isinstance(payload['history'],list) or not isinstance(payload['config'],dict) or not isinstance(payload['best_f1'],(int,float)) or not math.isfinite(payload['best_f1']) or not -1<=payload['best_f1']<=1: raise ValueError('invalid training checkpoint field types')
    rng=payload['rng']
    if not isinstance(payload['model'],dict) or not all(isinstance(k,str) and isinstance(v,torch.Tensor) and torch.isfinite(v).all() for k,v in payload['model'].items()): raise ValueError('invalid model state')
    if not all(isinstance(payload[k],dict) and _valid_state_tree(payload[k]) for k in ('optimizer','scheduler','scaler')) or not _valid_state_tree(payload['history']) or not _valid_state_tree(payload['config']): raise ValueError('invalid component state')
    if not isinstance(rng,dict) or not isinstance(rng.get('python'),tuple) or len(rng['python'])!=3 or type(rng['python'][0]) is not int or not isinstance(rng['python'][1],tuple) or len(rng['python'][1])!=625 or not (rng['python'][2] is None or isinstance(rng['python'][2],float) and math.isfinite(rng['python'][2])) or not math.isfinite(rng.get('numpy_cached_gaussian',float('nan'))) or not isinstance(rng.get('torch'),torch.Tensor) or rng['torch'].dtype!=torch.uint8 or not isinstance(rng.get('numpy_state'),list) or len(rng['numpy_state'])!=624 or not 0<=rng.get('numpy_pos',-1)<=624 or rng.get('numpy_has_gauss') not in (0,1) or rng['torch'].shape!=torch.get_rng_state().shape or not isinstance(rng.get('cuda'),list) or len(rng['cuda'])!=(torch.cuda.device_count() if torch.cuda.is_available() else 0) or any(v.dtype!=torch.uint8 or v.ndim!=1 for v in rng['cuda']) or (torch.cuda.is_available() and any(v.shape!=current.shape for v,current in zip(rng['cuda'],torch.cuda.get_rng_state_all()))): raise ValueError('invalid RNG state')
    import copy
    snapshots=copy.deepcopy((model.state_dict(),optimizer.state_dict(),scheduler.state_dict(),scaler.state_dict(),random.getstate(),np.random.get_state(),torch.get_rng_state(),torch.cuda.get_rng_state_all() if torch.cuda.is_available() else []))
    try:
        model.load_state_dict(payload['model']); optimizer.load_state_dict(payload['optimizer']); scheduler.load_state_dict(payload['scheduler']); scaler.load_state_dict(payload['scaler'])
        random.setstate(tuple(rng['python'])); np.random.set_state(('MT19937',np.asarray(rng['numpy_state'],dtype=np.uint32),rng['numpy_pos'],rng['numpy_has_gauss'],rng['numpy_cached_gaussian'])); torch.set_rng_state(rng['torch'])
        if torch.cuda.is_available() and rng['cuda']: torch.cuda.set_rng_state_all(rng['cuda'])
    except Exception as exc:
        model.load_state_dict(snapshots[0]); optimizer.load_state_dict(snapshots[1]); scheduler.load_state_dict(snapshots[2]); scaler.load_state_dict(snapshots[3]); random.setstate(snapshots[4]); np.random.set_state(snapshots[5]); torch.set_rng_state(snapshots[6]);
        if torch.cuda.is_available(): torch.cuda.set_rng_state_all(snapshots[7])
        raise ValueError(f'invalid training checkpoint state: {exc}') from exc
    return payload


def _atomic_text(path, text):
    destination=Path(path); destination.parent.mkdir(parents=True,exist_ok=True)
    handle=tempfile.NamedTemporaryFile('w',encoding='utf-8',newline='',dir=destination.parent,prefix='.'+destination.name,suffix='.tmp',delete=False); temporary=Path(handle.name)
    try:
        with handle: handle.write(text); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary,destination)
    finally:
        if temporary.exists(): temporary.unlink()

def _write_json(path,value): _atomic_text(path,json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False))

def _write_csv(path,rows,fieldnames):
    destination=Path(path); destination.parent.mkdir(parents=True,exist_ok=True)
    handle=tempfile.NamedTemporaryFile('w',encoding='utf-8-sig',newline='',dir=destination.parent,prefix='.'+destination.name,suffix='.tmp',delete=False); temporary=Path(handle.name)
    try:
        with handle:
            writer=csv.DictWriter(handle,fieldnames=fieldnames); writer.writeheader(); writer.writerows(rows); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary,destination)
    finally:
        if temporary.exists(): temporary.unlink()

def _atomic_figure(figure,path):
    destination=Path(path); handle=tempfile.NamedTemporaryFile(dir=destination.parent,prefix='.'+destination.name,suffix='.png',delete=False); temporary=Path(handle.name); handle.close()
    try:
        figure.savefig(temporary,format='png')
        with temporary.open('r+b') as stream: os.fsync(stream.fileno())
        os.replace(temporary,destination)
    finally:
        if temporary.exists(): temporary.unlink()
def _plot_artifacts(output,history,metrics):
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    output=Path(output); epochs=[r['epoch'] for r in history]
    figure,axes=plt.subplots(1,2,figsize=(10,4)); axes[0].plot(epochs,[r['train_loss'] for r in history],label='train'); axes[0].plot(epochs,[r['val_loss'] for r in history],label='val'); axes[0].legend(); axes[0].set_title('Loss'); axes[1].plot(epochs,[r['val_macro_f1'] for r in history],label='Macro-F1'); axes[1].plot(epochs,[r.get('learning_rate',0.0) for r in history],label='Learning rate'); axes[1].legend(); axes[1].set_title('Validation Macro-F1 / LR'); figure.tight_layout(); _atomic_figure(figure,output/'training_curves.png'); plt.close(figure)
    figure,axis=plt.subplots(figsize=(8,7)); axis.imshow(metrics['confusion_matrix'],cmap='Blues'); axis.set_xlabel('Predicted'); axis.set_ylabel('True'); figure.tight_layout(); _atomic_figure(figure,output/'confusion_matrix.png'); plt.close(figure)

def write_artifacts(output_root,history,metrics):
    output=Path(output_root); output.mkdir(parents=True,exist_ok=True)
    fields=['epoch','train_loss','val_loss','val_accuracy','val_macro_f1','learning_rate']
    _write_csv(output/'history.csv',history,fields); _write_json(output/'metrics.json',metrics)
    report=[{'class_id':r['class_id'],'precision':r['precision'],'recall':r['recall'],'f1':r['f1'],'support':r['support']} for r in metrics['per_class']]
    _write_csv(output/'classification_report.csv',report,['class_id','precision','recall','f1','support'])
    matrix=[{'class_id':i,**{f'pred_{j}':v for j,v in enumerate(row)}} for i,row in enumerate(metrics['confusion_matrix'])]
    _write_csv(output/'confusion_matrix.csv',matrix,['class_id']+[f'pred_{i}' for i in range(len(matrix))]); _plot_artifacts(output,history,metrics)

def _class_counts(loader):
    samples=getattr(getattr(loader,'dataset',None),'samples',None)
    if samples is None: return None
    counts=[0]*12
    for sample in samples: counts[sample.label_id-1]+=1
    return counts

def run_training(model,loaders,output_root,config,device='cpu',resume=None,evaluate_fn=evaluate,train_fn=train_epoch):
    if not {'train','val'}<=set(loaders): raise ValueError('training requires train and val loaders')
    output=Path(output_root); output.mkdir(parents=True,exist_ok=True); device=torch.device(device); model.to(device)
    optimizer=torch.optim.AdamW(model.parameters(),lr=config.learning_rate,weight_decay=config.weight_decay)
    scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,T_max=max(1,config.epochs)); scaler=_scaler(config.amp and device.type=='cuda')
    counts=_class_counts(loaders['train']); weights=make_class_weights(counts) if counts is not None else None
    start=0; best=-1.; best_metrics=None; stale=0; history=[]; frozen=config.freeze_backbone_epochs>0
    if frozen: set_backbone_frozen(model,True)
    if resume:
        state=load_training_state(resume,model,optimizer,scheduler,scaler,config)
        start=state['epoch']+1; best=state['best_f1']; stale=state['patience']; history=list(state['history'])
        frozen=start<config.freeze_backbone_epochs
        if config.freeze_backbone_epochs>0: set_backbone_frozen(model,frozen)
    last_metrics=None
    for epoch in range(start,config.epochs):
        if frozen and epoch>=config.freeze_backbone_epochs: set_backbone_frozen(model,False); frozen=False
        _set_loader_epoch(loaders['train'],epoch,config.seed)
        trained=train_fn(model,loaders['train'],optimizer,device,config,weights,scaler=scaler)
        validation=evaluate_fn(model,loaders['val'],device,weights); last_metrics=validation.metrics
        row={'epoch':epoch,'train_loss':trained.loss,'val_loss':validation.loss,'val_accuracy':validation.metrics['accuracy'],'val_macro_f1':validation.metrics['macro_f1'],'learning_rate':optimizer.param_groups[0]['lr']}; history.append(row)
        improved=validation.metrics['macro_f1']>best
        if improved:
            best=validation.metrics['macro_f1']; best_metrics=validation.metrics; stale=0
            save_behavior_checkpoint(output/'best.pt',model,validation.metrics,asdict(config))
        else: stale+=1
        scheduler.step(); save_training_state(output/'last.pt',epoch,model,optimizer,scheduler,scaler,best,stale,history,config)
        _write_csv(output/'history.csv',history,['epoch','train_loss','val_loss','val_accuracy','val_macro_f1','learning_rate'])
        if stale>=config.patience: break
    if last_metrics is None: raise ValueError('resume checkpoint is already beyond configured epochs')
    if best_metrics is None and (output/'best.pt').is_file():
        best_model=load_behavior_checkpoint(output/'best.pt',device).model; best_metrics=evaluate_fn(best_model,loaders['val'],device,weights).metrics
    write_artifacts(output,history,best_metrics or last_metrics); return {'history':history,'metrics':last_metrics,'best_f1':best,'epochs_completed':len(history)}

def run_evaluation(checkpoint,loader,output_root,device='cpu'):
    loaded=load_behavior_checkpoint(checkpoint,device); result=evaluate(loaded.model,loader,device); write_artifacts(output_root,[],result.metrics); return result

def make_smoke_loaders(loaders,config):
    if set(loaders) != {'train','val','test'}: raise ValueError('smoke requires train, val, and test loaders')
    result={}
    for offset,split in enumerate(('train','val','test')):
        source=loaders[split]; samples=getattr(source.dataset,'samples',None)
        if samples is None: raise ValueError('smoke datasets must expose indexed samples')
        by_class={i:[] for i in range(12)}
        for index,sample in enumerate(samples): by_class[sample.label_id-1].append(index)
        if any(not values for values in by_class.values()): raise ValueError(f'{split} smoke split must cover all 12 classes')
        rng=random.Random(config.seed+offset); indices=[]
        needed=max(12,config.batch_size*config.accumulation_steps*2)
        for position in range(needed):
            label=position%12; indices.append(by_class[label][rng.randrange(len(by_class[label]))])
        generator=torch.Generator().manual_seed(config.seed+offset)
        result[split]=DataLoader(Subset(source.dataset,indices),batch_size=config.batch_size,shuffle=False,num_workers=config.workers,worker_init_fn=_seed_worker,generator=generator)
    return result
def run_smoke(model,loader,output_root,config,device='cpu'):
    output=Path(output_root); output.mkdir(parents=True,exist_ok=True); model.to(device); optimizer=torch.optim.AdamW(model.parameters(),lr=config.learning_rate); before=torch.cuda.max_memory_allocated(device) if torch.device(device).type=='cuda' else 0
    result=train_epoch(model,loader,optimizer,device,config,max_steps=2);
    if result.optimizer_steps != 2:
        raise ValueError('smoke data must provide exactly two optimizer steps')
    state=output/'smoke_state.pt'; scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,1); scaler=_scaler(False)
    save_training_state(state,0,model,optimizer,scheduler,scaler,-1,0,[],config)
    load_training_state(state,model,optimizer,scheduler,scaler)
    first=next(iter(loader))[0]; evidence={'device':str(device),'python':platform.python_version(),'torch':torch.__version__,'cuda':torch.version.cuda,'gpu':torch.cuda.get_device_name(device) if torch.device(device).type=='cuda' else None,'input_shape':list(first.shape),'loss':result.loss,'optimizer_steps':result.optimizer_steps,'peak_vram_mb':(torch.cuda.max_memory_allocated(device)-before)/1048576 if torch.device(device).type=='cuda' else 0.0,'reload_success':True}; _write_json(output/'smoke_metrics.json',evidence); return evidence

def build_parser():
    parser=argparse.ArgumentParser(description='CVB behavior training')
    parser.add_argument('--mode',required=True,choices=['smoke','train','evaluate']); parser.add_argument('--index-root',required=True); parser.add_argument('--source-data-root',required=True); parser.add_argument('--output-root',required=True); parser.add_argument('--checkpoint'); parser.add_argument('--split',choices=['val','test'],default='test'); parser.add_argument('--resume'); parser.add_argument('--device',default='cuda' if torch.cuda.is_available() else 'cpu')
    parser.add_argument('--learning-rate','--lr',dest='learning_rate',type=float,default=3e-4); parser.add_argument('--seed',type=int,default=20260814); parser.add_argument('--epochs',type=int,default=30); parser.add_argument('--batch-size',type=int,default=4); parser.add_argument('--accumulation-steps',type=int,default=4); parser.add_argument('--weight-decay',type=float,default=1e-4); parser.add_argument('--patience',type=int,default=6); parser.add_argument('--workers',type=int,default=2); parser.add_argument('--freeze-backbone-epochs',type=int,default=2); parser.add_argument('--no-amp',action='store_true'); return parser

def main(argv=None):
    args=build_parser().parse_args(argv); config=TrainingConfig(args.epochs,args.batch_size,args.accumulation_steps,args.learning_rate,args.weight_decay,args.patience,args.workers,args.seed,not args.no_amp,args.freeze_backbone_epochs); seed_everything(config.seed)
    if args.mode=='evaluate' and not args.checkpoint: raise SystemExit('--checkpoint is required in evaluate mode')
    if args.resume and args.mode!='train': raise SystemExit('--resume is valid only in train mode')
    loaders=make_loaders(args.index_root,args.source_data_root,config,'evaluate' if args.mode=='evaluate' else 'train')
    if args.mode=='smoke': loaders=make_smoke_loaders(loaders,config)
    if args.mode=='evaluate': return run_evaluation(args.checkpoint,loaders[args.split],args.output_root,args.device)
    model=build_x3d(pretrained=args.mode=='train')
    if args.mode=='smoke': return run_smoke(model,loaders['train'],args.output_root,config,args.device)
    return run_training(model,loaders,args.output_root,config,args.device,args.resume)

if __name__=='__main__': main()

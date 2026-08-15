import random
import numpy as np
import pytest
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset
import cattle_health_app.behavior.train as training

@pytest.mark.parametrize('kwargs',[{'epochs':0},{'batch_size':0},{'accumulation_steps':0},{'learning_rate':0},{'weight_decay':-1},{'patience':0},{'workers':-1},{'seed':-1},{'amp':1},{'freeze_backbone_epochs':31}])
def test_config_rejects_invalid_values(kwargs):
    with pytest.raises(ValueError): training.TrainingConfig(**kwargs)

def test_config_defaults():
    assert training.TrainingConfig()==training.TrainingConfig(30,4,4,3e-4,1e-4,6,2,20260814,True,2)

def test_seed_reproducible_across_libraries():
    training.seed_everything(7); first=(random.random(),np.random.rand(),torch.rand(1))
    training.seed_everything(7); second=(random.random(),np.random.rand(),torch.rand(1))
    assert first[0]==second[0] and first[1]==second[1] and torch.equal(first[2],second[2])

def test_weights_normalized_inverse_frequency():
    weights=training.make_class_weights(range(1,13)); assert weights.mean()==pytest.approx(1); assert weights[0]>weights[-1]; assert torch.isfinite(weights).all()

@pytest.mark.parametrize('counts',[[1]*11,[1]*11+[0],[1]*11+[float('nan')]])
def test_weights_reject_invalid_counts(counts):
    with pytest.raises(ValueError): training.make_class_weights(counts)

def test_metrics_exact_and_absent_class():
    result=training.compute_metrics([0,1,1],[0,0,1],3)
    assert result['accuracy']==pytest.approx(2/3); assert result['macro_f1']==pytest.approx((2/3+2/3+0)/3); assert result['per_class'][2]['support']==0; assert result['confusion_matrix']==[[1,0,0],[1,1,0],[0,0,0]]

@pytest.mark.parametrize('true,pred', [([],[]),([0],[0,1]),([-1],[0]),([0],[2]),([0.0],[0])])
def test_metrics_reject_invalid_labels(true,pred):
    with pytest.raises(ValueError): training.compute_metrics(true,pred,2)

class Counting(nn.Module):
    def __init__(self): super().__init__(); self.linear=nn.Linear(2,2); self.calls=0
    def forward(self,x): self.calls+=1; return self.linear(x)

def test_train_accumulates_final_partial_and_forwards_once():
    model=Counting(); loader=DataLoader(TensorDataset(torch.randn(5,2),torch.tensor([0,1,0,1,0])),batch_size=1)
    optimizer=torch.optim.SGD(model.parameters(),.1); result=training.train_epoch(model,loader,optimizer,'cpu',training.TrainingConfig(accumulation_steps=2,amp=True))
    assert result.optimizer_steps==3 and model.calls==5 and len(result.y_pred)==5 and np.isfinite(result.loss)

def test_evaluate_has_no_grad_and_no_optimizer_steps():
    class Check(Counting):
        def forward(self,x): assert not torch.is_grad_enabled(); return super().forward(x)
    result=training.evaluate(Check(),DataLoader(TensorDataset(torch.randn(3,2),torch.tensor([0,1,0]))),'cpu')
    assert result.optimizer_steps==0 and np.isfinite(result.loss)

def test_freeze_and_unfreeze_x3d_shape():
    class Tail(nn.Module):
        def __init__(self): super().__init__(); self.proj=nn.Linear(2,2)
    class Fake(nn.Module):
        def __init__(self): super().__init__(); self.stem=nn.Linear(2,2); self.blocks=nn.ModuleList([Tail()])
    model=Fake(); head=training.set_backbone_frozen(model,True)
    assert head is model.blocks[-1].proj and not model.stem.weight.requires_grad and head.weight.requires_grad
    training.set_backbone_frozen(model,False); assert all(p.requires_grad for p in model.parameters())

def test_state_roundtrip_and_rng(tmp_path):
    model=nn.Linear(2,2); optimizer=torch.optim.AdamW(model.parameters()); scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,3); scaler=training._scaler(False); config=training.TrainingConfig(); history=[{'epoch':1}]
    training.seed_everything(11); training.save_training_state(tmp_path/'last.pt',1,model,optimizer,scheduler,scaler,.7,2,history,config); expected=(random.random(),np.random.rand(),torch.rand(1)); training.load_training_state(tmp_path/'last.pt',model,optimizer,scheduler,scaler); actual=(random.random(),np.random.rand(),torch.rand(1))
    assert expected[0]==actual[0] and expected[1]==actual[1] and torch.equal(expected[2],actual[2])

def test_corrupt_state_rejected_without_destination_change(tmp_path):
    path=tmp_path/'bad.pt'; torch.save({'schema':1},path)
    model=nn.Linear(1,1); opt=torch.optim.AdamW(model.parameters()); sched=torch.optim.lr_scheduler.CosineAnnealingLR(opt,1)
    with pytest.raises(ValueError): training.load_training_state(path,model,opt,sched,training._scaler(False))

def test_make_loaders_split_and_shuffle(monkeypatch):
    seen=[]
    class DS(TensorDataset):
        def __init__(self,path,root,training,seed): seen.append((str(path),root,training,seed)); super().__init__(torch.randn(2,1),torch.zeros(2,dtype=torch.long))
    monkeypatch.setattr(training,'CvbClipDataset',DS); loaders=training.make_loaders('idx','data',training.TrainingConfig(workers=0),'train')
    assert set(loaders)=={'train','val','test'} and seen[0][2] is True and all(not x[2] for x in seen[1:])

def _epoch(score,loss=1.0):
    metrics={'accuracy':score,'macro_f1':score,'per_class':[{'class_id':i,'precision':0.,'recall':0.,'f1':0.,'support':0} for i in range(2)],'confusion_matrix':[[0,0],[0,0]]}
    return training.EpochResult(loss,[0],[0],metrics,1)

def test_run_training_strict_best_last_and_early_stop(tmp_path,monkeypatch):
    scores=iter([.8,.7,.6]); saved=[]
    monkeypatch.setattr(training,'save_behavior_checkpoint',lambda path,*args,**kwargs:saved.append(path.name))
    monkeypatch.setattr(training,'write_artifacts',lambda *args:None)
    monkeypatch.setattr(training,'save_training_state',lambda path,epoch,*args:saved.append((path.name,epoch)))
    model=nn.Sequential(nn.Linear(2,2)); loaders={'train':[0],'val':[0]}; config=training.TrainingConfig(epochs=5,patience=2,freeze_backbone_epochs=0)
    result=training.run_training(model,loaders,tmp_path,config,train_fn=lambda *a,**k:_epoch(0),evaluate_fn=lambda *a,**k:_epoch(next(scores)))
    assert result['epochs_completed']==3 and saved.count('best.pt')==1 and [x for x in saved if isinstance(x,tuple)]==[('last.pt',0),('last.pt',1),('last.pt',2)]

def test_resume_starts_next_epoch_and_preserves_better_best(tmp_path,monkeypatch):
    model=nn.Sequential(nn.Linear(2,2)); config=training.TrainingConfig(epochs=3,freeze_backbone_epochs=0); saved=[]
    monkeypatch.setattr(training,'load_training_state',lambda *a:{'epoch':1,'best_f1':.9,'patience':0,'history':[{'epoch':0},{'epoch':1}]})
    monkeypatch.setattr(training,'save_behavior_checkpoint',lambda *a,**k:saved.append('best'))
    monkeypatch.setattr(training,'save_training_state',lambda *a,**k:None); monkeypatch.setattr(training,'write_artifacts',lambda *a:None); monkeypatch.setattr(training,'_write_csv',lambda *a:None)
    result=training.run_training(model,{'train':[0],'val':[0]},tmp_path,config,resume='last.pt',train_fn=lambda *a,**k:_epoch(0),evaluate_fn=lambda *a,**k:_epoch(.8))
    assert len(result['history'])==3 and not saved and result['best_f1']==.9

def test_write_artifacts_creates_required_files(tmp_path):
    history=[{'epoch':0,'train_loss':1.,'val_loss':1.,'val_accuracy':.5,'val_macro_f1':.4}]; metrics=_epoch(.4).metrics
    training.write_artifacts(tmp_path,history,metrics)
    assert {'history.csv','metrics.json','classification_report.csv','confusion_matrix.csv','confusion_matrix.png','training_curves.png'} <= {p.name for p in tmp_path.iterdir()}

def test_smoke_exactly_two_steps_and_evidence(tmp_path):
    model=Counting(); loader=DataLoader(TensorDataset(torch.randn(5,2),torch.tensor([0,1,0,1,0])),batch_size=1)
    evidence=training.run_smoke(model,loader,tmp_path,training.TrainingConfig(accumulation_steps=1,workers=0),'cpu')
    assert evidence['optimizer_steps']==2 and evidence['reload_success'] and (tmp_path/'smoke_metrics.json').is_file()
    assert (tmp_path/'last.pt').is_file()
    assert evidence['checkpoint']['sha256']
    assert evidence['reload_forward_finite'] is True
    assert evidence['elapsed_seconds'] >= 0
    assert evidence['loss_is_finite'] is True
    assert evidence['config']['input_frames'] == 16
    assert evidence['config']['input_size'] == 224

def test_cli_requires_checkpoint_and_resume_scope():
    base=['--index-root','i','--source-data-root','s','--output-root','o']
    with pytest.raises(SystemExit,match='checkpoint'): training.main(['--mode','evaluate']+base)
    with pytest.raises(SystemExit,match='resume'): training.main(['--mode','smoke','--resume','x']+base)

def test_learning_rate_name_and_cli_alias():
    assert training.TrainingConfig().learning_rate == 3e-4
    args=training.build_parser().parse_args(['--mode','train','--index-root','i','--source-data-root','s','--output-root','o','--learning-rate','.01'])
    assert args.learning_rate == .01

def test_smoke_loaders_cover_classes_deterministically():
    class Samples(TensorDataset):
        def __init__(self):
            super().__init__(torch.arange(48).float().view(24,2),torch.tensor(list(range(12))*2)); self.samples=[type('S',(),{'label_id':i+1})() for i in list(range(12))*2]
    source={s:DataLoader(Samples(),batch_size=4) for s in ('train','val','test')}
    a=training.make_smoke_loaders(source,training.TrainingConfig(workers=0)); b=training.make_smoke_loaders(source,training.TrainingConfig(workers=0))
    for split in source:
        labels=[source[split].dataset.samples[i].label_id for i in a[split].dataset.indices]
        assert set(labels)==set(range(1,13)) and a[split].dataset.indices==b[split].dataset.indices

def test_history_records_learning_rate(tmp_path,monkeypatch):
    monkeypatch.setattr(training,'save_behavior_checkpoint',lambda *a,**k:None); monkeypatch.setattr(training,'save_training_state',lambda *a,**k:None); monkeypatch.setattr(training,'write_artifacts',lambda *a:None)
    result=training.run_training(nn.Sequential(nn.Linear(2,2)),{'train':[0],'val':[0]},tmp_path,training.TrainingConfig(epochs=1,freeze_backbone_epochs=0),train_fn=lambda *a,**k:_epoch(0),evaluate_fn=lambda *a,**k:_epoch(.5))
    assert result['history'][0]['learning_rate']==pytest.approx(3e-4)

def test_smoke_loaders_cover_classes_present_in_leakage_safe_splits():
    class Samples(TensorDataset):
        def __init__(self, labels):
            super().__init__(torch.arange(len(labels)*2).float().view(len(labels),2),torch.tensor(labels)); self.samples=[type('S',(),{'label_id':i+1})() for i in labels]
    source={'train':DataLoader(Samples(list(range(1,12))),batch_size=4),
            'val':DataLoader(Samples(list(range(11))),batch_size=4),
            'test':DataLoader(Samples(list(range(12))),batch_size=4)}
    loaders=training.make_smoke_loaders(source,training.TrainingConfig(workers=0))
    for split in source:
        expected={sample.label_id for sample in source[split].dataset.samples}; actual={source[split].dataset.samples[i].label_id for i in loaders[split].dataset.indices}
        assert actual == expected

def test_resume_rejects_incompatible_config(tmp_path,monkeypatch):
    config=training.TrainingConfig(epochs=2,freeze_backbone_epochs=0)
    monkeypatch.setattr(training,'load_training_state',lambda *a:(_ for _ in ()).throw(ValueError('incompatible resume configuration')))
    with pytest.raises(ValueError,match='incompatible'): training.run_training(nn.Sequential(nn.Linear(2,2)),{'train':[0],'val':[0]},tmp_path,config,resume='x')

def test_late_corrupt_state_does_not_mutate_targets(tmp_path):
    import copy
    model=nn.Linear(2,2); optimizer=torch.optim.AdamW(model.parameters()); scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,2); scaler=training._scaler(False)
    training.save_training_state(tmp_path/'x.pt',0,model,optimizer,scheduler,scaler,.1,0,[],training.TrainingConfig()); payload=torch.load(tmp_path/'x.pt',weights_only=True); payload['rng']['torch']='bad'; torch.save(payload,tmp_path/'x.pt')
    before=copy.deepcopy(model.state_dict()); opt_before=copy.deepcopy(optimizer.state_dict())
    with pytest.raises(ValueError): training.load_training_state(tmp_path/'x.pt',model,optimizer,scheduler,scaler)
    assert all(torch.equal(before[k],v) for k,v in model.state_dict().items()) and optimizer.state_dict()==opt_before

def test_smoke_persists_and_reloads_real_state(tmp_path,monkeypatch):
    calls=[]; original_save=training.save_training_state; original_load=training.load_training_state
    monkeypatch.setattr(training,'save_training_state',lambda *a,**k:(calls.append('save'),original_save(*a,**k))[1])
    monkeypatch.setattr(training,'load_training_state',lambda *a,**k:(calls.append('load'),original_load(*a,**k))[1])
    loader=DataLoader(TensorDataset(torch.randn(4,2),torch.tensor([0,1,0,1])),batch_size=1)
    evidence=training.run_smoke(Counting(),loader,tmp_path,training.TrainingConfig(accumulation_steps=1,workers=0),'cpu')
    assert calls==['save','load'] and (tmp_path/'last.pt').is_file() and evidence['reload_success'] is True

def test_learning_rate_is_checkpoint_dataclass_field():
    config=training.TrainingConfig(learning_rate=.02)
    assert training.asdict(config)['learning_rate']==.02 and 'lr' not in training.asdict(config)

def test_incompatible_resume_rejected_before_any_state_or_rng_mutation(tmp_path):
    import copy, random
    source=nn.Linear(2,2); source_opt=torch.optim.AdamW(source.parameters()); source_sched=torch.optim.lr_scheduler.CosineAnnealingLR(source_opt,2); source_scaler=training._scaler(False)
    training.save_training_state(tmp_path/'last.pt',0,source,source_opt,source_sched,source_scaler,.1,0,[],training.TrainingConfig(seed=1))
    target=nn.Linear(2,2); before=copy.deepcopy(target.state_dict()); training.seed_everything(9); expected=(random.random(),np.random.rand(),torch.rand(1)); training.seed_everything(9)
    with pytest.raises(ValueError,match='incompatible'):
        training.run_training(target,{'train':[0],'val':[0]},tmp_path,training.TrainingConfig(epochs=2,seed=2,freeze_backbone_epochs=0),resume=tmp_path/'last.pt')
    actual=(random.random(),np.random.rand(),torch.rand(1))
    assert all(torch.equal(before[k],v) for k,v in target.state_dict().items()) and expected[0]==actual[0] and expected[1]==actual[1] and torch.equal(expected[2],actual[2])

def test_training_config_rejects_legacy_lr_keyword():
    with pytest.raises(TypeError): training.TrainingConfig(lr=.1)

def test_partial_accumulation_matches_equivalent_large_batches():
    training.seed_everything(4); initial=nn.Linear(2,2).state_dict(); x=torch.randn(5,2); y=torch.tensor([0,1,0,1,1])
    micro=nn.Linear(2,2); micro.load_state_dict(initial); large=nn.Linear(2,2); large.load_state_dict(initial)
    config=training.TrainingConfig(accumulation_steps=4,amp=False)
    training.train_epoch(micro,DataLoader(TensorDataset(x,y),batch_size=1,shuffle=False),torch.optim.SGD(micro.parameters(),.1),'cpu',config)
    training.train_epoch(large,DataLoader(TensorDataset(x,y),batch_sampler=[[0,1,2,3],[4]]),torch.optim.SGD(large.parameters(),.1),'cpu',training.TrainingConfig(accumulation_steps=1,amp=False))
    assert all(torch.allclose(a,b,atol=1e-7) for a,b in zip(micro.parameters(),large.parameters()))

def test_final_artifacts_use_best_epoch_metrics(tmp_path,monkeypatch):
    scores=iter([.8,.2]); captured=[]
    monkeypatch.setattr(training,'save_behavior_checkpoint',lambda *a,**k:None); monkeypatch.setattr(training,'save_training_state',lambda *a,**k:None); monkeypatch.setattr(training,'_write_csv',lambda *a,**k:None); monkeypatch.setattr(training,'write_artifacts',lambda root,history,metrics:captured.append(metrics['macro_f1']))
    training.run_training(nn.Sequential(nn.Linear(2,2)),{'train':[0],'val':[0]},tmp_path,training.TrainingConfig(epochs=2,freeze_backbone_epochs=0),train_fn=lambda *a,**k:_epoch(0),evaluate_fn=lambda *a,**k:_epoch(next(scores)))
    assert captured==[.8]

def test_resume_rejects_changed_epochs_before_restore(tmp_path):
    source=nn.Linear(1,1); opt=torch.optim.AdamW(source.parameters()); sched=torch.optim.lr_scheduler.CosineAnnealingLR(opt,2); scaler=training._scaler(False)
    training.save_training_state(tmp_path/'x.pt',0,source,opt,sched,scaler,.1,0,[],training.TrainingConfig(epochs=2))
    with pytest.raises(ValueError,match='epochs'): training.load_training_state(tmp_path/'x.pt',source,opt,sched,scaler,training.TrainingConfig(epochs=3))

@pytest.mark.parametrize('mutate',[lambda p:p.update(best_f1=float('nan')),lambda p:p['rng'].update(torch=torch.zeros(2)),lambda p:p['rng'].update(numpy_pos=999)])
def test_semantically_malformed_state_rejected(tmp_path,mutate):
    model=nn.Linear(1,1); opt=torch.optim.AdamW(model.parameters()); sched=torch.optim.lr_scheduler.CosineAnnealingLR(opt,2); scaler=training._scaler(False)
    training.save_training_state(tmp_path/'x.pt',0,model,opt,sched,scaler,.1,0,[],training.TrainingConfig()); payload=torch.load(tmp_path/'x.pt',weights_only=True); mutate(payload); torch.save(payload,tmp_path/'x.pt')
    with pytest.raises(ValueError): training.load_training_state(tmp_path/'x.pt',model,opt,sched,scaler)

def test_epoch_generator_sequence_is_resume_equivalent(tmp_path,monkeypatch):
    dataset=TensorDataset(torch.zeros(1,2),torch.zeros(1,dtype=torch.long)); loader=DataLoader(dataset,generator=torch.Generator())
    monkeypatch.setattr(training,'save_behavior_checkpoint',lambda *a,**k:None); monkeypatch.setattr(training,'save_training_state',lambda *a,**k:None); monkeypatch.setattr(training,'write_artifacts',lambda *a,**k:None); monkeypatch.setattr(training,'_write_csv',lambda *a,**k:None)
    full=[]; config=training.TrainingConfig(epochs=3,seed=17,freeze_backbone_epochs=0)
    training.run_training(nn.Linear(2,2),{'train':loader,'val':[0]},tmp_path,config,train_fn=lambda *a,**k:(full.append(loader.generator.initial_seed()) or _epoch(0)),evaluate_fn=lambda *a,**k:_epoch(.5))
    resumed=[]; monkeypatch.setattr(training,'load_training_state',lambda *a,**k:{'epoch':0,'best_f1':.5,'patience':0,'history':[{'epoch':0}],'config':training.asdict(config)})
    training.run_training(nn.Linear(2,2),{'train':loader,'val':[0]},tmp_path,config,resume='x',train_fn=lambda *a,**k:(resumed.append(loader.generator.initial_seed()) or _epoch(0)),evaluate_fn=lambda *a,**k:_epoch(.4))
    assert full==[17,18,19] and resumed==full[1:]

def test_atomic_png_failure_cleans_temp_and_preserves_destination(tmp_path):
    destination=tmp_path/'plot.png'; destination.write_bytes(b'old')
    class Figure:
        def savefig(self,path,format):
            path.write_bytes(b'partial'); raise RuntimeError('render failed')
    with pytest.raises(RuntimeError): training._atomic_figure(Figure(),destination)
    assert destination.read_bytes()==b'old' and list(tmp_path.iterdir())==[destination]

def test_powershell_script_has_formal_parameters_and_no_literal_chinese_path():
    text=(training.Path(__file__).parents[1]/'scripts'/'train_cvb_behavior.ps1').read_text(encoding='utf-8')
    assert 'param(' in text and '[Parameter(Mandatory=$true)]' in text and '$projectRoot' in text
    assert '$Checkpoint' in text and '$Resume' in text and 'F:\\new大创' not in text

def test_each_microbatch_backward_finishes_before_next_forward():
    state={'forward':0,'backward':0}
    class Observe(torch.autograd.Function):
        @staticmethod
        def forward(ctx,value): state['forward']+=1; return value
        @staticmethod
        def backward(ctx,gradient): state['backward']+=1; return gradient
    class Model(nn.Module):
        def __init__(self): super().__init__(); self.linear=nn.Linear(2,2)
        def forward(self,x):
            assert state['backward']==state['forward']
            return Observe.apply(self.linear(x))
    model=Model(); loader=DataLoader(TensorDataset(torch.randn(4,2),torch.tensor([0,1,0,1])),batch_size=1)
    training.train_epoch(model,loader,torch.optim.SGD(model.parameters(),.1),'cpu',training.TrainingConfig(accumulation_steps=4,amp=False))
    assert state=={'forward':4,'backward':4}

def test_real_getitem_augmentation_is_epoch_index_deterministic(tmp_path):
    import cv2
    from cattle_health_app.behavior.dataset import ClipSample, CvbClipDataset
    paths=[]
    for index in range(16):
        path=tmp_path/f'{index}.png'; image=np.arange(12*12*3,dtype=np.uint8).reshape(12,12,3); image=(image+index).astype(np.uint8); assert cv2.imwrite(str(path),image); paths.append(path.name)
    sample=ClipSample('s',tuple(paths),(.1,.1,.9,.9),1,'v',1.,0,'g')
    dataset=CvbClipDataset.__new__(CvbClipDataset); dataset.samples=[sample]; dataset.data_root=tmp_path; dataset.training=True; dataset.context=.15; dataset.size=16; dataset._injected_rng=None; dataset.seed=3; dataset._worker_rng=None; dataset._worker_rng_key=None
    continuous=training.EpochSeededDataset(dataset,23); continuous.set_epoch(1); expected=continuous[0][0]
    resumed=training.EpochSeededDataset(dataset,23); resumed.set_epoch(1); actual=resumed[0][0]
    assert torch.equal(expected,actual)

def test_real_getitem_epoch_changes_augmentation(tmp_path):
    import cv2
    from cattle_health_app.behavior.dataset import ClipSample, CvbClipDataset
    paths=[]
    for index in range(16):
        path=tmp_path/f'{index}.png'; assert cv2.imwrite(str(path),np.full((10,12,3),30+index,dtype=np.uint8)); paths.append(path.name)
    dataset=CvbClipDataset.__new__(CvbClipDataset); dataset.samples=[ClipSample('s',tuple(paths),(.1,.1,.9,.9),1,'v',1.,0,'g')]; dataset.data_root=tmp_path; dataset.training=True; dataset.context=.15; dataset.size=16; dataset._injected_rng=None; dataset.seed=3; dataset._worker_rng=None; dataset._worker_rng_key=None
    wrapped=training.EpochSeededDataset(dataset,23); wrapped.set_epoch(0); first=wrapped[0][0]; wrapped.set_epoch(1); second=wrapped[0][0]
    assert not torch.equal(first,second)

def test_weighted_partial_accumulation_matches_large_batches():
    training.seed_everything(31); initial=nn.Linear(2,2).state_dict(); x=torch.randn(5,2); y=torch.tensor([0,1,1,0,1]); weights=torch.tensor([1.,10.])
    micro=nn.Linear(2,2); micro.load_state_dict(initial); large=nn.Linear(2,2); large.load_state_dict(initial)
    expected=torch.nn.functional.cross_entropy(micro(x),y,weight=weights).item()
    micro_result=training.train_epoch(micro,DataLoader(TensorDataset(x,y),batch_size=1,shuffle=False),torch.optim.SGD(micro.parameters(),.1),'cpu',training.TrainingConfig(accumulation_steps=8,amp=False),weights)
    large_result=training.train_epoch(large,DataLoader(TensorDataset(x,y),batch_sampler=[[0,1,2,3,4]]),torch.optim.SGD(large.parameters(),.1),'cpu',training.TrainingConfig(accumulation_steps=1,amp=False),weights)
    assert all(torch.allclose(a,b,atol=1e-7) for a,b in zip(micro.parameters(),large.parameters()))
    assert micro_result.loss==pytest.approx(expected)

def test_unweighted_partial_equivalence_remains_covered():
    test_partial_accumulation_matches_equivalent_large_batches()

@pytest.mark.parametrize('weights',[None,torch.tensor([1.,10.])],ids=['unweighted','nonuniform-weighted'])
def test_multiple_accumulation_groups_match_independent_torch_reference(weights):
    training.seed_everything(47)
    inputs=torch.randn(5,2)*.1; targets=torch.tensor([0,1,1,0,1]); initial=nn.Linear(2,2).state_dict()
    actual=nn.Linear(2,2); actual.load_state_dict(initial); actual_optimizer=torch.optim.SGD(actual.parameters(),.05)
    result=training.train_epoch(actual,DataLoader(TensorDataset(inputs,targets),batch_size=1,shuffle=False),actual_optimizer,'cpu',training.TrainingConfig(accumulation_steps=4,amp=False),weights)

    reference=nn.Linear(2,2); reference.load_state_dict(initial); reference_optimizer=torch.optim.SGD(reference.parameters(),.05)
    for indices in (slice(0,4),slice(4,5)):
        reference_optimizer.zero_grad(set_to_none=True)
        loss=torch.nn.functional.cross_entropy(reference(inputs[indices]),targets[indices],weight=weights,reduction='mean')
        loss.backward()
        torch.nn.utils.clip_grad_norm_(reference.parameters(),5.)
        reference_optimizer.step()

    assert result.optimizer_steps==2
    for actual_parameter,reference_parameter in zip(actual.parameters(),reference.parameters()):
        assert torch.allclose(actual_parameter,reference_parameter,atol=1e-7)

def test_training_preflight_names_missing_official_classes():
    class Samples(TensorDataset):
        def __init__(self):
            super().__init__(torch.randn(10,2),torch.arange(10)); self.samples=[type('S',(),{'label_id':i})() for i in range(1,11)]
    loader=DataLoader(Samples(),batch_size=2)
    with pytest.raises(ValueError,match=r"training split is missing CVB classes: 11, 12"):
        training.require_training_class_coverage(loader)

def test_smoke_utc_interval_contains_training_call(tmp_path):
    from datetime import datetime,timezone
    start=datetime(2026,8,15,1,2,3,tzinfo=timezone.utc)
    during=datetime(2026,8,15,1,2,4,tzinfo=timezone.utc)
    finish=datetime(2026,8,15,1,2,5,tzinfo=timezone.utc)
    clock_values=iter((start,finish)); observed=[]
    original=training.train_epoch
    def probed_train(*args,**kwargs):
        observed.append(during)
        return original(*args,**kwargs)
    model=Counting(); loader=DataLoader(TensorDataset(torch.randn(4,2),torch.tensor([0,1,0,1])),batch_size=1)
    evidence=training.run_smoke(model,loader,tmp_path,
        training.TrainingConfig(accumulation_steps=1,workers=0),'cpu',
        clock=lambda:next(clock_values),train_fn=probed_train)
    parsed_start=datetime.fromisoformat(evidence['started_at_utc'])
    parsed_finish=datetime.fromisoformat(evidence['finished_at_utc'])
    assert parsed_start <= observed[0] < parsed_finish
    assert parsed_start.utcoffset().total_seconds() == 0
    assert parsed_finish.utcoffset().total_seconds() == 0

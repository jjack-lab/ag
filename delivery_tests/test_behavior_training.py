import random
import numpy as np
import pytest
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset
import cattle_health_app.behavior.train as training

@pytest.mark.parametrize('kwargs',[{'epochs':0},{'batch_size':0},{'accumulation_steps':0},{'lr':0},{'weight_decay':-1},{'patience':0},{'workers':-1},{'seed':-1},{'amp':1},{'freeze_backbone_epochs':31}])
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

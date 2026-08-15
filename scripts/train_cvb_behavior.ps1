param(
 [Parameter(Mandatory=$true)][ValidateSet('smoke','train','evaluate')][string]$Mode,
 [string]$SourceDataRoot='F:\CVB_dataset\000058916v001\data',
 [string]$IndexRoot,
 [string]$OutputRoot,
 [string]$Checkpoint,
 [string]$Resume,
 [ValidateSet('val','test')][string]$Split='test',
 [int]$Epochs=30,[int]$BatchSize=4,[int]$AccumulationSteps=4,
 [double]$LearningRate=0.0003,[double]$WeightDecay=0.0001,
 [int]$Patience=6,[int]$Workers=2,[int]$FreezeBackboneEpochs=2,[int]$Seed=20260814,
 [string]$Device='cuda'
)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
if(-not $IndexRoot){$IndexRoot=Join-Path $projectRoot 'data\cvb_behavior_v1'}
if(-not $OutputRoot){$OutputRoot=Join-Path $projectRoot 'outputs\training\cvb_x3d_v1'}
$log=Join-Path $OutputRoot ("{0}_run.log" -f $Mode)
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
$env:TORCH_HOME=Join-Path $projectRoot 'models\cache\torch'
$python='F:\deepl\anaconda1\envs\pytorch\python.exe'
if($Mode -eq 'evaluate' -and -not $Checkpoint){throw '-Checkpoint is required for evaluate mode'}
$arguments=@('-m','cattle_health_app.behavior.train','--mode',$Mode,'--index-root',$IndexRoot,'--source-data-root',$SourceDataRoot,'--output-root',$OutputRoot,'--split',$Split,'--device',$Device,'--epochs',$Epochs,'--batch-size',$BatchSize,'--accumulation-steps',$AccumulationSteps,'--learning-rate',$LearningRate,'--weight-decay',$WeightDecay,'--patience',$Patience,'--workers',$Workers,'--freeze-backbone-epochs',$FreezeBackboneEpochs,'--seed',$Seed)
if($Checkpoint){$arguments+=@('--checkpoint',$Checkpoint)}
if($Resume){$arguments+=@('--resume',$Resume)}
& $python @arguments *>&1 | Tee-Object -FilePath $log
$processExitCode=$LASTEXITCODE
if($processExitCode -ne 0){exit $processExitCode}

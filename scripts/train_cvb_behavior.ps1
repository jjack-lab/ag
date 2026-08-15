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
$utf8=New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding=$utf8
$env:PYTHONIOENCODING='utf-8'
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
$savedErrorActionPreference=$ErrorActionPreference
$ErrorActionPreference='Continue'
[IO.File]::WriteAllText($log,'',$utf8)
& $python @arguments *>&1 | ForEach-Object {$_; [IO.File]::AppendAllText($log,([string]$_)+[Environment]::NewLine,$utf8)}
$processExitCode=$LASTEXITCODE
$ErrorActionPreference=$savedErrorActionPreference
if($processExitCode -ne 0){exit $processExitCode}

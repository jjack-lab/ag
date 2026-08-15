param([string]$IndexRoot,[string]$SourceDataRoot='F:\CVB_dataset\000058916v001\data',[string]$OutputRoot)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
if(-not $IndexRoot){$IndexRoot=Join-Path $projectRoot 'data\cvb_behavior_v1'}
if(-not $OutputRoot){$OutputRoot=Join-Path $projectRoot 'outputs\training\cvb_x3d_v1'}
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
$python='F:\deepl\anaconda1\envs\pytorch\python.exe'
$evidence=Join-Path $OutputRoot 'data_validation.json'
$log=Join-Path $OutputRoot 'validation_run.log'
& $python -m cattle_health_app.behavior.validate_index --index-root $IndexRoot --source-data-root $SourceDataRoot --output $evidence *>&1 | Tee-Object -FilePath $log
$processExitCode=$LASTEXITCODE
if($processExitCode -ne 0){exit $processExitCode}

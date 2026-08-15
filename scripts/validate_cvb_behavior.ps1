param([string]$IndexRoot,[string]$SourceDataRoot='F:\CVB_dataset\000058916v001\data',[string]$OutputRoot)
$ErrorActionPreference='Stop'
$utf8=New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding=$utf8
$env:PYTHONIOENCODING='utf-8'
$projectRoot=Split-Path -Parent $PSScriptRoot
if(-not $IndexRoot){$IndexRoot=Join-Path $projectRoot 'data\cvb_behavior_v1'}
if(-not $OutputRoot){$OutputRoot=Join-Path $projectRoot 'outputs\training\cvb_x3d_v1'}
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
$python='F:\deepl\anaconda1\envs\pytorch\python.exe'
$evidence=Join-Path $OutputRoot 'data_validation.json'
$log=Join-Path $OutputRoot 'validation_run.log'
[IO.File]::WriteAllText($log,'',$utf8)
& $python -m cattle_health_app.behavior.validate_index --index-root $IndexRoot --source-data-root $SourceDataRoot --output $evidence *>&1 | ForEach-Object {$_; [IO.File]::AppendAllText($log,([string]$_)+[Environment]::NewLine,$utf8)}
$processExitCode=$LASTEXITCODE
if($processExitCode -ne 0){exit $processExitCode}

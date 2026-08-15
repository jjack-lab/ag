$ErrorActionPreference = 'Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$python = 'F:\deepl\anaconda1\envs\pytorch\python.exe'
$data = 'F:\CVB_dataset\000058916v001\data'
$output = Join-Path $projectRoot 'data\cvb_behavior_v1'
& $python -m cattle_health_app.behavior.cvb_index `
  --data-root $data `
  --train-ava "$data\cvb_in_ava_format\ava_train_set.csv" `
  --test-ava "$data\cvb_in_ava_format\ava_val_set.csv" `
  --output $output `
  --seed 20260814
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

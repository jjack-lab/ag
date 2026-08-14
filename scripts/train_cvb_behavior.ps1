$ErrorActionPreference='Stop'
$env:TORCH_HOME='F:\new大创\models\cache\torch'
$python='F:\deepl\anaconda1\envs\pytorch\python.exe'
if($args.Count -lt 1){throw 'mode argument is required: smoke, train, or evaluate'}
$mode=$args[0]
& $python -m cattle_health_app.behavior.train `
 --mode $mode `
 --index-root 'F:\new大创\data\cvb_behavior_v1' `
 --source-data-root 'F:\CVB_dataset\000058916v001\data' `
 --output-root 'F:\new大创\outputs\training\cvb_x3d_v1' `
 --seed 20260814
if($LASTEXITCODE -ne 0){exit $LASTEXITCODE}

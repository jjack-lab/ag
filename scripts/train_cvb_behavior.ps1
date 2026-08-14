$ErrorActionPreference='Stop'
$env:TORCH_HOME='F:\new大创\models\cache\torch'
$python='F:\deepl\anaconda1\envs\pytorch\python.exe'
$mode=if($args.Count){$args[0]}else{'smoke'}
& $python -m cattle_health_app.behavior.train `
 --mode $mode `
 --index-root 'F:\new大创\data\cvb_behavior_v1' `
 --source-data-root 'F:\CVB_dataset\000058916v001\data' `
 --output-root 'F:\new大创\outputs\training\cvb_x3d_v1' `
 --model-root 'F:\new大创\models\behavior' `
 --seed 20260814
if($LASTEXITCODE -ne 0){exit $LASTEXITCODE}

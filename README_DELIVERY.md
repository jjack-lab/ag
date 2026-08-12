# 交付说明

请以项目根目录的 `README.md` 为唯一运行说明。

快速检查：

```powershell
Set-Location -LiteralPath 'F:\new大创'
$env:AGRINEBULA_PYTHON = 'F:\deepl\anaconda1\envs\pytorch\python.exe'
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_delivery.ps1 -CheckOnly
```

启动和停止：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_delivery.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\stop_delivery.ps1
```

健康风险结果只用于辅助筛查，不是兽医疾病诊断。
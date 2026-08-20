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

## 运行日志与启动预检

运行日志位于 `data/logs`：API 分别写入 `api.stdout.log` 和 `api.stderr.log`，Web 分别写入 `web.stdout.log` 和 `web.stderr.log`。

- 每次进入服务启动阶段（启动 API/Web）都会覆盖上一轮的四个日志文件；若预检、依赖或端口检查提前失败，则保留上一轮日志。
- API/Web 未通过就绪检查时，脚本会自动显示每个非空日志的最后 40 行；更早的预检或端口错误会直接显示在控制台。
- 停止服务不会删除日志，便于结束运行后排查。

启动预检会输出 `detector` 和 `behavior` 的状态、路径与 SHA-256：

- 检测模型缺失会阻断启动（`detector` 是交付运行的必需项）。
- 行为模型缺失时，`behavior` 状态显示 `unavailable`，但不阻断 YOLO 检测、跟踪、轨迹和原有规则健康分析。

行为模型仍属于研究演示能力，健康风险结果仍只用于辅助筛查，不是兽医疾病诊断。

行为研究模型安装在 `models/behavior/cvb_x3d_v2_best.pt`，SHA-256 为：

```text
731c6ed39dcf002915e888c829e1f86727f815331a2b3c21d06a17d40d62a08e
```

首次视频行为推理需要加载 X3D，耗时会高于后续任务。CUDA 可用时优先使用 GPU，加载失败时尝试 CPU。视频任务完成后可下载行为时间线 CSV、行为汇总 CSV 和 JSON 报告，并在页面查看视频内 Track ID 的行为时长。

行为模型缺失或运行失败不会中断 YOLO 检测、跟踪、轨迹和规则健康报告，页面会显示“行为模型未加载”或失败原因。

当前行为模型 Accuracy 为 `0.8342201644668648`，Macro-F1 为 `0.2188597785907576`，类别不均衡明显。行为识别属于研究演示结果。

研究演示结果仅用于风险筛查辅助，不是疾病诊断。

健康风险结果只用于辅助筛查，不是兽医疾病诊断。
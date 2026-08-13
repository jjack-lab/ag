# 星牧智控整合版

这是 E、F 两盘项目成果的独立整合版本，项目目录为 `F:\new大创`。原项目不会被本项目覆盖或修改。

当前版本面向可运行演示，已经接通：

- YOLO11 牧场牲畜图片检测；
- 本地视频异步检测；
- ByteTrack 持续跟踪和 Track ID；
- 带框图片、带跟踪视频和轨迹 CSV；
- 静止、离群、活动量下降等规则型健康风险提示；
- 健康告警 CSV、个体汇总 CSV 和 HTML 报告；
- SQLite 任务与告警记录；
- FastAPI 后端与 React 浏览器控制台。

健康风险结果用于辅助筛查，不是兽医疾病诊断。

## 最简单的启动方式（推荐）

在资源管理器中打开 `F:\new大创`：

1. 双击 `启动项目.bat`。
2. 脚本完成环境和模型检查后会启动前后端，并自动打开 <http://127.0.0.1:5173>。
3. 使用结束后双击 `停止项目.bat`，释放 8000 和 5173 端口。

如果启动失败，窗口会保留并显示原因。下面的 PowerShell 方式可用于进一步诊断。

## PowerShell 启动与诊断

打开 PowerShell：

```powershell
Set-Location -LiteralPath 'F:\new大创'
$env:AGRINEBULA_PYTHON = 'F:\deepl\anaconda1\envs\pytorch\python.exe'
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_delivery.ps1
```

启动后访问：

- Web 控制台：<http://127.0.0.1:5173>
- API 文档：<http://127.0.0.1:8000/docs>
- 服务状态：<http://127.0.0.1:8000/api/health>

结束服务：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\stop_delivery.ps1
```

## 启动前检查

```powershell
Set-Location -LiteralPath 'F:\new大创'
$env:AGRINEBULA_PYTHON = 'F:\deepl\anaconda1\envs\pytorch\python.exe'
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_delivery.ps1 -CheckOnly
```

看到 `Delivery preflight passed.` 说明 Python、模型、API入口、Node/npm和Web清单齐全。

## 使用方式

### 图片检测

1. 打开 Web 控制台。
2. 进入智能识别工作台并选择图片识别。
3. 上传 JPG、JPEG、PNG 或 BMP。
4. 设置置信度、IoU和类别过滤。
5. 开始识别，查看并下载带框结果。

### 视频检测与健康风险提示

1. 切换到视频识别。
2. 上传 MP4、AVI、MOV 或 MKV。
3. 选择 ByteTrack 或 BoT-SORT。
4. 提交任务并等待进度到达完成。
5. 播放带 Track ID 的结果视频。
6. 下载结果视频、轨迹、告警、个体健康汇总和 HTML 报告。

当前Windows环境使用OpenCV `mp4v`生成结果视频。若浏览器不能直接播放，请点击“下载结果视频”，使用本地播放器查看。要保证浏览器内H.264播放，需要另行安装并配置兼容的FFmpeg/OpenH264编码器。

视频为后台任务。浏览器会显示按已处理帧数计算的真实进度，任务失败时 API 会保存失败状态和错误信息。默认单个上传文件上限为512MB，可通过 `AGRINEBULA_MAX_UPLOAD_MB` 调整。

## 模型

默认模型：

```text
models/detection/yolo11s-waid.pt
```

模型来自 WAID4500 YOLO11s、960输入、120轮训练。SHA-256：

```text
46d734cba7553f31e89e739156f50e9a675b176f798c70159838497531771a64
```

可通过 `AGRINEBULA_DETECTOR_MODEL` 指定其他模型，但模型必须兼容当前 Ultralytics YOLO11 运行时。

## 首次安装到其他电脑

需要 Python 3.8、Node.js 和 npm。建议创建独立虚拟环境：

```powershell
Set-Location -LiteralPath 'F:\new大创'
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Set-Location .\web
npm ci
Set-Location ..
```

将已验证的权重复制到 `models/detection/yolo11s-waid.pt`，再运行启动前检查。

## 验证结果

2026-08-12 已完成以下实际验证：

- Python测试：52项通过；
- React测试：7项通过；
- React生产构建：通过；
- 一键启动：API和Web均可访问；
- 固定WAID图片：检测到26头牛并生成带框图片；
- 固定视频：210帧输入与210帧输出一致；
- 视频跟踪：26个Track ID、5460行轨迹；
- 健康规则：26条静止风险记录；
- CSV、HTML、SQLite、API仪表盘与模型哈希一致。

重新运行自动测试：

```powershell
$env:AGRINEBULA_PYTHON = 'F:\deepl\anaconda1\envs\pytorch\python.exe'
& $env:AGRINEBULA_PYTHON -m pytest -q -p no:cacheprovider

Set-Location .\web
npm test -- --run --reporter=dot
npm run build
```

## 输出目录

```text
data/
├─ agrinebula.db
└─ media/
   ├─ uploads/
   └─ results/
```

视频任务的跟踪视频、轨迹、健康告警和报告位于 `data/media/results/<job-id>/`。

## 当前边界

当前已经实现检测、跟踪和基于轨迹规则的健康风险提示，但尚未接入经过训练的时序行为分类模型、Isolation Forest轨迹异常模型或具体疾病识别模型。具体疾病诊断必须在获得合规、可靠的疾病标注数据后单独验证。

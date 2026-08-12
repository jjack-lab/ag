# 星牧智控：视频追踪健康检测交付说明

## 当前可交付能力

本版本已把训练完成的 YOLO11s 模型接入本地 FastAPI/React 系统，可完成：

- 牛只图片识别；
- 视频上传与后台异步处理；
- YOLO11 + ByteTrack 持续追踪和稳定 Track ID；
- 每帧轨迹、位置、框大小和置信度导出；
- 长时间静止、疑似卧倒、离群、活动量下降、区域停留等规则型健康风险；
- 标注视频、轨迹 CSV、告警 CSV、个体健康汇总 CSV 和 HTML 健康报告；
- SQLite 任务状态与真实告警接口；
- 浏览器端任务进度、追踪视频和证据文件展示。

本系统是科研与牧场辅助筛查工具，不是兽医诊断系统。任何健康风险都必须由现场人员或兽医复核，不能直接作为治疗依据。

## 已验证环境

- Windows 10/11
- Python 3.8.20（现有 `pytorch` Conda 环境）
- Node.js 24.14.0
- npm 11.9.0
- FastAPI 0.124.4
- Ultralytics/项目内 YOLO 实现

`requirements.txt` 已改为兼容 Python 3.8 的 FastAPI 和 Uvicorn 版本。若使用其他 Python，可通过环境变量指定：

```powershell
$env:AGRINEBULA_PYTHON = "D:\path\to\python.exe"
```

## 模型

- 训练产物来源：`E:\大创\WAID_YOLO11\runs\waid4500_v1_yolo11s_img960_e120\weights\best.pt`
- 交付位置：`models\detection/yolo11s-waid.pt`
- 文件大小：19,283,703 字节
- SHA-256：`46D734CBA7553F31E89E739156F50E9A675B176F798C70159838497531771A64`
- 固定测试指标：Precision 0.93521、Recall 0.91298、mAP50 0.95182、mAP50-95 0.58098

权重被 `.gitignore` 排除，不会意外推送到代码仓库。交付压缩包必须保留上述交付位置。

## 首次安装

在项目根目录执行：

```powershell
& "F:\deepl\anaconda1\envs\pytorch\python.exe" -m pip install -r requirements.txt
Set-Location .\web
npm ci
Set-Location ..
```

若官方 PyPI 在当前网络环境中出现证书问题，可使用：

```powershell
& "F:\deepl\anaconda1\envs\pytorch\python.exe" -m pip install -r requirements.txt `
  --index-url http://mirrors.aliyun.com/pypi/simple/ `
  --trusted-host mirrors.aliyun.com
```

## 一键启动

先只做环境预检：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_delivery.ps1 -CheckOnly
```

正式启动：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_delivery.ps1
```

- Web 控制中心：`http://127.0.0.1:5173`
- FastAPI 文档：`http://127.0.0.1:8000/docs`
- 服务健康检查：`http://127.0.0.1:8000/api/health`
- 模型状态：`http://127.0.0.1:8000/api/models`

启动脚本使用隐藏后台进程，并在终端打印 API 和 Web 的 PID。

## 使用流程

1. 打开 Web 控制中心；
2. 在“智能识别工作台”切换到“视频识别”；
3. 上传 MP4、AVI、MOV 或 MKV；
4. 等待任务由“排队/运行中”变为“完成”；
5. 查看带 Track ID 的视频；
6. 打开健康报告，或下载轨迹 CSV 做论文统计。

运行文件保存在：

```text
data/
├── agrinebula.db
└── media/
    ├── uploads/
    └── results/
        └── <job-id>/
            ├── *_tracked.mp4
            ├── *_tracks.csv
            ├── *_health_alerts.csv
            ├── *_health_summary.csv
            └── *_health_report.html
```

## 测试

Python：

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
& "F:\deepl\anaconda1\envs\pytorch\python.exe" -m pytest `
  delivery_tests -q -p no:cacheprovider
```

Web：

```powershell
Set-Location .\web
npm test -- --run --reporter=dot
npm run build
Set-Location ..
```

## 第一阶段边界

本次交付底座已经具备“检测 + 追踪 + 可解释健康规则”，但尚未把 CBVD-5/CVB 行为模型和 Isolation Forest 轨迹异常模型接入运行链路。下一阶段会在当前 Track ID、轨迹 CSV、异步任务和证据接口上继续增加六类行为识别、轨迹异常分数与融合风险，不需要推翻现有系统。

第三方数据与代码的许可证和下载状态见 `THIRD_PARTY_DATA.md`。

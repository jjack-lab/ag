# ICAERUS 羊视频识别演示与实测（2026-10-14）

## 直接看视频

- 浏览器友好的 H.264 演示视频：`data/verification/icaerus_sheep_20261014/icaerus_yolo11n/crop_23.11.23-12_demo.mp4`（99 帧、9 fps、1960×1080、27,425,541 字节；SHA-256 `8a31d9d3b9b1f1585a59d14506d6932ffa5f95c83ad15bbb944ba8efbdf304b9`）。左侧是原视频上重新绘制的小号羊检测框与 Track ID，右侧显示模型来源、时间、逐帧数量、部分 ID 置信度和画面位移档位。
- 原始带框跟踪视频及轨迹 CSV：同目录下的 `crop_23.11.23-12_tracked.mp4` 与 `crop_23.11.23-12_tracks.csv`。另有 `data/verification/icaerus_sheep_20261014/evaluation.json` 保存输入、权重、预测文件哈希与原始指标。以上运行产物在 `.gitignore` 排除的 `data/verification/` 下，不提交视频大文件。

## 模型、输入与测量

- 来源视频及标注：官方 [ICAERUS Zenodo 12094356](https://zenodo.org/records/12094356)，其中 `crop_23.11.23-12.MP4` 为 99 帧、1,956 个真值羊框；数据下载与配对核验见 [数据记录](2026-10-14-icaerus-sheep-video-download.md)。
- 原交付模型：`models/detection/yolo11s-waid.pt`，此轮仅用于对比，没有替换产品默认模型。
- 演示模型：ICAERUS [yolo11n_all.pt 官方文件](https://github.com/ICAERUS-EU/UC3_Livestock_Monitoring/blob/main/models/sheep_detection/yolo11n_sheep/yolo11n_all.pt)，本机保存在 `data/external/sheep_icaerus_model/raw/yolo11n_all.pt`，5,488,666 字节，Git blob SHA-1 `3f927657fb195241d825a9bba68c7802e49a2149` 与官方 GitHub API 一致，SHA-256 `666fcf6d87c57ee87a5c001dac4ab35fc7f65be439ddd30a70714e9f4718e95a`。这是另一个公开项目的羊专用模型，不是本项目训练的权重；它未被安装到产品默认模型目录。
- 两次运行都使用本项目 `process_tracked_video()`、ByteTrack、`conf=0.25`、推理 NMS IoU `0.45`、`imgsz=960`、羊类 ID `0`，从逐帧预测 CSV 与公开 GT 按框 IoU≥0.5 匹配。该视频 99 帧均有 GT，因此每帧都参加评测。

| 模型 | TP | FP | FN | Precision | Recall | F1 | 匹配帧 ID 切换 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 当前交付检测模型 | 2 | 0 | 1954 | 100.0% | 0.10% | 0.20% | 0 |
| ICAERUS YOLO11n 羊模型 | 1722 | 257 | 234 | 87.01% | 88.04% | 87.52% | 2 |

交付模型的 Precision=100% 只基于两个匹配框，没有实际覆盖羊群的意义。演示模型共输出 1,979 条带 ID 的预测框、47 个视频内 Track ID 和 80 个画面位移切换事件。两组数字只描述**这一段公开无人机视频**；ICAERUS 模型与数据来自同一项目，训练数据关联尚未排除，因此不能把它写成独立测试或新牧场泛化结果。

## 画面中哪些功能可见

1. 羊只检测：每只预测羊的彩色框；右侧列出部分活跃 ID 的预测置信度。
2. 视频内追踪：框旁的小号 `ID`、逐帧活跃 ID 数；ID 不能跨视频当作同一只羊。
3. 活动相关观测：轨迹框中心的**画面位移**分为低/中/高；右侧显示逐帧人数与部分 ID 状态。无人机镜头运动未补偿，因此高画面位移**不等于羊奔跑**，也不代表采食、卧姿、健康评分或疾病诊断。
4. 可核对结果：预测轨迹 CSV、原始 MOT 标注、转换后的 GT CSV 和 `evaluation.json` 均保留，可重算上表。

演示视频可用下列命令从原视频与已生成轨迹重新绘制（Windows 优先 H.264，其他环境回退 MP4V）：

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m cattle_health_app.sheep_demo_video `
  --source-video 'data\external\sheep_zenodo_12094356\derived\depot_zenodo_2_annotations\Videos\crop_23.11.23-12.MP4' `
  --tracks-csv 'data\verification\icaerus_sheep_20261014\icaerus_yolo11n\crop_23.11.23-12_tracks.csv' `
  --output 'data\verification\icaerus_sheep_20261014\icaerus_yolo11n\crop_23.11.23-12_demo.mp4' `
  --model-name 'ICAERUS YOLO11n'
```

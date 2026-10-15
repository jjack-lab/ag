# 公开羊视频网页链路验收（2026-10-15）

## 输入与任务

- 从本地网页 `http://127.0.0.1:5173/` 的识别工作台上传 ICAERUS `crop_23.11.23-12.MP4`，选“羊”、ByteTrack、置信度 0.25、NMS IoU 0.45。源视频 SHA-256：`a161bf717ffdc56c6db29465b642a87cee9edf2bfdbf00c86e4d0089b72270e2`。
- 网页创建的任务 ID：`b6584849f10c403c8a1404e8f91748b8`。本机 SQLite 中状态为 `completed`，结果 99 帧、1 个视频内 Track ID（10）、0 条牛规则告警、羊行为模型 `unavailable`，无羊活动摘要（连续追踪帧不足）。页面显示视频播放器、轨迹 CSV 下载、事件时间轴、画面纠错和人工复核入口。
- 浏览器文件选择器在导入标注时中断，故通过同一个本地 `POST /api/evaluations` 接口导入转换后的真值 CSV。评测 ID：`9cc4bc9791364cfdbf9329e8e7a0dc2b`。登记来源为 [Zenodo 12094356](https://zenodo.org/records/12094356)、许可 `CC BY 4.0`、划分 `development`。这段视频此前已用于模型对比，因此不能标为独立外部测试。

## 可核验结果

网页任务评测接口返回 99 个有标注帧、1,956 个真值框、TP 2、FP 0、FN 1,954；IoU≥0.5 时 Precision 100.00%（只匹配到两个框）、Recall 0.102%、F1 0.204%、匹配帧 ID 切换 0。与 [离线实跑记录](2026-10-14-icaerus-sheep-model-demo.md) 的默认模型结果一致。标注 CSV SHA-256：`ece519fcd065005223ab0d1dc47ec85c78eaf6c279c53512e3ce0d923ee170ed`。

结果视频位于 `data/media/results/b6584849f10c403c8a1404e8f91748b8/a0f278c71b3c4aa4ab6acf5673d487de_tracked.mp4`，HTTP 返回 `200 OK`、`video/mp4`、`accept-ranges: bytes`、39,371,454 字节；本机 OpenCV 完整解码 99/99 帧（1440×1080、9 fps）。轨迹 CSV 地址也返回 `200 OK`。浏览器中已看到播放器与下载链接，但未成功观察播放器实际播放或在页面中显示新评测记录，这两项仍须复核。

## 产品判断

当前网页默认权重适合展示此样本上的失败和纠错流程，**不能展示为羊群盘点、丢失提醒或羊只健康检测已可用**。离线 ICAERUS 羊专用模型的同源演示视频未接入网页，不能冒充本任务结果。要面向牧场盘点和防丢失，至少需要现场稳定身份核对、按区域和时段的期望存栏数、拍摄覆盖率及人工确认机制；当前视频内 Track ID 不能跨天识别同一只羊。健康与疾病功能还需要带出处的兽医诊断和独立验证数据。

## 公开羊权重接入调查

[ICAERUS 仓库](https://github.com/ICAERUS-EU/UC3_Livestock_Monitoring) 标记为 GPL-3.0，根目录有 [GPL-3.0 LICENSE](https://github.com/ICAERUS-EU/UC3_Livestock_Monitoring/blob/main/LICENSE)，但未见针对 `yolo11n_all.pt` 的单独许可声明。接入/分发权重前需明确其适用许可与归属；当前仅在本机被忽略的实验目录使用，未改产品默认权重或提交模型文件。

[官方 YOLO11n 模型说明](https://github.com/ICAERUS-EU/UC3_Livestock_Monitoring/blob/main/models/sheep_detection/yolo11n_sheep/README.md) 列出的训练来源是五个 Roboflow 数据集与 [Zenodo 18889623 羊图像集](https://zenodo.org/records/18889623)，没有明确写使用本次 Zenodo 12094356 的四段视频。但 18889623 的说明称图像选自同项目 2023–2026 年积累的原始影像；仅凭公开说明无法逐帧排除与本视频同场景或抽帧重叠。因此上述 87.52% F1 只能标为同项目演示，不能写成独立验证。

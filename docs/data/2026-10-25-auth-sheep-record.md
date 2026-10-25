# AUTH-Sheep 独立来源视频记录

日期：2026-10-25。用途：核对图一羊检测模型在非 ICAERUS 来源视频上的表现。原始数据属于 AUTH-Sheep 作者，不提交到本仓库。

## 来源与权利

- 官方记录：[AUTH-Sheep Zenodo 13843376](https://zenodo.org/records/13843376)，DOI `10.5281/zenodo.13843376`。发布单位 Fraunhofer Institute for Digital Media Technology，与 ICAERUS 项目不同。
- [作者官方仓库](https://github.com/idmt-odoll/AUTH-Sheep)写明 CC BY 4.0。Zenodo 页面许可证栏当前未显示具体值；使用时以作者仓库声明和来源署名为依据，若要进一步分发原始数据应再次核对记录元数据。
- 官方说明：4 段 UAV 视频，逐帧框与视频内一致的 Track ID。本轮只取得 video1；不同机构来源降低同项目训练重叠风险，但不能凭机构不同保证逐帧绝无重叠。

## 本机文件核验

| 文件 | 官方 MD5 | 本机 MD5 | 结果 |
| --- | --- | --- | --- |
| `ReadMe.txt` | `d66e74f0c97c86502ad21aaa1aa1ef29` | `d66e74f0c97c86502ad21aaa1aa1ef29` | 匹配 |
| `video1_annotations_hbb.json` | `37cbf28e82ba14d52d548e0ac4f0f742` | `37cbf28e82ba14d52d548e0ac4f0f742` | 匹配 |
| `video1_instances_default.json` | `6569b46cc8e8e51ea3428c473400265b` | `6569b46cc8e8e51ea3428c473400265b` | 匹配 |
| `video1.mp4` | `df80976b22d869394d823bbaf68d736b` | `df80976b22d869394d823bbaf68d736b` | 匹配 |

视频为 3840×2160、约 29.97 fps、1,198 帧；首帧及末帧可解码。HBB 与 CVAT 原始标注均有 21,336 条，同 ID 的帧与类别逐条一致。羊框 20,814、人框 522；羊框中 613 个部分越界，转换时裁到图内，不删掉这些目标。转换 CSV 位于 `data/external/auth_sheep/derived/video1_ground_truth.csv`，SHA-256 `8c27ab65cc8131c015fc5c9d88bf097891840fbb902b94a662fe9d23878bf4b6`，共 1,198 个有羊标注帧。25 行临界浮点坐标经保守舍入后严格落在归一化画面内。

## 评测口径

网站当前默认权重与 ICAERUS 研究候选使用同一 video1 原帧、`conf=0.25`、NMS IoU=0.45、ByteTrack、输入尺寸 640、羊类 ID=0；框匹配 IoU≥0.5。分别记录 TP/FP/FN、Precision/Recall/F1 和视频内 ID 切换。预测、指标与权重哈希保存在 `data/verification/auth_sheep_20261025/`，该目录被 Git 忽略。

本数据只检验这段公开航拍视频，不证明固定牧场机位或疾病筛查效果；原始图一 ICAERUS 结果保留为开发样例。

## video1 实测

| 模型 | TP | FP | FN | Precision | Recall | F1 | ID 切换 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 网站默认 `yolo11s-waid.pt` | 10,561 | 7,501 | 10,253 | 58.47% | 50.74% | 54.33% | 81 |
| ICAERUS 羊专用研究候选 `yolo11n_all.pt` | 13,247 | 8,277 | 7,567 | 61.55% | 63.64% | 62.58% | 70 |

候选相对默认提高 Recall 12.90 个百分点、F1 8.25 个百分点；本视频仅属于独立来源的初步比较。候选权重的再分发许可仍需核实，且不能仅凭一个视频排除所有训练图像重叠；因此没有改交付默认模型或历史图一卡片。两组结果可用保存的预测 CSV 及转换后的 GT CSV 通过 `cattle_health_app.dataset_evaluation.evaluate_annotations()` 复算。默认模型首次推理后，因转换 CSV 中 25 行浮点舍入越界，评测器正确拒绝计分；修复 CSV 后用 `--reuse-predictions` 重算，未重新推理或改预测。

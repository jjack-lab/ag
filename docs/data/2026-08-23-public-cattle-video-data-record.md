# 公开牛只视频数据与操作记录

## 记录目的

本文件回答三个问题：项目引用了什么数据集、文件存放在哪里、对数据进行了哪些操作。它与 `data/external/registry.json`、各数据集 `manifests/` 下的机器可读清单共同构成数据溯源证据。

当前状态：`experiment_complete`。截至 2026-08-24，CBVD-5 version 11 的 687 个官方连续视频和三份标注/标签文件已在 5 GiB 预算内完成下载、逐文件哈希、严格/扩展标签映射、虚拟片段清单生成与人工抽查；冻结模型已完成 1000 个逻辑样本的零样本外部推理及 6 类可控退化实验。真实结果和限制见 `docs/experiments/2026-08-23-cross-domain-behavior-results.md`。

## 数据存放边界

- 项目根目录：`F:\new大创`
- 外部数据根目录：`F:\new大创\data\external`
- 下载压缩包：`data/external/<dataset_id>/archives/`
- 不修改的原始解压文件：`data/external/<dataset_id>/raw/`
- 派生片段和缓存：`data/external/<dataset_id>/derived/`
- 可提交来源清单：`data/external/<dataset_id>/manifests/`
- 实验输出：`outputs/cross_domain/cvb_to_cbvd5/`

原始视频、压缩包、派生帧和推理缓存不提交 Git。登记表、清单、哈希、排除原因、指标和文档可以提交。

## 数据集登记

| 数据集 | 官方来源 | 许可状态 | 计划用途 | 当前操作 |
|---|---|---|---|---|
| CVB | DOI `10.25919/3g3t-p068` | 已登记 CC BY-NC-SA 4.0 | 现有模型训练域、校准域和域内基线 | 本轮未重新下载 |
| CBVD-5 | Scientific Reports 论文与 Kaggle version 11 | Kaggle 官方页：CC0 Public Domain | 首选外部测试域 | 已下载、审计并完成冻结外部推理与压力实验 |
| MmCows | 官方 GitHub 与 Hugging Face 数据卡 | 数据卡 CC BY-NC-SA 4.0 | CBVD-5 受阻时的后备数据；未来多模态 | 尚未下载 |
| CattleEyeView | 官方 GitHub | 仓库代码许可不能替代数据许可 | 后续顶视检测/跟踪候选 | 本轮不使用 |

## 下载预算与许可门槛

- 本轮所有新增外部文件累计上限：`5 GiB`。
- 只有注册表 `license_status` 为 `verified` 的数据才能进入下载命令。
- 需要登录时只使用官方流程，账号令牌不得写入项目。
- 许可不明确、文件超过预算或标注不能与连续视频关联时，先更新计划和本文件，再选择后备方案。

## 操作日志

| 时间 | 数据集 | 操作 | 输入 | 输出 | 大小/SHA-256 | 结果 |
|---|---|---|---|---|---|---|
| 2026-08-23 | 全部候选 | 创建机器可读登记表 | 官方论文/数据页信息 | `data/external/registry.json` | 由 Git 记录 | 完成；未下载媒体 |
| 2026-08-23 | CBVD-5 v11 | 读取官方数据集元数据 | Kaggle 公开 API | `data/external/cbvd5/manifests/official_dataset_metadata_v11.json` | 8,592 B；`e3a6338572af50e7884c42f1a2f0da4c0f303126ec7e3e88682b1ba7f6f2079f` | 许可 CC0；全量 11,642,084,084 B |
| 2026-08-23 | CBVD-5 v11 | 下载 VIA 原始标注 | `CBVD-5.csv` | `data/external/cbvd5/archives/CBVD-5.csv` | 2,409,930 B；`da271e825931eb36e4877b61280b2a0ac0019918b692a8b27355f16ada9c0aa9` | 完成；仅用于结构核验 |
| 2026-08-23 | CBVD-5 v11 | 下载 AVA 训练标注 | `miniannotations/ava_train_v2.1.csv` | `data/external/cbvd5/archives/ava_train_v2.1.csv` | 1,733,774 B；`fad18b34f43c2f7efbbe5dfbdc3b10c27dbc7bca5306076e8ad61a32ccdef920` | 完成；确认 8 列 AVA 结构 |
| 2026-08-23 | CBVD-5 v11 | 下载标签映射 | `miniannotations/labelmap.txt` | `data/external/cbvd5/archives/labelmap.txt` | 67 B；`78ae410e0005ffca882e0709e0ebc31b7fbab3fb80be3809eff37a28404125ba` | 完成；1站立、2卧躺、3采食、4饮水、5反刍 |
| 2026-08-23 | CBVD-5 v11 | 解析真实 AVA 训练标注并合并同框原子标签 | `archives/ava_train_v2.1.csv` | 内存审计；摘要写入 `manifests/official_inventory_summary.json` | 22,754个有效合并框；严格映射11,300个 | 排除32个坏框、12个姿态冲突 |
| 2026-08-23 | CBVD-5 v11 | 下载官方连续视频目录并逐文件校验 | Kaggle `videos/videos` | `data/external/cbvd5/raw/videos/videos/`；`manifests/acquired_video_files_v11.json` | 687个 MP4，共3,480,105,107 B；每个文件记录 SHA-256 | 完成；1个复用、686个新下载，未修改原视频 |
| 2026-08-23 | CBVD-5 v11 | 生成冻结外测虚拟片段清单 | 官方 AVA 标注、视频盘点与哈希 | `evaluation_clips_strict.csv`、`evaluation_clips_extended.csv`、`source_videos.csv`、`excluded_samples.csv`、`manifest_summary.json` | strict 400条/4类/211源视频；extended 600条/6类/298源视频 | 完成；每类固定100条，seed=20260823，均为external_test_only |
| 2026-08-23 | CBVD-5 v11 | 人工审计确定性样本联系表 | extended清单，每类按sample_id取前10条 | 忽略目录 `outputs/cross_domain/cvb_to_cbvd5/audit/`；摘要 `manifests/manual_audit_summary.json` | 60条；审计行 SHA-256 `23595d6d...37ad8da` | 60/60主体和裁剪可见；0个明显姿态冲突；0个新增排除 |
| 2026-08-24 | CBVD-5 v11 | 冻结零样本外部推理 | strict 400条、extended 600条；CVB X3D checkpoint | `outputs/cross_domain/cvb_to_cbvd5/predictions.csv`、`metrics.json`、报告图表 | 1000逻辑样本/600物理片段；`metrics.json` SHA-256 `9ce51921...b489a48` | 完成；CUDA；1284.253秒；strict Macro-F1 0.0048，表明直接迁移失效 |
| 2026-08-24 | CBVD-5 v11 | 固定压力子集可控退化 | 6种退化×3个非零等级×200逻辑样本 | `stress/`条件缓存、`stress_metrics.csv`、`stress_curves.png` | 18个条件缓存、96行指标；压力集 SHA-256 `cf25bf15...97e6a2` | 完成；非零压力推理合计6665.834秒 |
| 2026-08-24 | CBVD-5 v11 | 数值一致性核验 | 概率、逐样本接受标志、协议指标和压力网格 | 核验摘要写入实验结果文档 | 概率和最大误差`4.44e-16`；0个argmax不一致 | 通过；8组接受数、覆盖率、96行压力指标全部吻合 |

逐视频大小与完整 SHA-256 不在本 Markdown 重复展开，以 `manifests/acquired_video_files_v11.json` 为机器可读权威记录。

## 标签与处理操作

已完成官方元数据核验、标注结构检查、原视频下载/哈希、外测清单冻结、冻结模型推理、质量证据计算和可控退化实验。AVA 行为行结构为 `video_id,timestamp,x1,y1,x2,y2,action_id,entity_id`；同一个框可有姿态与反刍两个原子标签。片段采用虚拟窗口：清单保存不可变源视频路径/SHA-256、4秒时间窗和归一化裁剪框，解码时才提取16帧，不复制 MP4。

模型预测不得用于替代人工原标签。语义不能唯一对齐的样本写入 `excluded_samples.csv`。

人工审计仅确认主体/裁剪可见性和卧/站姿合理性。饮水与反刍属于时序动作，单张联系表不能独立确认；本轮保留官方时序标注，不依据模型或静态帧重标。部分远景、遮挡和窄裁剪作为真实域偏移限制保留，不在查看结果前筛除。

## 排除与未使用记录

- CattleEyeView：本轮不使用；其主要任务和当前行为标签不匹配，且数据条款需在申请时确认。
- 零散视频网站内容：本轮不作为主数据，避免版权、链接失效和标签不可审计问题。

## 计划变更

| 时间 | 原假设 | 观察事实 | 修正 | 对实验协议的影响 |
|---|---|---|---|---|
| 2026-08-23 | 可先实现解析器再核验远端文件 | 未取得真实文件结构前实现解析器会引入猜测 | 把官方元数据/许可门槛提前到解析器之前 | 无；5 GiB、冻结外测和标签边界不变 |
| 2026-08-23 | 全量测试可直接在中文项目路径运行 | PyTorch 2.0 原生文件 I/O 和 Windows PowerShell 5 对部分中文临时路径不兼容 | 仅全量验证使用此前获批的临时 ASCII 工作树，验证后删除 | 无；实现、数据和实验输出仍在项目内 |
| 2026-08-23 | CBVD-5 version 8 含 `video_cut` | 官方当前版本为11；连续 MP4 位于 `videos/videos`，687个共3,480,105,107 B；全量数据11,642,084,084 B | 固定 version 11，只批准 `videos/videos`、`miniannotations` 和根 VIA CSV，共3,485,904,149 B | 无；仍低于5 GiB，外部测试协议不变 |
| 2026-08-23 | 可从现有 CVB 验证材料训练视频质量门 | 项目内只有2,897条验证 logits 缓存，没有对应验证视频或质量特征 | 保留学习型门实现；本轮在读取 CBVD-5 指标前冻结绝对质量规则，标记为 `predeclared_heuristic` | 不使用外部标签拟合；质量拒识结论降级为探索性，不声称学习型提升 |
| 2026-08-23 | OpenCV 可直接把审计图写入项目中文路径 | Windows 下 `cv2.imwrite` 对该 Unicode 路径失败，而内存编码与 Python 文件写入正常 | 审计工具改为 `cv2.imencode` 后由 `Path.write_bytes` 落盘，并增加 Unicode 路径测试 | 不改变样本、标签或指标；仅修复可复现审计产物写入 |
| 2026-08-24 | strict 与 extended 压力子集可完全物理配对 | 两层按各自类别/源组确定性抽样后共有200个逻辑样本、173个物理片段，跨层只部分重合 | 只比较同一映射层内部的固定退化曲线，不声称跨层配对 | 不改变冻结样本；收紧论文和答辩的比较边界 |
| 2026-08-24 | 域内温度校准和简单拒识可能缓解外域错误 | strict 校准 Macro-F1 仅0.0048，固定拒识降至60.25%覆盖率后仍无正确接受样本；质量启发式无实质风险改善 | 将本阶段结论写为可审计的跨域失效证据，并按预设门控只建议新建少样本适配计划 | 不在外测集上调温度、阈值或质量规则；VLM/热成像仍保留在计划最后 |

## 复现命令

以下命令均从项目实现工作树根目录运行：

```powershell
F:\deepl\anaconda1\envs\pytorch\python.exe -X utf8 -m scripts.acquire_cbvd5_videos --project-root . --storage-root data/external/cbvd5 --workers 4
F:\deepl\anaconda1\envs\pytorch\python.exe -X utf8 -m scripts.prepare_external_behavior_data prepare --dataset cbvd5 --tier strict --max-per-class 100 --clip-seconds 4 --seed 20260823
F:\deepl\anaconda1\envs\pytorch\python.exe -X utf8 -m scripts.prepare_external_behavior_data prepare --dataset cbvd5 --tier extended --max-per-class 100 --clip-seconds 4 --seed 20260823
F:\deepl\anaconda1\envs\pytorch\python.exe -X utf8 -m scripts.create_cbvd5_audit_sheets --manifest data/external/cbvd5/manifests/evaluation_clips_extended.csv --output outputs/cross_domain/cvb_to_cbvd5/audit --per-class 10
F:\deepl\anaconda1\envs\pytorch\python.exe -X utf8 -m scripts.run_cross_domain_behavior_experiment --manifest data/external/cbvd5/manifests/evaluation_clips_strict.csv --manifest data/external/cbvd5/manifests/evaluation_clips_extended.csv --output outputs/cross_domain/cvb_to_cbvd5 --checkpoint models/behavior/cvb_x3d_v2_best.pt --calibration models/behavior/cvb_x3d_v2_calibration.json --project-root . --device cuda --batch-size 4 --stress-per-class 20 --stress-levels 0,1,2,3 --seed 20260823 --resume
```

冻结检查点 SHA-256 为 `731c6ed39dcf002915e888c829e1f86727f815331a2b3c21d06a17d40d62a08e`；strict、extended 和合并清单 SHA-256 分别为 `4d8e5c18...f89a62`、`15a05f1d...19b001`、`48384dcc...20320`。输出目录内 `metrics.json`、`predictions.csv` 和 `stress_metrics.csv` SHA-256 分别为 `9ce51921...b489a48`、`daf69850...3dd88c`、`682d30a8...69db4`。逐样本概率缓存、视频和审计图仍按 `.gitignore` 留在本机；最终提交只保留可审计的紧凑摘要与图表。

# 公开牛只视频数据与操作记录

## 记录目的

本文件回答三个问题：项目引用了什么数据集、文件存放在哪里、对数据进行了哪些操作。它与 `data/external/registry.json`、各数据集 `manifests/` 下的机器可读清单共同构成数据溯源证据。

当前状态：`metadata_verified`。截至 2026-08-23，本轮已下载三份小型官方标注/标签文件用于确认解析结构，尚未下载外部视频，也尚未生成外部实验结果。登记候选不等于已经用于模型评测。

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
| CBVD-5 | Scientific Reports 论文与 Kaggle version 11 | Kaggle 官方页：CC0 Public Domain | 首选外部测试域 | 已核验元数据与标注结构；视频尚未下载 |
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

实际下载后，每个压缩包、标注文件和最终使用视频都必须在此追加记录，不覆盖历史行。

## 标签与处理操作

已完成官方元数据核验和标注结构检查。AVA 行为行结构为 `video_id,timestamp,x1,y1,x2,y2,action_id,entity_id`；同一个框可有姿态与反刍两个原子标签。计划中的后续操作为：按文件下载连续 MP4、SHA-256、文件盘点、标注解析、严格/扩展标签映射、按原视频/摄像机/时间段分组、单牛片段生成、质量计算、冻结模型推理和可控退化实验。

模型预测不得用于替代人工原标签。语义不能唯一对齐的样本写入 `excluded_samples.csv`。

## 排除与未使用记录

- CattleEyeView：本轮不使用；其主要任务和当前行为标签不匹配，且数据条款需在申请时确认。
- 零散视频网站内容：本轮不作为主数据，避免版权、链接失效和标签不可审计问题。

## 计划变更

| 时间 | 原假设 | 观察事实 | 修正 | 对实验协议的影响 |
|---|---|---|---|---|
| 2026-08-23 | 可先实现解析器再核验远端文件 | 未取得真实文件结构前实现解析器会引入猜测 | 把官方元数据/许可门槛提前到解析器之前 | 无；5 GiB、冻结外测和标签边界不变 |
| 2026-08-23 | 全量测试可直接在中文项目路径运行 | PyTorch 2.0 原生文件 I/O 和 Windows PowerShell 5 对部分中文临时路径不兼容 | 仅全量验证使用此前获批的临时 ASCII 工作树，验证后删除 | 无；实现、数据和实验输出仍在项目内 |
| 2026-08-23 | CBVD-5 version 8 含 `video_cut` | 官方当前版本为11；连续 MP4 位于 `videos/videos`，687个共3,480,105,107 B；全量数据11,642,084,084 B | 固定 version 11，只批准 `videos/videos`、`miniannotations` 和根 VIA CSV，共3,485,904,149 B | 无；仍低于5 GiB，外部测试协议不变 |

## 复现命令

尚未产生可运行的外部实验命令。对应 CLI 实现并验证后，将在本节写入实际命令、检查点哈希、清单哈希和输出目录。

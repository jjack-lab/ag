# WAID4500 YOLO11s 可复现训练资产整合设计

日期：2026-09-29  
状态：已由用户确认

## 1. 背景与目标

当前项目运行时使用的目标检测模型为
`models/detection/yolo11s-waid.pt`。该文件与原训练工程
`E:\大创\WAID_YOLO11\runs\waid4500_v1_yolo11s_img960_e120\weights\best.pt`
的 SHA-256 一致：

`46D734CBA7553F31E89E739156F50E9A675B176F798C70159838497531771A64`

本设计将训练图片、数据划分依据、训练配置、训练过程日志、结果图表和模型权重整合进
`F:\new大创`，使获得项目目录的研究者能够：

1. 验证当前交付模型确实来自已归档训练；
2. 直接使用冻结的 WAID4500 数据集重新训练；
3. 从原始 WAID 数据和冻结清单重建完全相同的数据划分；
4. 通过统一脚本检查文件完整性、运行冒烟训练和启动完整训练；
5. 在不把第三方数据和大型运行产物提交到 Git 的情况下保存完整本地复现现场。

本阶段只处理当前生产链路使用的 WAID4500 YOLO11s 目标检测模型。行为识别数据和
CBVD4 跨域实验留给后续阶段。

## 2. 已确认的现状

- 原始 WAID 数据位于 `E:\大创\WAID-main\WAID`，约 1.63 GB。
- 冻结训练集位于 `E:\大创\WAID_YOLO11\waid4500_v1`，包含 4500 张训练图、
  200 张验证图和 20 张测试图，约 638 MB。
- 原训练运行目录约 45 MB，训练日志约 23 MB。
- 训练参数为 YOLO11s、输入尺寸 960、120 epochs、batch 4、workers 0、seed 42、
  cosine learning rate。
- `waid4500_v1/reports/dataset_manifest.csv` 保存了每个输出样本对应的原始图片、
  标签、类别、来源划分和分组信息。
- 现有 `prepare_waid1000.py` 的配额固定为 1000 张训练图，不能直接重建
  WAID4500。直接把该脚本描述成 WAID4500 生成程序是不正确的。
- WAID 本地资料未发现独立许可证文件，因此原始数据和派生图片不进入 Git；公开分发前
  仍需向数据集作者确认许可。

## 3. 方案比较与选择

### 方案 A：只复制冻结训练集

复制 WAID4500 和运行结果，能够立即训练，但无法证明或重建数据选择过程。

### 方案 B：原始数据、冻结训练集与清单重建并存

同时保留原始 WAID、WAID4500 快照、冻结清单、重建脚本和训练产物。日常训练直接使用
快照，需要审计时从原始数据按清单重建。这是本项目采用的方案。

### 方案 C：整体复制旧训练工程

能保存更多历史实验，但会混入 WAID1000、WAID2000、腐蚀实验和论文探索代码，路径仍然
写死在 E 盘，难以区分生产基线与废弃实验，因此不采用。

## 4. 目录结构与版本控制边界

```text
F:\new大创
├─ data\waid\raw\
│  └─ ...                         # 原始 WAID，大文件，不进入 Git
├─ data\waid\waid4500_v1\
│  └─ images/ labels/ splits/     # 冻结训练集，不进入 Git
├─ outputs\training\waid4500_yolo11s\
│  ├─ run\                       # results.csv、图表、best.pt、last.pt
│  └─ logs\                      # 原始 stdout/stderr/supervisor 日志
├─ reproducibility\waid4500\
│  ├─ dataset_manifest.csv        # 冻结样本选择，进入 Git
│  ├─ class_statistics.csv        # 数据统计，进入 Git
│  ├─ generation_summary.json     # 划分摘要，进入 Git
│  ├─ training_config.yaml        # 可移植训练配置，进入 Git
│  ├─ run_summary.json            # 最佳 epoch 和指标摘要，进入 Git
│  ├─ checksums.sha256            # 关键文件校验值，进入 Git
│  └─ environment.json            # 软件/硬件环境，进入 Git
└─ scripts\reproducibility\
   ├─ import_waid_assets.py
   ├─ rebuild_waid4500.py
   ├─ train_waid_yolo11s.py
   ├─ verify_waid_reproduction.py
   └─ run_waid_reproduction.ps1
```

`.gitignore` 只忽略明确的大文件目录，不忽略
`reproducibility/waid4500` 中的清单、配置和摘要。模型大文件继续遵守仓库现有模型治理规则，
不得通过本次工作手工替换 `models/detection/yolo11s-waid.pt`。

## 5. 数据导入与重建

### 5.1 本地资产导入

`import_waid_assets.py` 接收显式的源目录参数，不把 `E:\大创` 写死为唯一位置。导入时：

1. 校验源目录结构、文件数量和必要报告；
2. 复制原始数据、冻结训练集、训练运行目录和日志；
3. 使用临时目录完成复制，校验成功后再发布到目标目录；
4. 目标已存在时默认拒绝覆盖，只有显式参数才允许更新；
5. 生成本机资产状态报告，但不把绝对源路径作为运行依赖。

### 5.2 精确重建 WAID4500

`rebuild_waid4500.py` 以版本化的 `dataset_manifest.csv` 为唯一选择依据，而不是重新随机
抽样。它根据清单中的 `source_split` 和文件名，在本地 `data/waid/raw` 中定位图片和标签，
并重建 train/valid/test 目录与 split 文件。

重建程序必须检查：

- 图片和标签一一对应；
- 输出分别为 4500、200、20 张；
- 类别编号仅为 0–5；
- 标签符合 YOLO 五列格式且归一化坐标有效；
- 分组在 train、valid、test 之间互斥；
- 生成后的相对文件集合与冻结清单完全一致；
- 不信任清单中的绝对旧路径，所有源文件必须解析在用户指定的原始数据根目录内。

## 6. 训练入口

`train_waid_yolo11s.py` 使用项目相对路径生成临时 Ultralytics 数据配置，避免
`data.yaml` 中的 E 盘绝对路径。默认参数与原始运行保持一致：

- 模型：YOLO11s 预训练权重；
- 数据：WAID4500；
- `imgsz=960`；
- `epochs=120`；
- `batch=4`；
- `workers=0`；
- `seed=42`；
- `cos_lr=True`；
- `device=auto`，允许命令行覆盖；
- 支持从 `last.pt` 断点续训；
- 新训练输出与归档训练结果分开，禁止覆盖原始归档。

脚本提供三种使用层级：

1. `--check-only`：只检查环境、数据和配置；
2. `--smoke`：使用少量样本和 1 epoch 验证训练链路；
3. 默认完整训练：按照冻结参数训练 120 epochs。

## 7. 结果归档与验证标准

训练过程归档包括 `results.csv`、训练/验证曲线、混淆矩阵、标签统计、`args.yaml`、
`best.pt`、`last.pt` 和监督器日志。Git 只保存从这些文件提取出的轻量摘要与校验值。

`verify_waid_reproduction.py` 分为四层：

1. **资产层**：路径、数量、标签格式和清单一致；
2. **来源层**：交付模型与归档 `best.pt` 的 SHA-256 一致；
3. **运行层**：训练依赖可导入、CUDA/CPU 设备可识别、YOLO 可加载数据；
4. **结果层**：结果表字段完整、最佳 epoch 可重算、指标达到记录的合理范围。

数据集和已归档权重要求哈希严格一致。重新训练受 GPU、CUDA、cuDNN 和 Ultralytics 版本
影响，不承诺产生逐字节相同的权重；其复现目标是相同数据、参数、随机种子和合理误差范围
内的检测指标。

## 8. 测试策略

实现遵循测试先行：

- 单元测试覆盖清单解析、路径越界拒绝、标签验证、数量校验、配置生成和结果摘要；
- 使用临时微型数据集测试导入与重建，不依赖 2 GB 实际数据；
- 命令行测试覆盖 `--help`、`--check-only`、缺失数据和目标已存在等场景；
- 在真实资产复制完成后执行完整校验；
- 只运行 1 epoch 冒烟训练验证端到端链路，不在普通测试中启动 120 epoch 完整训练；
- 最终还需运行仓库 Python 测试、前端测试和前端构建，确保未破坏现有交付链路。

## 9. 文档与使用体验

新增一份面向复现者的中文说明，按以下顺序提供命令：

1. 安装/检查依赖；
2. 获取或导入 WAID 数据；
3. 校验本地资产；
4. 可选地从原始 WAID 重建 WAID4500；
5. 运行 1 epoch 冒烟训练；
6. 启动或恢复完整训练；
7. 验证训练结果；
8. 使用已有 `best.pt` 启动星牧智控项目。

同时更新主 README、第三方数据说明和 `HANDOFF.md`，明确哪些内容随 Git 分发、哪些内容
只保存在本地，以及公开发布前的数据授权责任。

## 10. 完成条件

本阶段仅在满足以下条件后声明完成：

- 所有指定本地大文件已复制到新目录且数量/关键哈希验证通过；
- 从原始 WAID 按冻结清单重建出的文件集合与 WAID4500 一致；
- 当前交付模型和归档 `best.pt` 哈希一致；
- `--check-only` 与 1 epoch 冒烟训练成功；
- 新增单元测试、现有 Python 测试、前端测试和构建通过，或对既存且无关的失败给出证据；
- 文档中的命令在不依赖 E 盘固定路径的情况下可执行；
- `HANDOFF.md` 已记录资产位置、验证结果和下一步。

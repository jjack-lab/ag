# WAID4500 YOLO11s 训练复现指南

本指南对应星牧智控当前目标检测模型 `models/detection/yolo11s-waid.pt`。复现资产按“代码与证据进入 Git、第三方图片与大型训练产物仅保存在本机”的边界组织。

## 复现边界

整合数据和训练结果不会自动提高识别率。本次工作的作用是固定基线、证明模型来源、复查数据划分并让后续训练可重复。不同 GPU、CUDA、cuDNN 或 Ultralytics 版本不保证重新训练得到逐字节相同的权重；数据清单和已归档权重则要求 SHA-256 严格一致。

WAID 本地副本和项目资料未发现独立许可证。当前数据只按大学科研内部用途保存，不随 Git 仓库或公开交付压缩包分发；公开再分发前须向数据集作者确认授权。

## 本地目录

```text
data/external/waid/raw/                    原始 WAID：28,733 文件，1,630,319,326 字节
data/external/waid/derived/waid4500_v1/   冻结数据集：9,450 文件，638,149,826 字节
data/external/waid/cache/yolo11s.pt        初始 YOLO11s 预训练权重
outputs/training/waid4500_yolo11s/run/     原训练产物：24 文件，45,270,542 字节
outputs/training/waid4500_yolo11s/logs/    原训练日志：16 文件，22,644,001 字节
reproducibility/waid4500/                  Git 跟踪的清单、配置、摘要和哈希
```

## 1. 选择 Python

```powershell
Set-Location -LiteralPath 'F:\new大创'
$env:AGRINEBULA_PYTHON = 'F:\deepl\anaconda1\envs\pytorch\python.exe'
```

已记录环境为 Python 3.8.20、PyTorch 2.0.0、Ultralytics 8.4.22、CUDA 11.8、RTX 4060 Laptop GPU。

## 2. 首次导入本地资产

当前 F 盘项目已经完成导入。迁移到另一份项目目录时运行：

```powershell
& $env:AGRINEBULA_PYTHON scripts/reproducibility/import_waid_assets.py `
  --source-raw 'E:\大创\WAID-main\WAID' `
  --source-training-root 'E:\大创\WAID_YOLO11' `
  --project-root 'F:\new大创'
```

目标存在时默认拒绝覆盖。只有明确要重新替换本地副本时才增加 `--replace`。

导入是**整批事务**：五类资产先全部复制到暂存目录并逐一校验，再统一发布；任一环节失败会回滚已发布的部分并恢复被替换的旧资产，不会留下半新半旧的项目状态。导入完成后，冻结数据集的 `data.yaml` 会被重写为本机的可移植路径（源机绝对路径如 `E:\大创\...` 不会被带过来）。

## 3. 验证完整复现证据

```powershell
& $env:AGRINEBULA_PYTHON scripts/reproducibility/verify_waid_reproduction.py `
  --project-root 'F:\new大创' `
  --output-json 'F:\new大创\outputs\training\waid4500_yolo11s\verification.json'
```

顶层 `status` 为 `passed` 时，表示以下六层**全部**通过：

1. 4,500/200/20 的划分资产与关键 SHA-256；
2. 逐样本结构校验：清单全部 4,720 条样本的图片/标签存在、标签内容与清单元数据（类别、目标数）一致；
3. 冻结划分校验：`splits/{train,valid,test}.txt` 的成员集合与清单划分完全一致（4,500/200/20）；
4. 逐样本内容哈希：`reproducibility/waid4500/dataset_samples.sha256` 中 4,720 条图片+标签内容摘要逐条重算一致；
5. 归档权重与交付模型来源（`best.pt` 与 `models/detection/yolo11s-waid.pt` 同哈希）；
6. 训练环境与最佳指标摘要。

当前实测（2026-10-02，真实资产 `--project-root F:\new大创`）：`status=passed`，样本 4,720/4,720、划分 4,500/200/20、内容哈希 4,720/4,720，全部一致。

需要重新记录内容哈希（例如换了数据机或重导入后）：

```powershell
& $env:AGRINEBULA_PYTHON scripts/reproducibility/write_waid_sample_hashes.py `
  --project-root 'F:\new大创'
```

该命令按清单顺序写出 `reproducibility/waid4500/dataset_samples.sha256`（列为 `output_image,image_sha256,label_sha256,content_sha256`），把结果提交进 Git 即可成为可复核证据。

## 4. 从原始 WAID 重建冻结划分

不要覆盖现有冻结数据集，使用新输出目录：

```powershell
& $env:AGRINEBULA_PYTHON scripts/reproducibility/rebuild_waid4500.py `
  --raw-root 'F:\new大创\data\external\waid\raw' `
  --manifest 'F:\new大创\reproducibility\waid4500\dataset_manifest.csv' `
  --output 'F:\new大创\data\external\waid\derived\waid4500_rebuilt'
```

当前验证结果：排除 3 个 Ultralytics `*.cache` 运行缓存后，原冻结目录与重建目录的 9,443 个图片、标签和 split 文件集合完全相同，哈希不一致数为 0。

## 5. 训练前检查

```powershell
& $env:AGRINEBULA_PYTHON scripts/reproducibility/train_waid_yolo11s.py `
  --project-root 'F:\new大创' `
  --check-only
```

该命令不训练，只检查模型、4,720 条清单记录、实际图片/标签、依赖、设备和输出目录。

## 6. 一轮冒烟训练

```powershell
& $env:AGRINEBULA_PYTHON scripts/reproducibility/train_waid_yolo11s.py `
  --project-root 'F:\new大创' `
  --smoke `
  --device 0
```

冒烟模式使用 1 epoch、2% 训练数据，输出到 `outputs/training/waid4500_yolo11s/reproduced/smoke_e1`，不会覆盖归档运行。

## 7. 完整训练与续训

完整协议：YOLO11s、`imgsz=960`、120 epochs、batch 4、workers 0、seed 42、确定性模式、cosine learning rate。

```powershell
& $env:AGRINEBULA_PYTHON scripts/reproducibility/train_waid_yolo11s.py `
  --project-root 'F:\new大创' `
  --device 0
```

断点续训：

```powershell
& $env:AGRINEBULA_PYTHON scripts/reproducibility/train_waid_yolo11s.py `
  --project-root 'F:\new大创' `
  --resume 'F:\new大创\outputs\training\waid4500_yolo11s\reproduced\full_e120_seed42\weights\last.pt' `
  --device 0
```

续训前会校验检查点里记录的输出根：Ultralytics 在续训时用检查点自身的参数覆盖全部参数（`BaseTrainer.check_resume`），因此输出位置来自检查点而不是 `--project-root`。归档运行的检查点记录的是旧的 `E:\大创\WAID_YOLO11\runs`，直接续训会写到那里；现在这种情况会被拒绝并报 `resume checkpoint output root is outside the portable project`。**只能续训由本工作流产生、且输出根位于 `outputs/training/waid4500_yolo11s/reproduced` 之下的检查点。**

统一入口：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/reproducibility/run_waid_reproduction.ps1 `
  -Mode verify `
  -Python $env:AGRINEBULA_PYTHON `
  -ProjectRoot 'F:\new大创'
```

`Mode` 可选 `verify`、`rebuild`、`smoke`、`train`、`resume`。

## 已归档基线

- 最佳 epoch：89；
- Precision：0.94186；
- Recall：0.91602；
- mAP50：0.95385；
- mAP50-95：0.584；
- 初始 `yolo11s.pt`：`85a76fe86dd8afe384648546b56a7a78580c7cb7b404fc595f97969322d502d5`；
- 最佳/交付模型：`46d734cba7553f31e89e739156f50e9a675b176f798c70159838497531771a64`。

## 启动星牧智控

复现检查不会改变交付模型。正常启动仍使用：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_delivery.ps1
```

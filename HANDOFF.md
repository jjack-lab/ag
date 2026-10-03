# HANDOFF.md — 交接台账

> 谁在干活谁维护。任何 AI 接手第一步：读完本文件 → `git log --oneline -10` + `git status` + `git worktree list` 核对 → 跑测试 → 从「下一步」清单继续。规则见 `AGENTS.md`。

- 最后更新：2026-10-03（多 seed 矩阵已结清；WAID 复现加固已合并；申报材料与仓库整理入库；四项 P0 逐项推进：确认集协议+冻结工具已就绪待素材、论文统计实现中、WAID 改进预注册草案待你选档、推广门控经核实早已实现）

## 当前阶段目标

1. 保留已完成的 CBVD4 冻结三臂实验及负晋级结论，禁止依据当前 test 结果换候选或调参。
2. 完成多 seed validation 矩阵（两种初始化 × seeds 20260824/20260901/20260908），只在开发集 train/val 上进行。
3. WAID4500 目标检测基线完成可复现封装（清单、哈希、环境、训练入口、验证器），随后在冻结基线上开展预注册的精度改进实验。
4. 大创申报材料定稿并入库；主线 `integration` 保持测试绿色、随时可演示。

## 已完成

- 主线：Unicode 路径兼容系列修复与原子发布验证（至 `4d058a7`）。
- 实验分支 `codex/cross-domain-behavior`：CBVD4 两种初始化训练已完成；validation Macro-F1 为 Kinetics 0.839844、CVB-transfer 0.840723，仅按 validation 冻结选择 CVB-transfer。
- 一次性三臂 test 已完成（`test_read_count=1`）：冻结 CVB12 / Kinetics / CVB-transfer 的 Macro-F1 分别为 0.022472 / 0.878173 / 0.830761；逐源视频 2,000 次 bootstrap 与独立数值复算完成。
- 冻结候选因站立反刍 F1=0.588235 低于预设 0.60 门槛，`promoted=false`；未安装 CBVD4 模型、未运行上传视频演示。推广 CLI 已提交（`b7d30e1`）。
- 正式结果、数据操作台账和计划状态已发布（`6add827`）：`docs/experiments/2026-08-24-cbvd4-domain-adaptation-results.md`。
- 下一阶段多 seed validation 已预注册并启动：设计 `4ca0746`、计划
  `ba8ac6e`；development-only loader/CLI、六单元矩阵和聚合核心已提交
  （`bd5b06b`、`8779ab1`、`cd8c900`、`1589d5d`）。33 项聚焦测试
  通过，真实 preflight 与两种初始化 smoke 均通过。
- validation-only 逐样本推理和六单元汇总工具已提交（`38a4517`），输出
  `validation_predictions.csv`、`validation_metrics.csv`、`aggregate.json`
  和 `report.md`，保留 checkpoint/validation manifest 哈希且不作晋级决定；
  之后通过三轮失败关闭审查加固（`30ed5f8`、`7cba9f5`、`e7723b3`）：
  六单元先整体校验 checkpoint/矩阵绑定后才推理，正式 test 路径在任何读取前
  拒绝，新训练仅允许 train/val 哈希。最终 60 项聚焦测试通过，规格与质量
  复审均无剩余 Critical/Important；计划状态提交为 `ed91bbb`。
- 多 seed 矩阵第 1 条新增臂 Kinetics seed 20260901 已完成：2026-09-23 20:57 写出
  `validation_metrics.json`/`history.csv`/`best.pt`（epoch 0--18 共 19 轮），
  validation Macro-F1=0.8530158904，`best.pt` SHA-256=
  `ecc4ccd176ef172c2ce9061ed242abce210d05d659627512b6b613a723c36654`，
  `test_metrics_read=false`；恢复日志
  `outputs/cbvd4/paper_20260922/logs/kinetics_seed_20260901_resume_20260923.stdout.log`。
- 多 seed 矩阵第 2 条新增臂 CVB-transfer seed 20260901 已完成：2026-09-30 18:37:50 正常
  收尾（`resume_exit=0`，**epoch 11 早停**，patience=6；最佳在 epoch 5），写出
  `validation_metrics.json`/`metrics.json`/`history.csv`/`best.pt` 等完整产物。
  validation Macro-F1=0.8325412642、accuracy=0.9146341463，最佳 `best.pt` SHA-256=
  `3f28cca2d984c1133d860afbae7e0d20de321cae0669c49b241a8a6a8ccb9857`，
  `test_metrics_read=false`，清单哈希与冻结矩阵一致（train `43dda22a…` / val `8a8a7d08…`）。
  逐类 F1：grazing 0.9292 / drinking 0.8167 / ruminating-standing 0.6012 /
  ruminating-lying 0.9831（站立反刍仍是最弱类，混淆主要在它与 grazing 之间）。日志
  `outputs/cbvd4/paper_20260922/logs/cvb_transfer_seed_20260901_resume_20260930.stdout.log`。
  参照：两条 20260824 旧臂为 Kinetics 0.8398443 / CVB-transfer 0.8407228，即本 seed 下
  Kinetics 升、CVB-transfer 降——只是稳定性观察，**六格齐全并跑完汇总前不作任何选择**。
- 多 seed 矩阵第 3 条新增臂 Kinetics seed 20260908 已完成：2026-10-01 22:34:22 正常收尾
  （`resume2_exit=0`，**epoch 13 早停**，patience=6；epoch 13 的 0.8424501 差一点点没刷新
  epoch 7 的最佳），共 14 轮。validation Macro-F1=0.8436268208、accuracy=0.9126016260，
  最佳 `best.pt` SHA-256=`5802f043d5a177b7cd1a3c90106254a22e176817d8918f86fdf1e8af1de4318d`
  （与 `validation_metrics.json` 记录一致，已独立复算），`test_metrics_read=false`，
  清单哈希与冻结矩阵一致。逐类 F1：grazing 0.9139 / drinking 0.8467 /
  ruminating-standing 0.6178 / ruminating-lying 0.9961。日志
  `outputs/cbvd4/paper_20260922/logs/kinetics_seed_20260908_resume2_20261001.stdout.log`。
  至此 Kinetics 臂三个 seed 齐全：0.8398443 / 0.8530159 / 0.8436268（均值 0.8455，
  样本标准差 0.0068）；CVB-transfer 臂还差 seed 20260908。
- 多 seed 矩阵第 4 条（也是最后一条）新增臂 **CVB-transfer seed 20260908 已完成**：
  2026-10-03 13:58:09 正常收尾（`resume_exit=0`，**epoch 10 早停**，共 11 轮；中途按用户
  要求在 epoch 8 暂停、次日 12:25:27 `--resume` 恢复）。validation Macro-F1=
  **0.8266304027953745**（最佳 epoch 4）、accuracy=0.8943089431，最佳 `best.pt` SHA-256=
  `0d3b19161a482fd3021ee843e75623b979a5f0b99d0180f9468b9d9aa604380e`
  （与 `validation_metrics.json` 一致），`test_metrics_read=false`，清单哈希与冻结矩阵一致。
  逐类 F1：grazing 0.8886 / drinking 0.8571 / **ruminating-standing 0.5607** /
  ruminating-lying 1.0000。日志
  `outputs/cbvd4/paper_20260922/logs/cvb_transfer_seed_20260908_resume_20261002.stdout.log`。
  **至此六格齐全**（两臂 × 三 seed，全部 `test_metrics_read=false`）：

  | 初始化 | 20260824 | 20260901 | 20260908 | 均值 | 样本标准差 |
  | --- | --- | --- | --- | --- | --- |
  | Kinetics | 0.8398443 | 0.8530159 | 0.8436268 | 0.84550 | 0.0068 |
  | CVB-transfer | 0.8407228 | 0.8325413 | 0.8266304 | 0.83330 | 0.0071 |

  即两个初始化的 seed 波动同量级（≈0.007），Kinetics 三个 seed 一致高于 CVB-transfer
  （平均高约 0.0122）。**这仍是 validation 稳定性观察；按预注册，做选择前必须跑完
  计划 Task 7 汇总，且不得读取正式 test。**
- WAID4500 YOLO11s 可复现包已入库（分支 `codex/waid-reproducibility`，现共 10 个提交，
  即 Codex 的 8 个加本次的 `f18bd4d` 修复与 `842b1bd` 交接）：
  manifest 合约、原子重建、本地资产导入、可移植训练入口、证据验证器、
  一键 PowerShell 工作流，以及中文指南 `docs/WAID4500_REPRODUCIBILITY.md`。
  `reproducibility/waid4500/` 跟踪 4,720 条清单（train 4500 / valid 200 / test 20）、
  类别统计、环境、运行摘要、训练配置与 `checksums.sha256`。
- WAID 真实资产验证（`--project-root F:\new大创`）：check-only `status=ready`
  （torch 2.0.0、ultralytics 8.4.22、device 0，`yolo11s.pt` SHA-256=
  `85a76fe86dd8afe384648546b56a7a78580c7cb7b404fc595f97969322d502d5`）；
  verifier `status=passed`，归档 `run/weights/best.pt` 与交付模型
  `models/detection/yolo11s-waid.pt` 同为
  `46d734cba7553f31e89e739156f50e9a675b176f798c70159838497531771a64`，
  选中 epoch 89（P 0.94186 / R 0.91602 / mAP50 0.95385 / mAP50-95 0.584）。
- WAID 真实 1 epoch 冒烟训练（2% 训练集 90 张 + 200 张验证）通过：输出
  `outputs/training/waid4500_yolo11s/reproduced/smoke_e1`，
  `best.pt`/`last.pt` 为 strip 后的 19,266,131 字节检查点，退出码 0。
- 修复 `f18bd4d`：非 ASCII 路径下 `torch.save` 会让训练在 `final_eval` 抛
  `RuntimeError: Parent directory ... does not exist`（详见「决策与坑」）。
- 测试证据：`tests/test_waid_repro.py` 45 项通过；完整 `pytest` 588 通过 /
  4 跳过 / 2 失败——两项失败在 `integration` 上同样复现
  （`delivery_tests/test_external_behavior_cli.py` 把临时输出放在 `project_root`
  外被安全校验拒绝），与本次改动无关；前端 `npm test` 16 项通过、
  `npm run build` 成功（2178 modules）。
- 完整评估：`docs/2026-08-24-new-dachuang-complete-project-assessment.md`；
  路线图（P0/P1/P2 与执行顺序）：worktree 内 `docs/2026-08-24-project-status-and-roadmap.md`。

## 进行中

- WAID 复现加固**已完成并合并回 `integration`**（分支 `codex/waid-repro-hardening`，
  worktree `.worktrees/waid-repro-hardening`，基于 `integration` 416b90e；用户 2026-10-02
  审阅后合并）：
  `2ea7dc6` 导入的冻结数据集 `data.yaml` 不再保留源机绝对根（原先写死
  `E:\大创\WAID_YOLO11\waid4500_v1`），并与 PowerShell `rebuild` 默认输出改为独立目录
  `derived\waid4500_rebuilt`（原先默认指向冻结目录本身，该模式必然失败）；
  `733cbbb` 续训前校验检查点内记录的输出根，越界即 fail-closed（Ultralytics
  `trainer.check_resume` 会用检查点参数覆盖全部参数，归档检查点记录的是
  `E:\大创\WAID_YOLO11\runs`，否则会静默写到旧 E 盘）——已用真实检查点验证：归档
  checkpoint 被拒、`reproduced` checkpoint 被接受；
  `7080174` 五类资产改为**整批事务**：先全部暂存校验、再一起发布，任一环节失败则回滚
  已发布组件并恢复被替换的旧资产；
  `f6e6df7` 证据强度补齐：`verify_reproduction()` 现在逐条校验全部 4,720 个样本
  （存在性 + 标签内容与清单元数据一致）、冻结划分成员集合（`splits/*.txt` 对
  4,500/200/20），并重算 `reproducibility/waid4500/dataset_samples.sha256` 里 4,720 条
  逐样本内容摘要（新增生成器 `scripts/reproducibility/write_waid_sample_hashes.py`）。
  **真实端到端实测**（`--project-root F:\new大创`）：`status=passed`，样本 4,720/4,720、
  划分 4,500/200/20、内容哈希 4,720/4,720，六层全通过。
  测试：聚焦 58 passed；worktree 全量 **601 passed / 4 skipped / 2 项既有失败**（与
  `integration` 相同）。至此复核的 6 项 Important 全部处理完毕，可声明"完整复现证据
  全部通过"——但声明措辞仍需用户确认后再写进 README/指南之外的对外材料。
- WAID 独立复核结论为 WARN（Critical=0、Important=6）：聚焦测试、真实 check-only、
  当前哈希/血缘 verifier 和既有 smoke 产物均通过，但“完整可移植复现”的声明仍需加固。
  已确认：verifier 未完整验证 4,720 个样本及固定划分；缺少逐样本内容哈希；导入的
  `data.yaml` 仍指向旧 E 盘；Ultralytics 续训会恢复检查点内旧 `save_dir`；PowerShell
  `rebuild` 默认目标已存在；五类资产导入不是整批事务。本轮未修改生产代码，等待用户
  确认采用完整加固还是缩小声明范围。CVB 长训练仍在运行，本轮没有启动 WAID GPU 训练。
- `codex/waid-reproducibility` 已快进合并到 `integration`（`1a8d033`，集成后完整
  `pytest` 588 通过 / 4 跳过 / 2 项既有失败，verifier `status=passed`）。worktree 仍在
  `C:\Users\Mrda\.codex\worktrees\waid-reproducibility\`（Codex 应用托管，未擅自删除），
  分支也保留，需要时再 `git worktree remove` + `git branch -d`。
- WAID 大资产只在本机且被忽略：`data/external/waid/{raw,derived,cache}`、
  `outputs/training/waid4500_yolo11s/{run,logs}`；训练会在冻结数据集目录内新增
  Ultralytics `*.cache`（已被忽略，重建对比时排除，勿手工删除或提交）。
- 多 seed validation 矩阵：新一代 4 条臂已完成 3 条——Kinetics seed 20260901
  （0.8530158904）、CVB-transfer seed 20260901（0.8325412642）与 Kinetics seed 20260908
  （0.8436268208，14 轮、最佳 epoch 7）；详见「已完成」。**最后一格 CVB-transfer
  seed 20260908 已于 2026-10-02 14:44:46 启动**（PID 28468，用户 10-02 决定开跑，此前自
  10-01 起暂缓）。形态与隔离自检：`--source-checkpoint models/behavior/cvb_x3d_v2_best.pt`
  （哈希 `731c6ed3…`，与 seed_20260901 臂同一来源）、无 `--kinetics-checkpoint`、
  `--seed 20260908`；协议 `test_data_read=false`、`evaluation_scope=train_val_only`、
  清单哈希与冻结矩阵一致。日志 `outputs/cbvd4/paper_20260922/logs/cvb_transfer_seed_20260908.{stdout,stderr}.log`、
  PID 文件同名 `.pid`（均在 `.worktrees/cross-domain-behavior` 下），输出
  `outputs/cbvd4/paper_20260922/multiseed_validation/cvb_transfer_init/seed_20260908`。
  **该臂已于 2026-10-03 13:58:09 完成**（epoch 10 早停，共 11 轮，validation Macro-F1
  0.8266304028；中途 10-02 22:45 曾在 epoch 8 边界按用户要求暂停，10-03 12:25:27
  `--resume` 恢复）。逐轮 val_macro_f1：0.5183 / 0.5657 / 0.7873 / 0.7994 / **0.8266** /
  0.7573 / 0.8087 / 0.7510 / 0.7544 / 0.8017 / 0.8181；最佳之后连续 6 轮未刷新即早停。
  日志 `.../logs/cvb_transfer_seed_20260908_resume_20261002.stdout.log`（7262 字节最终摘要）。
  **六格矩阵已全部有 validation 结果**；**计划 Task 7 汇总已于 2026-10-03 14:49 完成**
  （14:08:23 启动，PID 17112，`--mode summarize --device cuda --batch-size 4 --workers 0`，
  日志 `outputs/cbvd4/paper_20260922/logs/multiseed_summarize_20261003.{stdout,stderr}.log`）。
  产物：`validation_metrics.csv`（6 行）、`aggregate.json`
  （39.6 KB，含每格 984 条逐样本预测路径与按源视频错误计数）、`report.md`，另有
  `analysis/<初始化>/seed_<seed>/validation_predictions.csv`。
  **结果**：Kinetics 均值 **0.845496**（样本标准差 0.006782）vs CVB-transfer **0.833625**
  （0.006623）；配对差值 cvb−kinetics = **+0.000878 / −0.020475 / −0.016016**（旧 seed 微正、
  两个新 seed 明显为负 → 符号反转）；`test_data_read=false`（`aggregate.json` 里唯一的
  "test" 字样就是这个布尔键），六格全部 validation-only。
  注意一处 0.001 量级差异：最后一格在训练内记录的 0.8266304028 与汇总统一重算的
  **0.8276105066** 不同（其余五格两者逐位一致）；汇总是对冻结 `best.pt` 的统一重评估，
  跨格比较应以 `validation_metrics.csv` 为准，训练内数字来自内存模型末轮评估。
  另已将结论写入跨域分支的 `docs/data/2026-08-23-public-cattle-video-data-record.md`
  （实验台账 + 假设修正表 + 复现命令），提交 `1606b71`。
  历史启动日志与暂停监视器日志保留在 `.worktrees/cross-domain-behavior` 的
  `outputs/cbvd4/paper_20260922/logs/` 下；识别进程靠完整命令行 + 输出目录，不能只信 PID。
- 运行方式经验（务必遵守）：本环境会静默回收无人托管的进程——2026-09-29 的会话后台任务在
  跑完 epoch 2 后被回收；2026-09-30 用 `Start-Process` 脱离式进程重试也在约 3 分钟后被回收；
  最终仍用**会话托管的后台任务**恢复成功并正常跑完。所以长训练只能走会话托管后台任务，
  中途被回收就用同一命令加 `--resume` 续跑（每 epoch 落一次 checkpoint，已完成轮次不丢）。
  识别进程必须靠完整命令行 + 输出目录，不能只信 PID。
- 该臂产物与日志：输出
  `outputs/cbvd4/paper_20260922/multiseed_validation/cvb_transfer_init/seed_20260901`
  （`history.csv` 每 epoch 一行；`stdout.log` 只在结束时写出最终 JSON 摘要，中途为空正常）；
  日志在 `.worktrees/cross-domain-behavior` 的 `outputs/cbvd4/paper_20260922/logs/`
  （首次 `cvb_transfer_seed_20260901.*`、被回收的两次尝试 `..._resume_20260929.*`、
  最终成功的 `cvb_transfer_seed_20260901_resume_20260930.*`），另有同名 `.pid` 文件。
  **早停属正常收尾**（patience=6：本臂停在 epoch 11，上一臂停在 epoch 18），不要误判为崩溃。
- `codex/cross-domain-behavior` 仍有 3 个用户所有、未提交文档（roadmap、2026-09-12
  选择性数据可行性、2026-09-12 测试来源审计），接手方不得擅自覆盖或提交。
- 主线有未跟踪文件：评估报告、`星牧智控-项目计划书.docx`、`申报-项目概述.txt`、`scripts/make_plan_docx.py`。

## 下一步（P0，按序执行）

- [x] 合并 `codex/waid-reproducibility` 到 `integration`（2026-09-29 快进完成，
  `1a8d033`；合并后完整 `pytest` 588 通过 / 4 跳过 / 2 项既有失败，verifier
  `status=passed`，指南里的 verify/rebuild/train 命令现可在主线直接运行）。
- [x] WAID 复现加固已完成并合并（2026-10-02，合并提交 `992f64a`）：全量 4,720 样本与固定
  划分校验、逐样本内容哈希、portable `data.yaml`、续训越界 fail-closed、独立 rebuild 输出、
  整批导入事务。真实资产端到端 verifier `status=passed`（六层），此后可以声明"完整复现证据
  全部通过"。
- [x] 多 seed 矩阵四条新臂全部完成（2026-10-03 13:58 最后一格 CVB-transfer seed 20260908
  早停收尾，11 轮、0.8266304028）；六格齐全，全部 `test_metrics_read=false`，两臂 seed
  波动同量级（≈0.007）。当前**没有训练进程在跑**。
- [x] 四条新臂齐后执行计划 Task 7 汇总（2026-10-03 完成）：`validation_metrics.csv`、
  `aggregate.json`、`report.md` 已生成，`test_data_read=false`；Kinetics 均值 0.845496
  （样本标准差 0.006782）vs CVB-transfer 0.833625（0.006623），配对差值 +0.000878 /
  −0.020475 / −0.016016；结论已写入跨域分支数据记录（`1606b71`）。**多 seed 矩阵至此结清，
  且按预注册不作任何候选选择或晋级决定。**
- [x] 主线申报材料与仓库整理入库（2026-10-03）：`AGENTS.md`、额度监听工具
  （`scripts/watch_quota.py` + `启动额度监听.bat`）、申报材料（`docs/申报-项目概述.txt`、
  `docs/星牧智控-项目计划书.docx` + 生成脚本 `scripts/make_plan_docx.py`、完整评估文档）
  已提交（`ae0d828`、`f0f51f7`、`86c033c`）；`data/delivery-processes.json`（运行时 PID
  登记）与 5 个第三方/大文件（`AID.pdf`、`CoastCor-Net.py/.yaml`、`train.zip`、`代码.zip`）
  已加入 `.gitignore`（`360f210`、`4183efb`），**主线工作树现在完全干净**。
- [ ] 数据（**协议与工具已就绪，等素材**）：前瞻性独立确认集的暴露边界机制已实现并提交到
  跨域分支（`323bac3` 模块+CLI+7 项测试、`547cda2` 协议文档
  `docs/experiments/2026-10-03-prospective-confirmation-set-protocol.md`）：新视频必须逐条
  SHA-256 与开发登记表 `manifests/cbvd4/source_videos.csv`（397 条，哈希
  `a0aad746…`）比对，命中即 exit 1 拒绝；实测把真实已暴露的 `10.mp4` 放进候选目录被正确
  拒绝。**本地已确认没有可用的新视频**（CBVD-5 687 个 mp4 属开发语料，E 盘那批属既有项目
  数据），需用户提供新牧场视频才能冻结。
- [x] 论文统计（2026-10-03 完成）：跨域分支 `a89769d`（模块 1707 行 + CLI + 27 项测试）、
  `dc0f3e3`（结果文档 `docs/experiments/2026-10-03-cbvd4-validation-calibration-coverage.md`）。
  已独立核验：聚焦 **27 passed**；`calibration.csv` 的 macro-F1 与既有 `validation_metrics.csv`
  **逐位一致**；`report.md` 明示 test 永不读取、不作选择/晋级决定。关键结果：原始 softmax
  严重过度自信（pooled ECE 0.449 → 交叉拟合温度后 0.034 / cvb 0.442 → 0.052），AURC
  0.0174（kinetics）/ 0.0232（cvb），选择性准确率@0.7 覆盖 0.9840 / 0.9705；配对差值
  +0.000878 / −0.020475 / −0.016016，**三个区间均含 0** → 两臂无已确立差异。
  另修正一处此前说法：`delivery_tests/test_external_behavior_cli.py` 的 2 项失败只出现在
  WAID worktree 与主检出，**本 worktree 为 8/8 通过**；本 worktree 的预存失败是
  `test_cross_domain_behavior_reporting.py::test_committed_result_document_records_verified_
  complete_evidence`（断言文档中缺失的句子，与本批改动无关，子代理未改任何既有文件）。
- [ ] WAID：预注册**草案已写**（`docs/superpowers/specs/2026-10-03-waid-improvement-preregistration-design.md`，
  提交 `70fd90f`）：假设来自仓库自有证据（训练集 zebra 仅 289 图 vs sheep 1041 图），单变量
  规则 H1 类别过采样 / H2 imgsz 960→1280，只读 valid、test 本阶段不读。用户已选 **B 档
  （筛选→确认）**。**真实速度已实测**（2026-10-03 18:30，协议同筛选、仅 `epochs=2`，`probe_exit=0`）：
  epoch 2 = **237.7 s = 3.96 分钟/轮**（累计 time 243.2 → 480.9 s；探测配置与日志在忽略目录
  `outputs/training/waid4500_yolo11s/timing_probe_e2.yaml` 与 `…/logs/timing_probe_e2.*.log`，
  输出 `…/reproduced/timing_probe_e2/`，2 轮后 val mAP50-95=0.4977，基线 120 轮为 0.584）。
  由此回填预算：**筛选 40 轮 × 3 seeds × 3 臂 ≈ 23.8 h**，胜者 120 轮 × 3 seeds 确认 ≈ 23.8 h，
  **B 档完整 ≈ 48 h**（超出草案 20–30 h 的估计，已向用户披露并等待其确认是否按此开跑、
  或缩为 3 臂 × 1 seed 筛选 ≈ 7.9 h）。**批准前不启动正式训练。**
  开跑前还差一件事：H1（类别过采样）在 Ultralytics 8.x 检测训练中无原生支持，需先实现
  LVIS 风格重复因子清单（生成 `train_rf.txt`，运行期 `data.yaml` 指向它）+ TDD 测试；
  H2 仅需新增一份 `imgsz: 1280` 配置变体。
- [ ] 仅当预注册候选在新的确认集达到 Macro-F1 ≥ 0.70 且每类 F1 ≥ 0.60，才安装 CBVD4 模型并执行上传视频端到端演示。
  → **门控机制其实早已实现且为绿**（`cattle_health_app/behavior/cbvd4_evaluation.py`
  的 `PromotionDecision` 固定 `macro_f1_threshold=0.70`、`per_class_f1_threshold=0.60`；
  `scripts/promote_cbvd4_model.py` 仅当 `promotion.json` 的 `promoted=true` 才落盘交付模型；
  `delivery_tests/test_promote_cbvd4_model.py` + `test_cbvd4_evaluation.py` **13 passed**；
  已有一条真实的 `promoted=false` 拒绝记录）。**因此该项只等前两项产出合格候选**，无需再写代码。

## 决策与坑（不要再踩）

- Windows 多进程 DataLoader 会触发 `nvfuser_codegen.dll / WinError 1114`，正式训练必须 `workers=0`。
- 测试集读取有原子记录机制，重复读取会被拒绝；任何调参只允许用验证集。
- 当前冻结 test 中 59 个源视频有 37 个曾出现在历史 strict/extended 研发实验（745/1,032 样本）。这不是本次 train/test 泄漏，但不能声称为研发过程完全未暴露的独立确认集，也不能事后把剩余 22 个视频重组为“干净测试集”。
- Kinetics 臂在 test 上优于冻结候选，但不得在看到 test 后改选；当前结论必须保留为负晋级结果。
- 模型加载绑定 checkpoint 哈希 / 标签空间 / 类别顺序，不一致会拒绝加载；不要手工改 `models/` 目录。
- CBVD-5 零样本 Macro-F1 仅 0.0048，当前行为模型不能跨域直接部署，必须走 CBVD4 域适应路线。
- 当前 CVB 模型在不均衡验证集上 Macro-F1 只有 0.2189，汇报效果禁止只看 Accuracy。
- 仓库路径含中文，脚本必须显式按 UTF-8 处理路径与子进程输出（主线近期一组修复即为此，勿回退）。
- Windows + torch 2.0.0 下 `torch.save` 不能接受非 ASCII 路径：PyTorch 的 C++ 检查点
  写入器用 ANSI 代码页解析父目录，对 `F:\new大创\...` 一律抛
  `RuntimeError: Parent directory ... does not exist`（纯 ASCII 路径正常）。
  Ultralytics 自己的 `save_model` 用 `BytesIO` + `Path.write_bytes` 绕开了这个坑，
  但 `final_eval` → `strip_optimizer` 直接调 `torch.save`，会让训练在跑完所有 epoch
  之后的最后一步失败。WAID 训练现在用 `unicode_safe_torch_save()` 包住
  `YOLO.train()`；动这条链路前先看 `tests/test_waid_repro.py::WaidUnicodeCheckpointTest`。
- `mock.patch.dict(sys.modules, ...)` 会对整张模块表做快照并在退出时恢复，块内新导入的
  模块（例如训练运行时的 `torch`）会被一并清掉，之后再次 `import torch` 会报
  `'_has_torch_function' already has a docstring` / `_C is not defined`。测试里改用
  `installed_ultralytics()`，只替换 `ultralytics` 这一个键。

## 中断记录

- 2026-09-30：WAID 复核重新运行真实 check-only、verifier 和聚焦测试：
  `status=ready`、当前 verifier `status=passed`、45 项聚焦测试通过；前端 16 项通过且
  构建成功；全量 Python 588 通过 / 4 跳过 / 2 项既有失败。代码审查发现 0 个
  Critical、6 个 Important，并用真实路径和 Ultralytics 8.4.22 源码逐项复现或确认。
  当前停在设计选择前，尚未修改生产实现；下一步需用户确认“完整加固”或“缩小复现声明”。
- 2026-09-22：CBVD4 冻结实验与正式报告已收尾。实验分支 HEAD=`6add827`；无训练进程需要恢复。下一执行点是“开发集多 seed/站立反刍改进方案 + 新前瞻性确认数据”，不是重跑当前 test。实验 worktree 仅剩 3 个用户所有的未跟踪文档，保持原样。
- 2026-09-22 13:27：多 seed 第一条新增训练已启动。实验分支 HEAD=
  `4869354`。当前训练在首轮尚未写出 history 时已确认进程存活；协议仅含
  train/val。旧自动化 ID `cbvd4` 在 Codex app 中已不存在，未自动新建。
- 2026-09-23：Kinetics seed 20260901 在完成 epoch 11 后曾无最终摘要退出；
  `last.pt` 与 binding 哈希一致，确认无重复进程后按冻结参数 `--resume`，
  当前识别到 PID 6164。最后检查已完成 epoch 12，尚无最终摘要。汇总实现
  `38a4517` 及审计加固 `30ed5f8`/`7cba9f5`/`e7723b3` 已通过 60 项聚焦测试，
  计划更新 `ed91bbb`；下一
  动作是等待本臂正常结束，核验最终摘要后串行启动 CVB-transfer seed
  20260901，不得并行占用单 GPU，也不得读取正式 test。
- 2026-09-29：WAID4500 收尾。Codex 停在 `f510859`（Task 9 未执行，卡在等审批时额度耗尽）。
  本次在同一 worktree 补齐 Task 9：聚焦/全量 Python 测试、真实 check-only、真实
  verifier、真实 1 epoch 冒烟训练、前端测试与构建。冒烟首次运行暴露上述非 ASCII
  路径缺陷（Codex 从未跑到这一步），已按 TDD 修复并提交 `f18bd4d`；随后冒烟退出码 0。
  未做：合并到 `integration`、剩余三条多 seed 臂。上一条 2026-09-23 记录的
  Kinetics seed 20260901 已于当日 20:57 正常结束（见「已完成」）。
- 2026-09-29 20:02：WAID 收尾已提交并快进合并（`integration` HEAD=`1a8d033`），随后
  启动多 seed 矩阵第 2 条新增臂 CVB-transfer seed 20260901，PID 6152，工作目录
  `.worktrees/cross-domain-behavior`，完整命令行：

  ```powershell
  & 'F:\deepl\anaconda1\envs\pytorch\python.exe' -u -X utf8 -m scripts.train_cbvd4_behavior `
    --mode train --development-only --project-root . `
    --manifest-root data/external/cbvd5/manifests/cbvd4 `
    --output-root outputs/cbvd4/paper_20260922/multiseed_validation/cvb_transfer_init/seed_20260901 `
    --initialization cvb_transfer_init --source-checkpoint models/behavior/cvb_x3d_v2_best.pt `
    --device cuda --epochs 30 --batch-size 8 --accumulation-steps 2 --learning-rate 3e-4 `
    --weight-decay 1e-4 --patience 6 --workers 0 --seed 20260901 --freeze-backbone-epochs 2
  ```

  启动时已核对：GPU 空闲（0 MiB/8188 MiB）、无其他 python 进程、两个起训权重与
  train/val 清单及视频数据齐备、目标输出目录不存在；`training_protocol.json`
  `test_data_read=false`。中断处理：确认无重复进程后，用上面完全相同命令加
  `--resume`；不得删除失败运行或换种子。
- 2026-09-29 22:44：上述进程在写完 epoch 2 后**静默消失**（`history.csv` 止于 epoch 2，
  `stdout.log` 一直为 0 字节，`stderr.log` 停在上一次启动时刻）。排查证据：应用程序日志与
  系统日志在该时间窗内没有任何 python.exe 错误、AppCrash 或内存耗尽记录，系统日志只有
  显卡 RTD3 电源状态事件 → 判定为外部终止（把训练当普通后台任务跑，被会话/系统回收），
  不是训练代码缺陷。这也解释了上一臂 2026-09-23「完成 epoch 11 后无最终摘要退出」的同类
  现象。
- 2026-09-30 11:49：第一次尝试从断点恢复 CVB-transfer seed 20260901。命令与上面完全相同，
  只追加 `--resume`；改用 **`Start-Process` 脱离式独立进程**（PID 29912），日志
  `cvb_transfer_seed_20260901_resume_20260929.{stdout,stderr}.log`。自检时（+3 分钟）GPU
  已升到 4356 MiB、`resume_binding.json` 校验通过、无绑定错误；但命令返回后不久该进程
  又被静默回收（`stdout` 0 字节、`stderr` 只有 TypedStorage 警告、无回溯），断点文件未被
  破坏。**教训：本环境会把手动脱离的子进程当游离进程回收，脱离式启动不可用。**
- 2026-09-30 11:52:54：第二次恢复，改用**会话托管的后台任务**（本会话唯一能长跑的形态），
  PID 3368，命令同前（含 `--resume`），日志
  `cvb_transfer_seed_20260901_resume_20260930.{stdout,stderr}.log`，PID 文件已更新为 3368。
  自检：GPU 4356 MiB、利用率 100%（确在训练 epoch 3）、命令行含 `--resume`、无重复进程。
  注意：跑完前 `stdout.log` 为空是正常的，最终 JSON 摘要只在结束时写出；进度看 `history.csv`。
  若该后台任务再被回收，按同一命令加 `--resume` 重启即可，已完成 epoch 不丢。
  当天另有**另一个 Codex 会话**在按 `docs/WAID4500_REPRODUCIBILITY.md` 跑 check-only →
  verifier → pytest（只读，不占显存）；它若继续跑文档 §6 的 WAID 冒烟/完整训练，会与本臂
  争抢 8 GB 显存，本臂结束前不要启动。
- 2026-09-30 18:37：CVB-transfer seed 20260901 **正常收尾（不是中断）**：后台任务回报
  `resume_exit=0`，`stdout.log` 写出 7758 字节最终 JSON 摘要，patience=6 触发早停，停在
  epoch 11（最佳 epoch 5），validation Macro-F1=0.8325412642、accuracy=0.9146341463，
  `best.pt` SHA-256=`3f28cca2d984c1133d860afbae7e0d20de321cae0669c49b241a8a6a8ccb9857`，
  `test_metrics_read=false`，产物齐全。新一代 4 条臂至此完成 2 条；下一步 Kinetics
  seed 20260908（同命令换 `--output-root …/kinetics_init/seed_20260908`、
  `--initialization kinetics_init`、`--kinetics-checkpoint models/pretrained/X3D_XS.pyth`、
  `--seed 20260908`，去掉 `--source-checkpoint`），必须串行、不得并行占卡。
- 2026-09-30 19:28:36：启动第 3 条臂 Kinetics seed 20260908（PID 5256），工作目录
  `.worktrees/cross-domain-behavior`，完整命令行：

  ```powershell
  & 'F:\deepl\anaconda1\envs\pytorch\python.exe' -u -X utf8 -m scripts.train_cbvd4_behavior `
    --mode train --development-only --project-root . `
    --manifest-root data/external/cbvd5/manifests/cbvd4 `
    --output-root outputs/cbvd4/paper_20260922/multiseed_validation/kinetics_init/seed_20260908 `
    --initialization kinetics_init --kinetics-checkpoint models/pretrained/X3D_XS.pyth `
    --device cuda --epochs 30 --batch-size 8 --accumulation-steps 2 --learning-rate 3e-4 `
    --weight-decay 1e-4 --patience 6 --workers 0 --seed 20260908 --freeze-backbone-epochs 2
  ```

  后台任务形态（本环境唯一能长跑的形态），日志
  `outputs/cbvd4/paper_20260922/logs/kinetics_seed_20260908.{stdout,stderr}.log`，PID 文件同名
  `.pid`。启动自检：无重复进程、协议 `test_data_read=false`、清单哈希与冻结矩阵一致。
  中断处理：确认无重复进程后原命令加 `--resume`；不得删除失败运行或换种子。
- 2026-09-30 22:43：Kinetics seed 20260908 在写完 epoch 2 后**再次被静默终止**（`pwsh-2`
  回报 `killed before exit`，`stdout.log` 0 字节，`stderr` 只有 TypedStorage 警告）。与
  09-29 22:44 那次一致：**两晚都在 22:43--22:44 被杀**，而 22:30--23:00 的系统日志里
  **没有任何睡眠/关机/注销/事件日志重启记录**（已查 Kernel-Power/Kernel-General/User32/
  EventLog/Power-Troubleshooter）→ 判定为会话/服务层面的进程清理（托管任务随会话结束被杀），
  不是系统断电或训练缺陷。**规律：会话每夜停止一次，训练每晚最多推进到 22:43。**
- 2026-10-01 13:20:24：按原命令加 `--resume` 恢复第 3 条臂（PID 3396）。恢复前独立核验：
  `torch.load(last.pt)` 得到 `epoch=2` 且含完整 `model/optimizer/scheduler/scaler/rng/
  history/best_f1/patience`，非截断；`validate_resume_binding()` 用 `last.pt` 的 SHA-256
  与 `resume_binding.json` 比对通过（该函数不一致即抛错）。日志
  `kinetics_seed_20260908_resume_20261001.{stdout,stderr}.log`，PID 文件已更新为 3396。
  用户 2026-10-01 明确决定：**不重跑**（重跑要删既有运行、偏离冻结矩阵，且解决不了夜杀），
  **也不加计划任务/守护脚本**；被回收后由用户叫起、按同命令加 `--resume` 续跑。
- 2026-10-01 21:01：Kinetics seed 20260908 在写完 epoch 12 后**第三次被静默回收**（进程消失、
  `stdout.log` 0 字节、GPU 归零、无回溯）。注意**回收时机并不固定在 22:43**（前两次在
  22:43--22:44，这次在 21:01 之后），所以不能按点预测，只能靠 `history.csv` 与进程/GPU 判断。
  此时进度 13 轮（epoch 0--12），最佳 epoch 7=0.8436268208，自 epoch 7 起连续 5 轮未刷新。
- 2026-10-01 21:47:08：第二次续训（PID 7000），命令同前加 `--resume`，日志改为
  `kinetics_seed_20260908_resume2_20261001.{stdout,stderr}.log`（递增命名，避免覆盖前一次
  日志），PID 文件更新为 7000。自检：GPU 4370 MiB、绑定校验通过、无重复进程。
  **下一步只等 epoch 13**：若它不刷新 0.8436268208，patience=6 触发早停，本臂即收尾并写出
  最终 JSON 摘要（届时核对 `best_val_macro_f1`/`test_metrics_read=false` 与 `best.pt` 哈希）。
- 2026-10-01 22:34：Kinetics seed 20260908 **正常收尾**（`resume2_exit=0`，`stdout.log`
  8736 字节最终摘要）：epoch 13 得 0.8424501，未刷新 epoch 7 的 0.8436268208，patience=6
  触发早停，共 14 轮。核对：`epochs_completed=14`、`best_val_macro_f1=0.8436268208269122`、
  `best.pt` 实际 SHA-256 与 `validation_metrics.json` 记录同为
  `5802f043d5a177b7cd1a3c90106254a22e176817d8918f86fdf1e8af1de4318d`、
  `test_metrics_read=false`、清单哈希与冻结矩阵一致。Kinetics 臂三 seed 齐全
  （0.8398443 / 0.8530159 / 0.8436268）。**六格只剩 CVB-transfer seed 20260908。**

- 2026-10-02：WAID 复现加固第 1 批（3 项，TDD，每项先看 RED）：
  1) 导入可移植性：`import_assets()` 复制冻结数据集后用 `write_runtime_data_yaml()`
     重写 `data.yaml`（并重算该组件清单，保持 file/bytes 统计真实）；`rebuild_dataset()`
     改用同一函数消除重复实现。
  2) PowerShell `rebuild` 默认输出由 `data\external\waid\derived\waid4500_v1`（冻结目录，
     必然已存在 → `rebuild_dataset` 拒绝）改为 `derived\waid4500_rebuilt`，与指南 §4 一致。
  3) 续训越界防护：新增 `recorded_output_root()` / `require_portable_resume()`，在
     `run_training()` 里于任何重活之前校验检查点记录的输出根必须落在配置的
     `project` 之内。证据：归档检查点 `train_args.project=E:\大创\WAID_YOLO11\runs`；
     Ultralytics `engine/trainer.py:845-851` 续训时 `self.args = get_cfg(ckpt_args)`。
     实测：归档 checkpoint REFUSED、`reproduced/smoke_e1` ACCEPTED。
  提交 `2ea7dc6`、`733cbbb`；聚焦 48 passed、worktree 全量 591 passed / 4 skipped /
  2 项既有失败。**下一步**：五类资产整批导入事务；verifier 全量样本/固定划分校验与逐样本
  内容哈希（后两项需用户确认声明口径）。

- 2026-10-02：WAID 复现加固第 2 批（**整批导入事务**，用户指定先做这一项，不动声明口径）：
  `import_assets()` 改为两阶段——先把五类资产全部复制到各自的兄弟暂存目录并逐一校验
  （新增 `_stage_asset()`，替代原先边拷边发布的 `_copy_asset()`），再统一发布；发布阶段任一
  失败即整体回滚：移除已发布组件、把被替换的旧资产从备份恢复，全部成功后才删除备份。
  RED 测试 `test_batch_import_publishes_nothing_when_a_later_component_fails` 先失败
  （原先中途失败会在项目里残留 `data/external/waid/raw`）。提交 `7080174`；聚焦 49 passed、
  全量 592 passed / 4 skipped / 2 项既有失败。**剩余 2 项**（verifier 全量 4,720 样本与固定
  划分校验、逐样本内容哈希）直接决定能否声明"完整复现证据全部通过"，等用户定调。

- 2026-10-02：WAID 复现加固第 3 批（**证据强度两项**，用户选定"两项都做"）：
  `verify_dataset_samples()` 逐条校验全部 4,720 个样本（图片/标签存在、`parse_label` 与
  清单元数据一致）并把 `splits/{train,valid,test}.txt` 的成员集合与清单划分比对；
  `sample_content_hashes()` / `write_sample_hashes()` / `load_sample_hashes()` /
  `verify_sample_hashes()` 记录并重算逐样本内容摘要（图片+标签），新增生成器
  `scripts/reproducibility/write_waid_sample_hashes.py`，跟踪文件
  `reproducibility/waid4500/dataset_samples.sha256`（4,720 行 / 1.2 MB）；verifier CLI 增加
  `--dataset` / `--sample-hashes`，整体 `status` 现聚合六层。RED 测试先失败（缺失 API，
  另有一次测试抓到"哈希文件接受任意相对路径"的真实弱点，已收紧为必须
  `images/<split>/` 前缀）。真实端到端：`status=passed`、样本 4,720/4,720、
  4,500/200/20、内容哈希 4,720/4,720。提交 `f6e6df7`；聚焦 58 passed、全量 601 passed /
  4 skipped / 2 项既有失败。**复核 6 项已全部处理，分支已由用户确认合并回 `integration`。**

- 2026-10-02 14:44:46：启动多 seed 矩阵最后一格 CVB-transfer seed 20260908（PID 28468），
  工作目录 `.worktrees/cross-domain-behavior`，完整命令行：

  ```powershell
  & 'F:\deepl\anaconda1\envs\pytorch\python.exe' -u -X utf8 -m scripts.train_cbvd4_behavior `
    --mode train --development-only --project-root . `
    --manifest-root data/external/cbvd5/manifests/cbvd4 `
    --output-root outputs/cbvd4/paper_20260922/multiseed_validation/cvb_transfer_init/seed_20260908 `
    --initialization cvb_transfer_init --source-checkpoint models/behavior/cvb_x3d_v2_best.pt `
    --device cuda --epochs 30 --batch-size 8 --accumulation-steps 2 --learning-rate 3e-4 `
    --weight-decay 1e-4 --patience 6 --workers 0 --seed 20260908 --freeze-backbone-epochs 2
  ```

  后台任务形态（本环境唯一能长跑的形态），日志
  `outputs/cbvd4/paper_20260922/logs/cvb_transfer_seed_20260908.{stdout,stderr}.log`，PID 文件
  同名 `.pid`。启动自检：无重复进程、GPU 空闲、协议 `test_data_read=false`、
  `evaluation_scope=train_val_only`、`source_checkpoint_sha256=731c6ed3…`（与 seed_20260901
  臂同源）、`kinetics_checkpoint_sha256=null`、清单哈希与冻结矩阵一致。中断处理：确认无
  重复进程后原命令加 `--resume`；不得删除失败运行或换种子。
- 2026-10-02 22:45：按用户要求**在 epoch 8 落盘后暂停**该臂（用户 22:16 指示「下一轮结束后
  暂停」）。做法：挂监视器（`cvb_transfer_seed_20260908.pause-watcher.log`）轮询
  `history.csv`，检测到第 9 行数据（epoch 8 @ 22:44:43）后再等 15 秒确认行数不再变化，
  才 `Stop-Process` 掉 PID 28468，并确认进程已退出（`still alive=False`）。这是**刻意的
  干净暂停**，不是崩溃：`last.pt`/`resume_binding.json`/`history.csv` 同一时刻写出，
  独立 `torch.load` 校验 `epoch=8`、`best_f1=0.8266304`、历史 9 条、
  optimizer/scheduler/scaler/rng 齐全 → 可原样 `--resume`。训练任务的
  `cvb_transfer_seed_20260908_exit=-1`（被主动 kill）与 `stdout.log` 为空都是预期现象，
  不要误判为失败运行。恢复命令即上面 14:44:46 那条命令加 `--resume`。
- 2026-10-03 12:25:27：按用户「继续下一个训练」的指示恢复该臂（**恢复前已确认无重复进程**、
  GPU 空闲，`last.pt` 为 epoch 8 完整状态）。命令 = 2026-10-02 14:44:46 那条原样加
  `--resume`，PID 6240，日志
  `outputs/cbvd4/paper_20260922/logs/cvb_transfer_seed_20260908_resume_20261002.{stdout,stderr}.log`
  （文件名后缀 20261002 只是调用时写的标签，实际启动为 2026-10-03 12:25:27），PID 文件已更新为
  6240。自检：`--resume` 生效、`validate_resume_binding()` 通过（stderr 无绑定错误）、
  GPU 4347 MiB / 100%（确在训练）。本次**未再挂暂停监视器**（用户未要求），训练将继续到
  早停或 30 轮上限。
- 2026-10-03 13:58:09：CVB-transfer seed 20260908 **正常收尾**（不是中断）：
  `cvb_transfer_seed_20260908_resume_exit=0`，恢复日志写出 7262 字节最终 JSON 摘要；
  epoch 9 = 0.8017、epoch 10 = 0.8181 均未刷新 epoch 4 的 0.8266304028，patience=6 触发
  早停，共 11 轮。核对：`val_macro_f1=0.8266304027953745`、`accuracy=0.8943089430894309`、
  `best.pt` 实际 SHA-256 与 `validation_metrics.json` 同为
  `0d3b19161a482fd3021ee843e75623b979a5f0b99d0180f9468b9d9aa604380e`、
  `test_metrics_read=false`、清单哈希与冻结矩阵一致；产物齐全（`metrics.json`、
  `classification_report.csv`、`confusion_matrix.*`、`training_curves.png`）。
  **多 seed 矩阵四条新臂至此全部跑完，六格齐全。** 下一步只剩计划 Task 7 汇总。
- 2026-10-03 14:49:02：计划 **Task 7 汇总完成**（`summarize_exit=0`，14:08:23 启动、耗时约
  41 分钟）：生成 `validation_metrics.csv`（6 行）、`aggregate.json`（39.6 KB）、`report.md`
  与 `analysis/<初始化>/seed_<seed>/validation_predictions.csv`（每格 984 条）。
  核对：`aggregate.json.test_data_read=false`、`seed_count_per_initialization=3`；
  Kinetics 均值 0.8454960（样本标准差 0.0067818）、CVB-transfer 均值 0.8336248
  （0.0066230）；配对差值 +0.0008785 / −0.0204746 / −0.0160163；逐类均值显示
  ruminating-standing 为两臂最弱（kinetics 0.624246 / cvb 0.591244）。
  **一处需知的差异**：最后一格训练内记录 0.8266304028、汇总统一重算为 0.8276105066
  （Δ≈0.00098），其余五格两者逐位一致；跨格比较以统一重算的 CSV 为准。
  本轮为 validation-only，**未读取正式 test**；矩阵至此结清，按预注册不作候选选择。
  `report.md` 亦明确写着 `No promotion decision is made from this validation-only experiment.`

## 还原上一段对话

最近 Codex 会话日志在 `C:\Users\Mrda\.codex\sessions\`（按日期分目录，`rollout-*.jsonl`）。
本次接手读的是 `2026\09\29\rollout-2026-09-29T17-54-22-*.jsonl` 等文件：Codex 已完成
Task 1--8 并提交到 `f510859`，开始 Task 9 后先跑通聚焦 40 项与全量测试（583 通过 /
2 失败）、前端测试与构建，随后临时把分支里的 `reproducibility/` 复制到 `F:\new大创`
以便对真实资产运行 check-only 与 verifier —— 就在这条命令的审批请求处额度耗尽，
Task 9 Step 2 起（真实 check-only、冒烟、verifier、HANDOFF 提交）全部未执行。

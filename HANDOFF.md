# HANDOFF.md — 交接台账

> 谁在干活谁维护。任何 AI 接手第一步：读完本文件 → `git log --oneline -10` + `git status` + `git worktree list` 核对 → 跑测试 → 从「下一步」清单继续。规则见 `AGENTS.md`。

- 最后更新：2026-10-01（第 3 条臂 Kinetics seed 20260908 昨夜 22:43 被会话层回收，已在 13:20 从 epoch 2 续训；用户确认「不重跑、不加计划任务，断了叫我续」；WAID4500 独立复核的 6 项加固缺口仍待用户定夺）

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
- 多 seed validation 矩阵：新一代 4 条臂已完成 2 条——Kinetics seed 20260901
  （0.8530158904）与 CVB-transfer seed 20260901（0.8325412642，详见「已完成」）；
  **第 3 条 Kinetics seed 20260908 正在训练**（2026-09-30 19:28:36 首启 PID 5256，跑完
  epoch 0--2 后于 22:43 被外部静默终止；2026-10-01 13:20:24 按原命令加 `--resume` 恢复，
  PID 3396，GPU 4347 MiB，绑定校验通过）。kinetics 臂形态：给
  `--kinetics-checkpoint models/pretrained/X3D_XS.pyth`、不给 `--source-checkpoint`、
  `--seed 20260908`。启动/恢复自检：协议 `test_data_read=false`、
  `evaluation_scope=train_val_only`、`kinetics_checkpoint_sha256=6dafc961…`、
  `source_checkpoint_sha256=null`、清单哈希与冻结矩阵一致。日志（在
  `.worktrees/cross-domain-behavior` 的 `outputs/cbvd4/paper_20260922/logs/`）：
  首启 `kinetics_seed_20260908.{stdout,stderr}.log`、当前恢复
  `kinetics_seed_20260908_resume_20261001.{stdout,stderr}.log`，PID 文件同名 `.pid`；
  输出 `outputs/cbvd4/paper_20260922/multiseed_validation/kinetics_init/seed_20260908`。
  识别进程靠完整命令行 + 输出目录，不能只信 PID；被回收就原命令加 `--resume`。
  **用户已确认的操作模式（2026-10-01）：不重跑、不加计划任务/守护脚本，每晚被回收后由
  用户叫起、按同命令加 `--resume` 续上。** 跑完只剩 CVB-transfer seed 20260908，
  必须串行、一次一条、不得并行占卡，只读 train/val。
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
- [ ] 用户确认后按测试驱动完成 WAID 复现加固：全数据/固定划分验证、逐样本内容哈希、
  portable `data.yaml`、安全续训、独立 rebuild 输出和整批导入事务；完成前不再把当前
  verifier 的 `passed` 表述为“完整复现证据全部通过”。
- [ ] 串行补齐剩余两条多 seed 臂（Kinetics seed 20260908 → CVB-transfer seed 20260908）；
  单 GPU 不得并行，异常退出只在绑定有效且无重复进程时按原参数 `--resume`，全程不得读取
  正式 test。（CVB-transfer seed 20260901 已于 2026-09-30 完成；剩余两条的完整命令见
  「中断记录」2026-09-30 18:37 条目与计划 Task 6 Step 3--4。）
- [ ] 主线：把申报材料相关未跟踪文件整理提交（`~$*` Office 临时文件已忽略，勿提交）。
- [ ] 数据：采集或取得新的前瞻性独立牧场视频，按源视频冻结新的确认集，并记录许可、来源、哈希和暴露边界。
- [ ] 论文统计：报告多 seed 均值/方差、逐类指标、校准、风险—覆盖率和按源视频 bootstrap；把当前结果定位为监督域适配与协议审计，不宣称完全独立外部验证。
- [ ] WAID：在冻结基线上预注册精度改进实验（本次资产整合与训练入口本身不提升精度，
  不同 GPU/CUDA/Ultralytics 版本也不保证逐字节相同的权重）。
- [ ] 仅当预注册候选在新的确认集达到 Macro-F1 ≥ 0.70 且每类 F1 ≥ 0.60，才安装 CBVD4 模型并执行上传视频端到端演示。

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
  **也不加计划任务/守护脚本**；每晚被回收后由用户叫起、按同命令加 `--resume` 续跑。

## 还原上一段对话

最近 Codex 会话日志在 `C:\Users\Mrda\.codex\sessions\`（按日期分目录，`rollout-*.jsonl`）。
本次接手读的是 `2026\09\29\rollout-2026-09-29T17-54-22-*.jsonl` 等文件：Codex 已完成
Task 1--8 并提交到 `f510859`，开始 Task 9 后先跑通聚焦 40 项与全量测试（583 通过 /
2 失败）、前端测试与构建，随后临时把分支里的 `reproducibility/` 复制到 `F:\new大创`
以便对真实资产运行 check-only 与 verifier —— 就在这条命令的审批请求处额度耗尽，
Task 9 Step 2 起（真实 check-only、冒烟、verifier、HANDOFF 提交）全部未执行。

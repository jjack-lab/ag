# HANDOFF.md — 交接台账

> 谁在干活谁维护。任何 AI 接手第一步：读完本文件 → `git log --oneline -10` + `git status` + `git worktree list` 核对 → 跑测试 → 从「下一步」清单继续。规则见 `AGENTS.md`。

- 最后更新：2026-09-29（接手方：补齐 Codex 中断的 WAID4500 复现收尾、修掉非 ASCII 路径下的检查点写入缺陷，并启动 CBVD4 CVB-transfer seed 20260901 训练）

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

- `codex/waid-reproducibility` 已快进合并到 `integration`（`1a8d033`，集成后完整
  `pytest` 588 通过 / 4 跳过 / 2 项既有失败，verifier `status=passed`）。worktree 仍在
  `C:\Users\Mrda\.codex\worktrees\waid-reproducibility\`（Codex 应用托管，未擅自删除），
  分支也保留，需要时再 `git worktree remove` + `git branch -d`。
- WAID 大资产只在本机且被忽略：`data/external/waid/{raw,derived,cache}`、
  `outputs/training/waid4500_yolo11s/{run,logs}`；训练会在冻结数据集目录内新增
  Ultralytics `*.cache`（已被忽略，重建对比时排除，勿手工删除或提交）。
- 多 seed validation 矩阵：已完成 Kinetics seed 20260901；**CVB-transfer seed
  20260901 正在训练**（2026-09-29 20:02 启动，PID 6152，接手时必须用完整命令行和
  输出目录重新识别进程，不要只信 PID；完整命令见「中断记录」）。输出
  `outputs/cbvd4/paper_20260922/multiseed_validation/cvb_transfer_init/seed_20260901`，
  日志 `outputs/cbvd4/paper_20260922/logs/cvb_transfer_seed_20260901.{stdout,stderr}.log`
  （均在 `.worktrees/cross-domain-behavior` 下）。`training_protocol.json` 已写出并通过
  隔离检查：`test_data_read=false`、`evaluation_scope=train_val_only`、只含 train/val
  清单哈希。仍剩 Kinetics seed 20260908、CVB-transfer seed 20260908，必须在本臂结束后
  串行启动，不得并行占卡。
- `codex/cross-domain-behavior` 仍有 3 个用户所有、未提交文档（roadmap、2026-09-12
  选择性数据可行性、2026-09-12 测试来源审计），接手方不得擅自覆盖或提交。
- 主线有未跟踪文件：评估报告、`星牧智控-项目计划书.docx`、`申报-项目概述.txt`、`scripts/make_plan_docx.py`。

## 下一步（P0，按序执行）

- [ ] 合并 `codex/waid-reproducibility` 到 `integration`（可快进）：合并后主线才具备
  `reproducibility/waid4500/` 证据文件，指南里的 verify/rebuild/train 命令才能直接运行。
- [ ] 串行补齐剩余三条多 seed 臂（CVB-transfer 20260901 → Kinetics seed 20260908 →
  CVB-transfer seed 20260908）；单 GPU 不得并行，异常退出只在绑定有效且无重复进程时
  按原参数 `--resume`，全程不得读取正式 test。
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

## 还原上一段对话

最近 Codex 会话日志在 `C:\Users\Mrda\.codex\sessions\`（按日期分目录，`rollout-*.jsonl`）。
本次接手读的是 `2026\09\29\rollout-2026-09-29T17-54-22-*.jsonl` 等文件：Codex 已完成
Task 1--8 并提交到 `f510859`，开始 Task 9 后先跑通聚焦 40 项与全量测试（583 通过 /
2 失败）、前端测试与构建，随后临时把分支里的 `reproducibility/` 复制到 `F:\new大创`
以便对真实资产运行 check-only 与 verifier —— 就在这条命令的审批请求处额度耗尽，
Task 9 Step 2 起（真实 check-only、冒烟、verifier、HANDOFF 提交）全部未执行。

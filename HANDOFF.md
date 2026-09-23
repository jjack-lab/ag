# HANDOFF.md — 交接台账

> 谁在干活谁维护。任何 AI 接手第一步：读完本文件 → `git log --oneline -10` + `git status` + `git worktree list` 核对 → 跑测试 → 从「下一步」清单继续。规则见 `AGENTS.md`。

- 最后更新：2026-09-23（Codex：CBVD4 多种子验证续训与汇总工具）

## 当前阶段目标

1. 保留已完成的 CBVD4 冻结三臂实验及负晋级结论，禁止依据当前 test 结果换候选或调参。
2. 为论文准备新的前瞻性独立确认数据；仅在开发集开展多 seed 与站立反刍改进实验。
3. 大创申报材料定稿并入库；主线 `integration` 保持测试绿色、随时可演示。

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
- 完整评估：`docs/2026-08-24-new-dachuang-complete-project-assessment.md`；
  路线图（P0/P1/P2 与执行顺序）：worktree 内 `docs/2026-08-24-project-status-and-roadmap.md`。

## 进行中

- `codex/cross-domain-behavior`：Kinetics seed 20260901 已从绑定有效的 epoch
  11 `last.pt` 原参数恢复；2026-09-23 最后检查时 PID 6164 为唯一匹配进程，
  history 已有 13 个已完成 epoch（0--12），epoch 12 validation Macro-F1=
  0.8530158904，进程继续下一轮且尚无最终摘要；stderr 仅有 PyTorch
  TypedStorage 弃用警告。当前 `best.pt` SHA-256=
  `ecc4ccd176ef172c2ce9061ed242abce210d05d659627512b6b613a723c36654`。输出
  `outputs/cbvd4/paper_20260922/multiseed_validation/kinetics_init/seed_20260901`，
  恢复日志为 `outputs/cbvd4/paper_20260922/logs/kinetics_seed_20260901_resume_20260923.*.log`。
  接手时必须用完整命令行和输出目录重新识别进程，不依赖旧 PID。
- 多 seed 矩阵固定为两种初始化 × seeds 20260824/20260901/20260908；旧
  20260824 两臂只读复用，新增四次训练串行执行。所有新协议只有 train/val，
  `test_data_read=false`。
- 实验 worktree 仍有 3 个用户所有、未提交文档（roadmap、2026-09-12
  选择性数据可行性、2026-09-12 测试来源审计），接手方不得擅自覆盖或提交。
- 主线有未跟踪文件：评估报告、`星牧智控-项目计划书.docx`、`申报-项目概述.txt`、`scripts/make_plan_docx.py`。

## 下一步（P0，按序执行）

- [ ] 主线：把申报材料相关未跟踪文件整理提交（`~$*` Office 临时文件已忽略，勿提交）。
- [ ] 完成当前 Kinetics seed 20260901；成功后按固定顺序串行运行
  CVB-transfer seed 20260901、Kinetics seed 20260908、CVB-transfer seed
  20260908。异常退出只允许在绑定有效且无重复进程时原参数 `--resume`。
- [x] 补齐 validation-only 逐样本推理/汇总 CLI，输出六单元均值、样本标准差、
  配对 seed 差值和逐类 F1；不得读取当前 test。
- [ ] 数据：采集或取得新的前瞻性独立牧场视频，按源视频冻结新的确认集，并记录许可、来源、哈希和暴露边界。
- [ ] 论文统计：报告多 seed 均值/方差、逐类指标、校准、风险—覆盖率和按源视频 bootstrap；把当前结果定位为监督域适配与协议审计，不宣称完全独立外部验证。
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

## 还原上一段对话

最近 Codex 会话日志在 `C:\Users\Mrda\.codex\sessions\`（按日期分目录，`rollout-*.jsonl`）。
接手方读最新文件的末尾若干条记录，即可还原中断时对方正在做什么、想什么。

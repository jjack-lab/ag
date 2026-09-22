# HANDOFF.md — 交接台账

> 谁在干活谁维护。任何 AI 接手第一步：读完本文件 → `git log --oneline -10` + `git status` + `git worktree list` 核对 → 跑测试 → 从「下一步」清单继续。规则见 `AGENTS.md`。

- 最后更新：2026-09-22（Codex：CBVD4 冻结三臂实验收尾）

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
- 完整评估：`docs/2026-08-24-new-dachuang-complete-project-assessment.md`；
  路线图（P0/P1/P2 与执行顺序）：worktree 内 `docs/2026-08-24-project-status-and-roadmap.md`。

## 进行中

- `codex/cross-domain-behavior`：正式训练和冻结评估已完成，无训练进程在运行。仍有 3 个用户所有、未提交文档（roadmap、2026-09-12 选择性数据可行性、2026-09-12 测试来源审计），接手方不得擅自覆盖或提交。
- 论文阶段尚未开始新的模型实验；当前 test 有历史研发暴露限制，必须另采前瞻性独立确认数据。
- 主线有未跟踪文件：评估报告、`星牧智控-项目计划书.docx`、`申报-项目概述.txt`、`scripts/make_plan_docx.py`。

## 下一步（P0，按序执行）

- [ ] 主线：把申报材料相关未跟踪文件整理提交（`~$*` Office 临时文件已忽略，勿提交）。
- [ ] 论文开发实验：在 train/val 范围内预注册多 seed 初始化对照，并针对站立反刍做类别均衡、时序/裁剪误差分析；不得读取当前 test 调参。
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

## 还原上一段对话

最近 Codex 会话日志在 `C:\Users\Mrda\.codex\sessions\`（按日期分目录，`rollout-*.jsonl`）。
接手方读最新文件的末尾若干条记录，即可还原中断时对方正在做什么、想什么。

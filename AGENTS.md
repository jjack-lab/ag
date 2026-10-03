# AGENTS.md — 项目宪法（GPT/Codex 与 ZCode 共同遵守）

> 任何 AI 助手在本仓库开始工作前，必须先读完本文件和 `HANDOFF.md`。
> 本文件是两个 AI 协作的唯一规则入口，修改本文件需用户同意。

## 项目

星牧智控：牛只视觉识别、行为分析与健康风险辅助筛查系统（科研原型，非牧场部署产品）。

- 主线分支：`integration` —— 必须随时保持测试绿色、可演示。
- 实验工作树（互不相同的独立分支）：
  - `.worktrees/cross-domain-behavior`（分支 `codex/cross-domain-behavior`，CBVD4 迁移学习主战场）
  - `.worktrees/cvb-behavior`（分支 `feature/cvb-behavior`）
  - `.worktrees/runtime-operability-hardening`（分支 `codex/runtime-operability-hardening`）

## 目录地图

| 位置 | 内容 |
| --- | --- |
| `cattle_health_app/` | Python 后端与算法 |
| `health_monitor.py` | 规则型健康监测 |
| `web/` | React 前端 |
| `tests/`、`delivery_tests/` | Python 自动化测试 |
| `models/detection/`、`models/behavior/` | 模型文件（带哈希校验，禁止手工改动） |
| `docs/` | 评估报告、实验记录、数据记录 |
| `scripts/` | 辅助脚本 |
| `HANDOFF.md` | 交接台账（唯一交接入口） |

## 常用命令

- 后端测试：`pytest`
- 前端测试：在 `web/` 下 `npm test`
- 前端构建：在 `web/` 下 `npm run build`
- 启动交付链路：`start_delivery.ps1` 或 `启动项目.bat`；停止：`stop_delivery.ps1` 或 `停止项目.bat`

## 工作纪律

1. 小步提交：一个可验证单元一个 commit，消息风格 `fix:` / `feat:` / `docs:` / `test:`。
2. 禁止 force push `integration`，禁止改写已合并的历史提交。
3. 禁止提交模型大文件与 `~$*` Office 临时文件（后者已在 `.gitignore`）。
4. 改动前后跑对应测试；一切"已完成"的声明以测试实际运行结果为准。

## 交接协议（核心）

1. 每段工作结束或额度将尽，必须更新 `HANDOFF.md` 并 commit —— 这是硬性要求，不是可选项。
2. 接手仪式（任何 AI 接手时按序执行）：
   1. 读 `HANDOFF.md` 全文；
   2. `git log --oneline -10`、`git status`、`git worktree list` 核对文件所述属实；
   3. 跑 `pytest` 与前端测试，确认客观状态；
   4. 从 `HANDOFF.md` 的「下一步」清单第一项继续。
3. 如需还原上一段对话的细节（如半成品思路），读最近的 Codex 会话日志：
   `C:\Users\Mrda\.codex\sessions\`（按日期分目录，`rollout-*.jsonl`，读最新文件的末尾即可）。

## 额度收尾话术（额度将尽时，用户复制给 GPT/Codex）

> 额度快用完了，请立即收尾：1) 把当前所有改动 git commit（WIP 也可以）；2) 更新 HANDOFF.md 的六个小节：当前阶段目标、已完成、进行中、下一步（拆成可独立执行的小任务）、决策与坑、中断点（停在哪一步、半成品在哪）；3) 提交 HANDOFF.md。完成后停止，不要再开始任何新任务。

## 额度监听器

- 双击仓库根目录的 `启动额度监听.bat`（或 `python scripts/watch_quota.py`）启动后台监听。
- 它盯住 `~/.codex/sessions/` 的本地会话日志，检测到额度/限流报错时自动：
  1. 对主仓库和所有 worktree 做 WIP 提交（保住半成品）；
  2. 在 `HANDOFF.md` 的「中断记录」小节追加现场记录（含来源会话文件路径）；
  3. 弹窗提醒切换到 ZCode。
- 监听只识别启动之后新写入的日志，**应在开始一天的工作前启动它**。
- 它只负责保现场和报警，不会自动启动另一个 AI 接手 —— 切换由用户说一句"继续"完成。

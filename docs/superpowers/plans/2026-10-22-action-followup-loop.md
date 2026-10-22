# 视频处置与复查闭环 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 从已完成视频创建人工核查事项，记录处理与复查，并能从全局清单打开原视频。

**Architecture:** FastAPI 验证业务规则；SQLite 用事项表保存当前状态、追加表保存历史；React 在视频结果与工作区使用同一事项 API。只绑定视频任务，不推断永久个体身份或疾病。

**Tech Stack:** Python/FastAPI/Pydantic/SQLite、React/TypeScript/Vitest。

---

### Task 1: 事项存储与服务端接口

**Files:** `cattle_health_app/repository.py`、`cattle_health_app/api.py`、`tests/test_action_tasks_api.py`

- [ ] 写 API 失败测试：已完成视频能创建 `pending` 事项并回读；不存在/未完成视频、无效 Track ID、空白标题和负责人被拒；101 条记录也能按视频查询；每次状态变更写历史。
- [ ] 运行 `python -m pytest -q tests/test_action_tasks_api.py`，确认缺接口而失败。
- [ ] 在 `SQLiteRepository.initialize()` 建 `action_tasks` 和 `action_task_updates`，增加 `create_action_task`、`list_action_tasks`、`get_action_task`、`append_action_task_update`；更新操作在一次事务内改状态与插入历史。
- [ ] 在 `api.py` 定义 `ActionTaskCreateRequest`、`ActionTaskUpdateRequest`，新增 `GET/POST /api/action-tasks`、`GET /api/action-tasks/{task_id}`、`POST /api/action-tasks/{task_id}/updates`；Pydantic 约束长度、非负秒数和枚举，服务端检查时区日期、必填说明及 Track ID 属于绑定视频。
- [ ] 聚焦测试变绿后提交 `feat: add action task API`。

### Task 2: 视频结果内创建和查看事项

**Files:** `web/src/api.ts`、`web/src/ActionTaskPanel.tsx`、`web/src/ActionTaskPanel.test.tsx`、`web/src/RecognitionStudio.tsx`、`web/src/workspace-interactions.css`

- [ ] 写组件失败测试：已完成视频可提交标题、负责人、截止时间和可选视频内 ID/秒数；提交后显示新事项；切换视频时不混入旧事项；错误可见。
- [ ] 运行 `npm test -- --run src/ActionTaskPanel.test.tsx`，确认失败。
- [ ] `api.ts` 新增事项类型及 fetch/create/update 客户端；`ActionTaskPanel` 在视频结果里使用选中 `job.id` 查询与创建事项；只在已完成视频显示。
- [ ] 组件测试和构建通过后提交 `feat: create action tasks from video results`。

### Task 3: 全局待办和证据回跳

**Files:** `web/src/ActionTaskInbox.tsx`、`web/src/ActionTaskInbox.test.tsx`、`web/src/App.tsx`、`web/src/workspace-interactions.css`

- [ ] 写组件失败测试：待处理、逾期、待复查按当前事项数据计算；状态和负责人筛选；保存状态后历史可见；点击“打开视频证据”选中绑定任务。
- [ ] 运行 `npm test -- --run src/ActionTaskInbox.test.tsx`，确认失败。
- [ ] 新增工作区“处置待办”入口；回跳复用 `App.openInventoryVideo` 的任务读取与结构校验逻辑，避免仅凭 `200` 打开错误视频。
- [ ] 组件测试、全量前端测试和构建通过后提交 `feat: add action task inbox`。

### Task 4: 验收与交接

**Files:** `README.md`、`docs/2026-10-22-action-followup-acceptance.md`、`HANDOFF.md`

- [ ] 在隔离 SQLite/浏览器走通创建、处理中、待复查、关闭与视频回跳，确认正式数据库不变。
- [ ] 运行全量 `python -m pytest -q`、`npm test -- --run` 和 `npm run build`；记录真实结果。
- [ ] 更新使用说明、验收记录和 HANDOFF 六节，分别提交文档与交接；审查分支后合入 `integration`，再次运行测试。

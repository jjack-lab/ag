# 本机网站完整接入实施计划

> 按 TDD 小步实现；每个单元测试绿色后提交。设计见 `docs/superpowers/specs/2026-10-25-local-full-site-integration-design.md`。

**目标：**本机网站实际启用羊专用模型、提供限定三类的牛行为研究入口，并验收档案、盘点与一键启动。

**架构：**模型注册表固定 SHA-256；牛羊检测按 `class_id` 分流，任务记录实际模型；三类行为走独立研究 API，不污染日常行为/健康链路。React 根据 API 状态显示入口和结果。

**技术栈：**Python/FastAPI/PyTorch/Ultralytics、React/TypeScript/Vite、SQLite、PowerShell。

## Task 1：检测模型分流

**Files:** `cattle_health_app/model_registry.py`、`cattle_health_app/media_processor.py`、`cattle_health_app/jobs.py`、`cattle_health_app/tracking_pipeline.py`、`cattle_health_app/api.py`、`delivery_tests/test_sheep_model_routing.py`。

- [ ] 写测试：牛用交付权重，羊用固定哈希候选；候选缺失/摘要不符不谎称启用；任务 JSON 保存实际模型。
- [ ] 跑聚焦测试确认失败。
- [ ] 实现注册表、按类分流和元数据持久化。
- [ ] 跑聚焦测试和现有媒体/任务测试，提交。

## Task 2：三类行为研究入口

**Files:** `cattle_health_app/behavior/research_runtime.py`、`cattle_health_app/api.py`、`delivery_tests/test_behavior_research_api.py`。

- [ ] 写测试：固定 checkpoint 哈希；中央两秒 16 帧；仅输出三类概率；缺失模型与无效视频返回清楚错误。
- [ ] 跑聚焦测试确认失败。
- [ ] 实现单独推理与 `/api/research/cattle-behavior`、状态接口。
- [ ] 跑聚焦测试并提交。

## Task 3：网页实际入口

**Files:** `web/src/api.ts`、`web/src/RecognitionStudio.tsx`、`web/src/CrossDomainResults.tsx`、相关前端测试及 CSS。

- [ ] 写测试：羊任务显示实际模型；研究短片入口的结果仅展示三类；模拟档案/盘点可见。
- [ ] 跑测试确认失败。
- [ ] 实现请求、状态和页面；保留旧指标与警示。
- [ ] 跑前端全量与构建，提交。

## Task 4：本机运行验收

**Files:** `docs/` 验收记录、`HANDOFF.md`；不提交第三方权重、数据、数据库。

- [ ] 后端全量、前端全量、前端构建。
- [ ] 检查启动脚本现有进程状态，启动本机服务并验证 8000/5173；通过 API 与浏览器验收四块内容及新羊视频任务。
- [ ] 记录真实结果、限制和停止方法；更新 `HANDOFF.md` 六小节并提交。

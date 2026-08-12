# 星牧智控整合版 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `F:\new大创` 交付可独立运行的图片检测、视频跟踪和规则型健康风险监测系统。

**Architecture:** 复用已通过验收的 FastAPI + React 应用层，以 SQLite 记录任务和告警，以 YOLO11s + ByteTrack 完成检测与跟踪。只迁入必要源码、测试、模型和固定验收媒体，并将所有路径收敛到新项目根目录。

**Tech Stack:** Python 3.8、FastAPI、Uvicorn、Ultralytics YOLO11、OpenCV、SQLite、React 18、TypeScript、Vite、Vitest。

---

### Task 1: 建立独立源码基线

**Files:**
- Copy: `cattle_health_app/**`
- Copy: `health_monitor.py`
- Copy: `inference_profile.py`
- Copy: `run_api.py`
- Copy: `delivery_tests/**`
- Copy: `tests/**`
- Copy: `web/src/**`
- Copy: `web/package.json`, `web/package-lock.json`, `web/tsconfig*.json`, `web/vite.config.ts`, `web/index.html`
- Create: `.gitignore`

- [ ] 创建独立 Git 仓库并确认工作树仅位于 `F:\new大创`。
- [ ] 复制上述自研源码与测试，排除缓存、依赖目录和历史输出。
- [ ] 复制 README、第三方数据说明和行为数据准备说明。
- [ ] 检查源码中不存在指向两份原项目的硬编码绝对路径。
- [ ] 提交源码基线。

### Task 2: 接入并验证模型

**Files:**
- Create: `models/detection/yolo11s-waid.pt`
- Modify: `cattle_health_app/model_registry.py`
- Test: `delivery_tests/test_model_registry.py`

- [ ] 运行现有模型注册测试，记录迁移前预期失败原因。
- [ ] 从 E 盘训练产物复制 YOLO11s 最佳权重。
- [ ] 验证 SHA-256 等于 `46d734cba7553f31e89e739156f50e9a675b176f798c70159838497531771a64`。
- [ ] 若模型注册仍依赖原路径，先补充失败测试，再改为项目相对路径。
- [ ] 运行模型注册测试并提交。

### Task 3: 独立化运行目录与启动脚本

**Files:**
- Modify: `run_api.py`
- Create: `start_delivery.ps1`
- Create: `requirements.txt`
- Create: `data/media/uploads/.gitkeep`
- Create: `data/media/results/.gitkeep`
- Test: `delivery_tests/test_delivery_api.py`

- [ ] 运行 API 测试，确认数据库、上传和结果目录从项目根目录推导。
- [ ] 为发现的绝对路径行为写失败测试。
- [ ] 使用相对目录和可选环境变量实现最小修复。
- [ ] 运行 API 测试确认通过。
- [ ] 执行 `start_delivery.ps1 -CheckOnly`，预期输出 `Delivery preflight passed.`。
- [ ] 提交运行基线。

### Task 4: 验证后端功能链路

**Files:**
- Test: `delivery_tests/**`
- Test: `tests/**`

- [ ] 执行 `python -m pytest delivery_tests -q -p no:cacheprovider`。
- [ ] 执行与媒体、健康规则、API、仓储相关的 `tests`。
- [ ] 对每个失败先定位根因并写最小回归测试。
- [ ] 一次只修一个根因，直至相关测试通过。
- [ ] 提交后端修复。

### Task 5: 验证 React 控制台

**Files:**
- Test: `web/src/App.test.tsx`
- Test: `web/src/test/setup.ts`
- Modify when required: `web/src/*.tsx`, `web/src/api.ts`, `web/src/styles.css`

- [ ] 在 `web` 执行 `npm ci`，只生成本地依赖目录。
- [ ] 执行 `npm test -- --run --reporter=dot`。
- [ ] 对界面/API契约失败先保留失败测试，再最小修复。
- [ ] 执行 `npm run build`，确认 TypeScript 和 Vite 生产构建通过。
- [ ] 提交前端验证结果。

### Task 6: 真实图片和视频验收

**Files:**
- Create: `data/verification/input/*`
- Create: `outputs/acceptance/*`
- Copy/Modify: `scripts/run_delivery_acceptance.py`

- [ ] 复制一张固定 WAID 测试图片和一段小型验收视频，不复制完整数据集。
- [ ] 启动 API 并轮询 `/api/health` 和 `/api/models`，确认服务与模型就绪。
- [ ] 通过 API 上传图片，确认带框图片可读取且至少包含一个检测结果。
- [ ] 通过 API 上传视频并轮询至完成。
- [ ] 校验输出视频可打开、输入输出帧数一致、轨迹 CSV 非空。
- [ ] 校验告警 CSV、健康汇总 CSV、HTML 报告和 SQLite 记录一致。
- [ ] 保存机器可读验收 JSON，停止测试服务并提交。

### Task 7: 完成交付文档

**Files:**
- Create: `README.md`
- Create: `README_DELIVERY.md`

- [ ] 写明首次安装、一键预检、启动命令和浏览器地址。
- [ ] 写明图片、视频、跟踪、健康风险和导出功能的操作步骤。
- [ ] 写明健康风险不是疾病诊断以及当前功能边界。
- [ ] 写明验收命令和最新实际结果。
- [ ] 从空闲终端按文档再次执行预检。
- [ ] 提交最终交付文档。

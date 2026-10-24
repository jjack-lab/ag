# 网站模块补齐 Implementation Plan

> 执行方式：在当前会话按 executing-plans 逐项实施；用户已批准推荐范围 A。每项经过失败测试、实现、通过验证后提交。

**Goal:** 接通档案、告警、分析、工作台和浏览器摄像头录像识别。

**Architecture:** 保留 React + FastAPI + SQLite，查询扩展放入独立 workspace API 模块；复用现有详情、回访、任务和视频管线。统计读取完整数据库，按 Asia/Shanghai 自然日计算。

**Tech Stack:** Python、FastAPI、SQLite、React、TypeScript、MediaRecorder、pytest、Vitest。

## Task 1：查询接口

- [x] 新增 `tests/test_workspace_api.py`：空目录、牛羊筛选、编号字面搜索、31 个视频的全量汇总、日期和 CSV 一致性。
- [x] 运行 `python -m pytest tests/test_workspace_api.py -q` 确认新路由缺失。
- [x] 新增 `cattle_health_app/workspace_api.py`，在 `api.py` 注册 `/api/animals`、`/api/analytics`、`/api/analytics.csv`。目录从已关联动物聚合，统计按视频创建、告警发生、事项创建与完成更新分别计数。
- [x] 运行聚焦测试与已有 web API 测试，提交此单元。

## Task 2：独立档案与告警

- [x] 新增前端关键交互测试：独立档案加载详情并保存回访；告警关闭回读与历史筛选。
- [x] 新增 `AnimalDirectory.tsx` 和可复用档案详情，使用已有 `fetchAnimalProfile`、`createAnimalFollowup`，保留原视频关联功能。
- [x] 新增 `AlertCenter.tsx`：状态/风险筛选、处置说明关闭、已处理历史、原视频跳转和从告警创建既有核查事项；扩展 `api.ts`。
- [x] 接入 `App.tsx`，运行前端测试与构建，提交此单元。

## Task 3：统计与工作台

- [x] 新增统计日期筛选、CSV 链接与最近任务跳转测试。
- [x] 新增 `WorkspaceAnalytics.tsx` 和 `RecentWork.tsx`；分析包含按日统计、同机位空间查询与原视频入口，CSV 参数与所见日期一致。
- [x] App 刷新入口与识别完成回调重新查询指标；保留评测中心。
- [x] 运行前端测试与构建，提交此单元。

## Task 4：摄像头录像

- [x] 新增 `CameraCapture.test.tsx` 验证权限失败、录制完成生成视频文件和离开释放设备。
- [x] 新增 `CameraCapture.tsx`，只在点击时请求视频权限；预览、开始、停止、重录、使用录像；MediaRecorder 结束生成 File，送入识别工作台同一上传入口。
- [x] `RecognitionStudio.tsx` 显示选中录像并沿用视频识别参数和进度；清除旧结果，不自动重复提交。
- [x] 运行前端测试与构建，提交此单元。

## Task 5：集成与交接

- [x] 全量后端/前端测试、生产构建；浏览器核对档案、告警、统计与摄像头入口。写操作用隔离数据。
- [x] 重启本地 API 使新路由生效，请求真实接口并核对结果。
- [x] 更新本计划、核查记录和 `HANDOFF.md`，记录设备与现场数据仍需验证的边界，提交。

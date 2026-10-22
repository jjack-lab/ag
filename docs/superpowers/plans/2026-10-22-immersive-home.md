# 沉浸式首页 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前首页改为 Planet Jumping 风格的牧场沉浸式入口，同时保持工作台功能。

**Architecture:** `App.tsx` 管理入口交互与现有工作台路由；独立 CSS 文件负责首屏场景、响应式样式和减少动态效果；现有 API 与业务组件不改动。

**Tech Stack:** React 18、TypeScript、Framer Motion、CSS、Vitest。

---

### Task 1: 入口交互

**Files:** `web/src/App.test.tsx`, `web/src/App.tsx`

- [ ] 在 `App.test.tsx` 增加断言：首页有“进入健康控制中心”入口，点击后切换到今日工作台并定位工作区；同时“查看识别能力”和“查看健康分析与报告”仍存在。
- [ ] 在 `web/` 运行 `npm test -- --run src/App.test.tsx`，确认新断言先失败。
- [ ] 在 `App.tsx` 使主入口触发约 550 毫秒的进场状态，随后调用现有 `openView("overview")`；减少动态效果时直接调用。保留其它入口。
- [ ] 再运行聚焦测试，确认通过。

### Task 2: 首屏视觉

**Files:** `web/src/App.tsx`, `web/src/site-refresh.css`, `web/src/particle-field.css`, `web/public/hero-cattle.jpg`

- [ ] 将现有牛开发素材静帧复制为 `web/public/hero-cattle.jpg`，不做假证据处理。
- [ ] 把双栏首屏改为全屏背景、巨型标题、中央主入口、少量场景说明及演示素材标签；工作台组件不变。
- [ ] 在 CSS 中实现缓慢镜头感、粒子层、入口推进、手机适配与 `prefers-reduced-motion` 跳过动效。
- [ ] 运行 `npm test -- --run` 和 `npm run build`。
- [ ] 用浏览器检查首页、入口转场与工作台，并修复实际发现的问题。
- [ ] 更新 `HANDOFF.md`，提交一个可验证的改动单元。

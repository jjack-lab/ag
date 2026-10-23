# Module Routes And Entrance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将星牧智控改为带 Planet Jumping 风格入场的模块化网站。

**Architecture:** 用 `web/src/moduleRoutes.ts` 解析与生成 hash 地址；`App.tsx` 只渲染当前首页、模块选择页或当前业务模块。`module-navigation.css` 与 `immersive-home.css` 负责转场和模块入口。保留既有 API 与业务组件。

**Tech Stack:** React 18、TypeScript、Framer Motion、CSS、Vitest。

---

### Task 1: 地址状态与模块隔离

**Files:** `web/src/moduleRoutes.ts`, `web/src/moduleRoutes.test.ts`, `web/src/App.tsx`, `web/src/App.test.tsx`, `web/src/module-navigation.css`

- [ ] 测试 `parseModuleHash()`：空 hash 为首页，`#/modules` 为模块选择页，`#/module/health` 等八个名字为模块页；无效名字回首页。
- [ ] 跑聚焦测试，确认缺少路由函数时失败。
- [ ] 实现上述纯函数和 `moduleHref()`，在 `App.tsx` 监听 `hashchange` 并根据路由条件渲染页面；导航时写入 hash。
- [ ] 在 App 测试中先写直达模块、切换模块、返回与概览不平铺识别工作台的失败断言，再实现最小交互。
- [ ] 跑聚焦测试并提交 `feat:` 小步提交。

### Task 2: 加载层和穿越入口

**Files:** `web/src/App.tsx`, `web/src/App.test.tsx`, `web/src/immersive-home.css`, `web/src/module-navigation.css`

- [ ] 先写测试：主页有加载状态，结束后中央入口可点击；点击入口进入 `#/modules`，减少动态效果时立即进入。
- [ ] 跑聚焦测试确认失败；实现一次性 0–100% 短加载、圆角入口缩放至全屏、菜单页入场。
- [ ] 用浏览器检查首页转场、模块卡片、直达地址、返回和手机宽度；修复实际问题。
- [ ] 运行 `npm test -- --run` 和 `npm run build`；记录后端未改动，更新 `HANDOFF.md` 和验收记录，提交并合入 `integration`。

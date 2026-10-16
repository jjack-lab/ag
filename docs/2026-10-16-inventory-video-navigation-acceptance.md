# 圈舍盘点打开视频证据：浏览器验收记录

- 验收日期：2026-10-16
- 浏览器验收代码基线：`b5b1e07`（含 `962e615`、`0cfd5d8` 与导航状态清理修复）
- 最终代码基线：`4023d75`（另含异常视频任务响应校验，不改变已验收的正常导航路径）
- 验收任务：`47de2b7fbb534f948296dbf8dc5dc1c4`
- 任务类别：牛
- 任务结果：210 帧、视频内 Track ID 26 个

## 隔离边界

验收服务使用 `data/agrinebula.db` 的 SQLite 备份 `data/verification/browser-acceptance.db`，只在备份中新增一条圈舍盘点记录：

- 圈舍：`隔离验收圈舍-A`
- 绑定任务：`47de2b7fbb534f948296dbf8dc5dc1c4`
- 登记存栏和人工清点：均为 26
- 验收服务：`http://127.0.0.1:8001/`

正式数据库没有写入验收数据。浏览器操作后再次核对：

- 正式 API `GET http://127.0.0.1:8000/api/inventory-checks`：0 条；
- 正式 SQLite `data/agrinebula.db` 的 `inventory_checks`：0 条；
- 隔离 API 与隔离 SQLite：各 1 条；
- 验收结束后 8001 服务已停止。

隔离数据库、CDP 脚本、结构化请求记录和截图均位于被 Git 忽略的 `data/verification/`，不会进入交付数据。

## 浏览器操作与结果

使用 Chrome 无头模式和 CDP 对生产构建执行真实 DOM 点击：

1. 打开隔离服务首页；
2. 点击左侧“圈舍盘点”；
3. 确认历史列表显示“隔离验收圈舍-A”；
4. 点击该卡片的“打开视频证据”；
5. 页面切换到“实时监控”；
6. 结果区显示“视频内 Track ID：26 个”；
7. `牛只视频追踪结果` 播放器的 `src` 为：
   `/media/results/47de2b7fbb534f948296dbf8dc5dc1c4/6f05b14731084efb91be0f3e6b6859b0_tracked.mp4`。

截图：`data/verification/inventory-video-navigation.png`。

结构化浏览器结果：`data/verification/inventory-video-navigation.json`。

## 同任务请求证据

浏览器点击后抓到以下 GET 请求，任务相关请求均绑定同一个 job ID：

- `/api/inventory-checks`
- `/api/jobs/47de2b7fbb534f948296dbf8dc5dc1c4`
- `/media/results/47de2b7fbb534f948296dbf8dc5dc1c4/6f05b14731084efb91be0f3e6b6859b0_tracked.mp4`
- `/api/jobs/47de2b7fbb534f948296dbf8dc5dc1c4/events`
- `/api/jobs/47de2b7fbb534f948296dbf8dc5dc1c4/corrections`
- `/api/jobs/47de2b7fbb534f948296dbf8dc5dc1c4/animal-links`
- `/api/jobs/47de2b7fbb534f948296dbf8dc5dc1c4/reviews`

这证明历史盘点卡片打开的是其绑定视频任务，并沿用现有结果、事件、纠错、个体关联和复核链路。

## 自动化验证

- 后端全量：`661 passed, 4 skipped`（同一最终代码基线由主任务运行）；
- 前端全量：12 个测试文件、`46 passed`；
- 前端生产构建：成功，Vite 转换 2186 个模块。

浏览器验收后的代码审查又补充了 8 项异常响应回归测试：`null`、缺少字段、未知状态、非有限进度及空结果对象均会留在盘点页并统一提示“视频证据加载失败”。代码审查同时核对正式 SQLite 中 4 个历史完成任务，均满足新增格式校验。

## 已知限制

全局“圈舍盘点”目前读取最近 100 条记录，没有分页、条件筛选或更早记录查询。视频内 Track ID 仍只用于画面定位，不能代替人工存栏清点，也不能跨视频当作永久动物身份。

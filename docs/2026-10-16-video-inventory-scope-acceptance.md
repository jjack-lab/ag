# 旧视频盘点记录按任务查询验收

- 日期：2026-10-16
- 实现提交：`a348782`（服务端）、`89622d6`（网页）
- 目标视频任务：`47de2b7fbb534f948296dbf8dc5dc1c4`，既有已完成牛视频

## 隔离数据与可复核结果

在正式 `data/agrinebula.db` 的备份 `data/verification/browser-acceptance.db` 中创建目标任务的 1 条旧盘点“旧视频盘点-可见”，再为另一条隔离任务创建 101 条更新的盘点。旧无参 `GET /api/inventory-checks` 返回最近 100 条，目标记录不在其中；`GET /api/inventory-checks?job_id=47de2b7fbb534f948296dbf8dc5dc1c4` 返回目标记录且没有其他任务记录。

Chrome 对隔离服务生产构建执行真实点击：全局“圈舍盘点”输入圈舍编号定位旧记录，点击“打开视频证据”，在“实时监控”的结果播放器下方看到“旧视频盘点-可见”卡片。抓到页面发起的带 `job_id` 盘点请求。截图和结构化结果保存在被 Git 忽略的：

- `data/verification/video-inventory-scope.png`
- `data/verification/video-inventory-scope.json`

正式 SQLite 和正式分页 API 均保持 0 条盘点记录；隔离库 102 条，8001 验收服务结束后已停止。视频内 Track ID 只作画面定位参考，不作为存栏数或个体永久身份。

## 自动化验证

- 后端全量：`664 passed, 4 skipped`
- 前端全量：`49 passed`
- 前端生产构建：成功

无参数数组接口保留最近 100 条的兼容行为，全局历史页继续使用分页接口；结果页使用按任务查询的完整数组。

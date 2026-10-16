# 圈舍存栏核对浏览器验收（2026-10-15）

## 验收对象

- 代码：`b7a1ea8` 后端 API、`d7faddf` 网页入口。
- 页面：新建盘点同时出现在已完成视频下方与左侧“圈舍盘点”导航。
- 数据：将正式 `data/agrinebula.db` 通过 SQLite backup 复制为被 Git 忽略的 `data/verification/browser-acceptance.db`，只在本地 8001 服务提交验收记录。正式数据库没有 `inventory_checks` 表；隔离副本有 2 条浏览器验收记录。

## 实际操作和结果

1. Chrome 打开隔离服务 8001；首页显示最近牛视频 26 个视频内 Track ID。左侧“圈舍盘点”可打开记录总览；切回“实时监控 → 视频识别”，重开已完成牛视频。
2. 在视频结果下方填写登记数 10、人工清点数 8、完整拍摄覆盖、台账来源和操作人；点击“保存盘点”。页面与 API 均显示差额 2、`discrepancy_pending`，并提示待复点。视频的 26 个 Track ID 单列为“仅参考”，没有当作存栏数。
3. 在该记录上点击“填写人工复核”，填复点 8、人工登记丢失 1、复核人和说明，并勾选已核对出入栏记录、已完成现场查找。页面显示“人工登记丢失 1”，API 回读 `loss_user_recorded`、`lost_count=1`、两项核查均为 `true`、`verification_status=user_recorded`。
4. 浏览器截图保存于被 Git 忽略的 `data/verification/inventory-browser.png`；此截图只证明开发样例上的操作流程，不代表牧场实际发生丢失。

## 验证与边界

- 审查补充发现并修复“首次人工清点为空仍可直接提交复核”的漏洞：后端现在拒绝此类请求，前端不显示复核入口；人工清点为 0 仍与未填写严格区分。页面首版明确展示最近 100 条盘点。
- 修复后全量：后端 661 passed、4 skipped；前端 30 passed；`npm run build` 成功。
- 接口拒绝未完成视频、负数、无时区时间；不完整覆盖禁止复核；人工丢失必须有小于等于差额的数量和两项核查。相关测试在 `tests/test_inventory_api.py` 和 `web/src/InventoryPanel.test.tsx`。
- 登记数、拍摄完整性、出入栏核查和现场查找目前由人员录入，系统无法独立证明其真实。牛开发视频的 Track ID 不能用来验证牧场存栏或损失。正式使用前还需要授权牧场原视频、现场台账与实地复核。

# 演示档案与盘点记录

2026-10-25 经用户允许在本机演示数据库 `data/agrinebula.db` 写入模拟数据。写入前通过 SQLite 在线备份到 `data/verification/demo_seed_backup_20261025.db`；数据库和备份均被 Git 忽略，不随代码分发。

- 关联已完成的牛视频任务 `202d89f9aaad433480d8570bd90c3d41` 的 Track 1、2，生成 `DEMO-COW-001/002` 两份**模拟档案**。编号不代表经过现场确认的耳标或永久身份。
- 为同一任务生成 `DEMO-PEN-01/02` 两条**模拟盘点记录**。模拟台账数为 4、6；拍摄覆盖均为 `unknown`，人工清点数留空。不能据此判断差额、丢失或真实存栏。
- 页面基于 `DEMO-` 前缀显示“模拟数据、未经现场核实”；盘点来源与覆盖说明也写明模拟性质。

脚本 `scripts/seed_demo_records.py` 默认只预览，带 `--apply` 时先备份再写入；同一任务重复调用的核心写入函数不会产生重复记录。脚本拒绝缺少 Track 1/2 的视频或覆盖同一 Track 已有的真实关联。若要恢复到写入前，可先停止服务，再以备份替换本机数据库；替换会回退备份之后的其他写入，应先另存现状。

```powershell
F:\deepl\anaconda1\envs\pytorch\python.exe -m scripts.seed_demo_records --database data/agrinebula.db --job-id 202d89f9aaad433480d8570bd90c3d41
```

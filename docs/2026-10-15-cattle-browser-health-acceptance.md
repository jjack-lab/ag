# 牛视频健康证据图谱浏览器验收（2026-10-15）

## 数据与隔离

使用既有开发样例 `data/verification/input/waid_cattle_static_acceptance.avi`，SHA-256 `8a7c40a3cf8c2996bb1b4085ef222b3d39695a1d7d56b05d773861a55bfba68c`。这是已用过的静态牛视频，不能算新牧场独立验收。通过隔离 SQLite 副本上的 8001 服务向真实 `POST /api/jobs/video` 上传，使用交付默认模型、牛类、ByteTrack、置信度 0.25、NMS IoU 0.45。任务 `125636b4627b46d09b564e3755b3b78b` 完成后关闭 8001；正式 8000 数据库未增加任务或规则提示。

## 实测结果

- 任务完成 210 帧、26 个视频内 Track ID、26 条规则提示、26 个健康证据链。数字是本段开发视频的轨迹和规则结果，不是全场存栏或真实病牛数。
- 新结果 `data/media/results/125636b4627b46d09b564e3755b3b78b/7a9cc365b02f40948aafcc02d1f6e406_tracked.mp4` 为 H.264，`ffprobe` 解码 210 帧，SHA-256 `ba1ffbfe579e73ff12ceb0b275b210d000bd8fb7539ea95be3554d1f33`。
- Chrome 从历史任务打开后看到 26 个证据链。第一个链条呈现“视频内 ID 1 → 持续低活动 20.0 秒 → 中风险 40 分 → 建议人工查看精神沉郁、跛行或采食异常”；播放器 `readyState=4`、时长 21 秒，播放约 2 秒后进度到 1.99 秒且未暂停。截图 `data/verification/cattle-browser-health-graph.png`，结构化浏览器结果 `data/verification/cattle-browser-health.json`，均为本机被 Git 忽略的运行产物。
- 关闭 8001 后，正式 8000 看板仍为最近牛视频 26 个 ID、历史未处理规则提示 84 条；隔离复跑没有把 26 条重复提示写入正式数据库。

## 边界

图谱连接的是视频内轨迹、规则观察和复核建议；此视频静态且已用于开发，无法证明新牧场泛化、疾病发生或未来发病时间。现场应用还需独立牧场视频、耳标或圈舍台账、人工复核与诊疗结果。

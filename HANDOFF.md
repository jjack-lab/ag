# HANDOFF.md — 交接台账

> 谁在干活谁维护。任何 AI 接手第一步：读完本文件 → `git log --oneline -10` + `git status` + `git worktree list` 核对 → 跑测试 → 从「下一步」清单继续。规则见 `AGENTS.md`。

- 最后更新：2026-10-22（新增行为局部放大人工复核，原帧、轨迹裁剪与复核记录已在演示视频验收；下方旧实验记录仅作历史参考。）

## 当前阶段目标

0.15. 对“无法确定”行为提供原视频全帧、Track ID 局部放大和上下文回看，支持人工结论单独留痕。后续用独立牧场视频与人员核对放大后究竟有多少片段可判读；不能把裁剪当成图像增强或模型自动纠错。

0.14. 已将真实拍摄的 21 秒牛开发视频接入首页一键演示，结果视频可在浏览器播放；演示只证明本机链路和界面。下一阶段仍需授权牧场固定机位长视频、台账及现场核对。

0.13. 当前四项短期产品功能的首版代码已实现：视频提示可展开截图/片段，手机宽度待办可快捷记录处置，固定机位画区可统计活动与同机位趋势，栏门画线可辅助计数和同日汇总。下一阶段需要真实固定机位牧场视频、出入栏台账与现场人员核对误差；在此之前不称为自动存栏真值或疾病预测。

0.11. 已按用户确认顺序实现视频问题到人工处置/复查闭环、拍摄补拍提示和一页式巡检摘要。保持 React + Python，不引入 PHP；只做必要输入校验，不堆叠防御性逻辑。

0.12. 三项短期功能均已有代码和前端测试；下一阶段用授权牧场视频与现场人员验证补拍建议、任务分派和摘要是否真正省时，再按反馈微调提示文案与打印样式。

0.10. 短期产品功能优先讨论“视频发现问题 → 人工核查任务 → 现场结果 → 关闭/复查”的处置闭环；用户尚未选定方案或批准设计，不能把讨论当成已实现功能。

0.9. 视频结果内的盘点记录已按当前任务完整查询，不再受全局最近 100 条窗口影响；下一步用授权牧场原视频、真实台账和现场复点检验产品实际使用效果。

0.8. 圈舍盘点历史可翻页和筛选，便于回看旧视频证据；下一步需授权牧场原视频、真实圈舍台账和现场复点，检验完整拍摄、漏拍和差额复核在实际使用中的表现。

0.7. 用授权牧场原视频和真实圈舍台账完成现场验收；历史盘点到绑定视频证据的回看链路已贯通，下一步验证真实操作人员能否凭视频、台账和复点记录快速定位问题。

0.6. 用授权牧场原视频、真实圈舍台账和现场复点验证圈舍存栏核对流程；在此之前，所有差额和丢失结论保持人工记录来源，不把视频 Track ID 当作存栏真值。

0.5. 在不把不完整视频或临时 Track ID 当作存栏真值的前提下，设计圈舍存栏核对与差额提醒。系统须记录期望数量、拍摄覆盖、人工核对结果和回访结论；未确认前只能提示待复核。

0.4. 网页结果视频、同源评测卡片、浏览器纠错/复核与下载操作已完成验收；证据链须保留，不能只凭 HTTP 状态。

0.3. 以牧场管理和经济损失减少为验收目标：先让视频任务、评测、复核与看板使用真实且清楚的口径；然后建设需完整覆盖与人工确认的存栏差额提醒。现有单视频 Track ID 不能当永久身份，公开羊视频也不能证明可判断疾病或丢失。

0.2. 将公开羊视频识别的真实效果与失败边界直观展示给用户；产品默认模型和外部羊专用模型明确区分，下一步再决定是否在 UI 提供可选模型。无人机位移未补偿，视频中只称“画面位移”。

0.1. ICAERUS 羊视频与标注已就绪，下一目标是在现有识别工作台真实处理其中一段，并导入同源标注计算外部检测/追踪指标；保留无人机俯视与目标牧场机位的域差异说明。

0. 先完成可演示、可纠错、可追溯的牛羊视频产品链路，再用有出处且未参与开发的数据做独立验收。当前页面只把牛规则结果称为风险辅助筛查，把羊轨迹位移称为活动摘要；不输出具体疾病或发病时间。

0. 产品演示链路：用牧场视频展示牛只检测、追踪、规则风险证据链与人工复核；羊先展示检测追踪。具体疾病预测、发病时间和羊健康评分须待标注及独立验证。

0.1. 当前产品优先级：取得未参与开发的牧场牛羊原视频并做现场验收；持续收集跨天耳标关联、复核结果和带出处的诊疗记录，形成可检验的病例数据。

1. 保留已完成的 CBVD4 冻结三臂实验及负晋级结论，禁止依据当前 test 结果换候选或调参。
2. 完成多 seed validation 矩阵（两种初始化 × seeds 20260824/20260901/20260908），只在开发集 train/val 上进行。
3. WAID4500 目标检测基线完成可复现封装（清单、哈希、环境、训练入口、验证器），随后在冻结基线上开展预注册的精度改进实验。
4. 大创申报材料定稿并入库；主线 `integration` 保持测试绿色、随时可演示。

## 已完成

- 2026-10-22：行为局部放大人工复核首版完成。牛视频结果页可选 Track ID 和时间，查看原帧与同帧轨迹框附近裁剪，回看视频并保存人工行为结论或“仍无法判断”。正式演示任务浏览器加载原帧 640×640、局部 101×101；未写正式复核数据。见 `docs/2026-10-22-behavior-zoom-review-acceptance.md`。后端 672 passed / 4 skipped，前端 59 passed，构建成功。

- 2026-10-22：核查本地训练集对区域活动与栏门计数的适用性。CBVD-5 的 687 段原视频在 `.worktrees/cross-domain-behavior/data/external/cbvd5/raw/videos/videos/`，逐文件时长均约 10 秒；`272.mp4` 为固定画面、前侧饲槽可见，可演示单段“饲槽附近观察区”画区与轨迹统计，但不能验证多日趋势。抽看采食/饮水及室内候选后未找到可确认的完整栏门经过；羊无人机视频镜头移动。证据与搜索范围见 `docs/2026-10-22-training-video-zone-gate-audit.md`。

- 2026-10-22：按用户要求，从已有牛开发素材 `data/verification/input/waid_cattle_static_acceptance.avi` 取 21 秒真实拍摄视频，通过正式本地 API 重新运行模型，生成任务 `202d89f9aaad433480d8570bd90c3d41`。首页新增“真实拍摄牛视频 · 开发素材演示”一键入口和来源提示。H.264 结果 210 帧、26 个视频内 ID、26 条规则提示；浏览器播放器实际解码并播放超过 2 秒。截图和哈希见 `docs/2026-10-22-cattle-training-video-demo.md`。入口只对当前本机数据库有效，训练素材不算独立牧场验收。接手基线后端 671 passed / 4 skipped，完成后前端 58 passed、构建成功。

- 2026-10-22：新增事件截图接口和时间轴内的前后片段预览，全局告警可打开绑定视频；处置待办提供“已查看/误报/已处理”快捷表单，备注仍由人工确认并记入既有历史。新增固定机位空间分析：在结果视频拖画采食/饮水矩形或栏门线，按轨迹记录进入次数、停留时间、穿线方向及时间；可沿用同机位画区，同日栏门汇总，长视频按每小时频率与过去 7 天同画区视频比较。连续 30 秒画区无检测或栏门视频相对开头持续明显减少时，生成待核查事件并复用截图、片段和人工事项链路。正式网页已显示新面板，旧牛视频事件截图实际展开；聚焦 7 passed，后端全量 671 passed / 4 skipped，前端 57 passed，构建成功。固定机位真实数据验收未做。

- 2026-10-22：拍摄检查读取本地视频时长/分辨率，短于 10 秒或短边低于 480 像素时建议补拍，不阻止识别；无法自动判断覆盖或疾病。已完成视频的一页式巡检摘要可按需读取人工复核及核查事项、显示结果视频链接并打印。前端全量 55 passed、构建成功；新功能只改前端。

- 2026-10-22：两项前端功能已合入 `integration`。正常网页真实点击已完成羊视频“生成巡检摘要”，显示 99 帧、1 个视频内 ID、0 条规则提示及同任务视频链接，正式待办仍为 0；见 `docs/2026-10-22-capture-summary-acceptance.md`。主线前端 55 passed、构建成功。打印样式还需实际打印/PDF 查看。

- 2026-10-22：视频核查事项与处置待办首版完成。已完成视频可创建任务，带时间点的规则提示可预填 ID/秒数；全局待办可筛选、记录处理、设置复查时间、关闭并回跳视频。隔离 SQLite + 浏览器走通全程，三条处理历史可见；正式库未写入演示事项。旧牛结果视频为 MPEG-4，浏览器不能播放但可下载，见 `docs/2026-10-22-action-followup-acceptance.md`。后端全量 667 passed / 4 skipped，前端 52 passed，构建成功。

- 2026-10-22：修复视频盘点旧记录回归测试的固定未来日期。原测试将 101 条“较新”记录写死在 2026-10-17，10-22 运行时反而早于新建的目标记录；现相对目标 `created_at` 生成时间。修复前全量 663 passed / 1 failed / 4 skipped；修复后聚焦 1 passed、全量 Python 664 passed / 4 skipped，前端 49 passed。提交 `03f39cf`；未改生产逻辑。

- 2026-10-16：视频结果内盘点记录按任务查询完成。`a348782` 为旧数组接口新增可选 `job_id` 参数和参数化仓储查询，保持无参最近 100 条兼容行为；`89622d6` 让结果面板传入当前任务 ID，全局历史分页不变。回归测试构造目标旧记录加 101 条较新的其他视频记录，证实旧无参列表漏掉目标、按任务查询仍返回目标且不混入其他任务。隔离 SQLite + Chrome 真实点击“圈舍盘点 → 打开视频证据”，结果页显示“旧视频盘点-可见”并发起带该 `job_id` 的请求；正式库/API 仍为 0 条。完整后端 `664 passed / 4 skipped`，前端 `49 passed`，构建成功；验收见 `docs/2026-10-16-video-inventory-scope-acceptance.md`。

- 2026-10-16：全局圈舍盘点历史分页与筛选完成。`a49d2b2` 新增只读 `/api/inventory-checks/page`（每页默认 20、总数、offset、圈舍编号字面包含搜索、按最新复核状态筛选），保留旧数组接口；`378a56c` 增加总数、上一页/下一页及筛选控件，并防止旧请求覆盖新筛选；`721c472` 补排序和字面搜索测试。隔离库 25 条记录的 Chrome 实测为 20+5 两页、状态筛选 5 条、叠加圈舍筛选 1 条，点击卡片仍打开绑定牛视频。正式库/API 为 0 条，隔离 8001 已停止，截图和请求见 `docs/2026-10-16-inventory-history-pagination-acceptance.md`。后端全量 `663 passed / 4 skipped`、前端 `48 passed`、构建成功；正式 8000/5173 已重启。

- 2026-10-16：圈舍历史盘点打开视频证据完成。`962e615` 让识别工作台接收外部选中的已完成任务，`0cfd5d8` 增加历史卡片按钮、加载/错误状态和应用级导航，`b5b1e07` 修复离开后普通进入实时监控仍残留旧证据的问题；`85f94d7`、`4023d75` 对 HTTP 200 但结构异常的视频任务响应增加运行时校验和回归测试，异常时留在盘点页统一提示加载失败。隔离 SQLite 绑定既有完成牛任务 `47de2b7fbb534f948296dbf8dc5dc1c4`，Chrome 真实点击“圈舍盘点 → 打开视频证据”后切到“实时监控”，显示 26 个视频内 Track ID 和对应结果视频；抓到同 job ID 的任务、结果视频、事件、纠错、个体关联、人工复核与盘点请求。正式 API 和 SQLite 盘点记录均保持 0。后端全量 `661 passed / 4 skipped`，前端 `46 passed`，生产构建成功；验收记录为 `4643a9a`，详见 `docs/2026-10-16-inventory-video-navigation-acceptance.md`。

- 2026-10-16：圈舍存栏核对首版完成。`f4794be` 增加追加式盘点/复核存储和状态规则，`b7a1ea8` 增加受约束 API，`d7faddf` 增加视频结果页与全局“圈舍盘点”网页入口，`91a64b3` 要求首次人工清点完成后才能复核。完整覆盖后数量差额先显示待复点；登记丢失必须再填写复点数量、丢失数、复核人和说明，并确认已核对出入栏记录与完成现场查找。视频 Track ID 始终标为仅参考。隔离 SQLite + Chrome 实测“登记 10、清点 8 → 差额 2 待复点 → 人工登记丢失 1”，正式数据库未写入测试记录；审查补充的首次清点门槛回归测试已通过，证据见 `docs/2026-10-15-pen-inventory-browser-acceptance.md`。

- 2026-10-15：在隔离数据库服务重跑既有 210 帧牛开发视频 `125636b4627b46d09b564e3755b3b78b`，得到 26 个视频内 ID、26 条规则提示、26 个健康证据链。结果 MP4 为 H.264，`ffprobe` 解码 210 帧；Chrome 中图谱显示“ID → 持续低活动 20 秒 → 中风险 40 分 → 人工复核建议”，播放器进度约 2 秒后到 1.99 秒。截图和结构化结果在被忽略的 `data/verification/cattle-browser-health-*`，正式看板仍为 26 ID / 84 历史提示。详见 `docs/2026-10-15-cattle-browser-health-acceptance.md`。这是开发样例，不能支持疾病或泛化结论。
- 2026-10-15：圈舍存栏核对建议设计已提交 `d8d1ef6`，见 `docs/superpowers/specs/2026-10-15-pen-inventory-reconciliation-design.md`。明确视频 Track ID 不参与存栏差额计算，覆盖不足先补拍，完整覆盖后的数量差额先待复点，人工登记丢失须现场与出入栏核对证据。已向用户询问优先圈舍数、耳标或同时做，以及是否采用推荐设计；在答复前未写生产功能代码。

- 2026-10-15：在 SQLite 备份形成的隔离服务（8001）上，Chrome 真实操作羊视频“暂停并绘制漏检框”并保存，页面与隔离 API 回读 1 条非零框纠错；人工复核表保存 1 条标记为隔离验收的漏检记录；点击下载 H.264 结果视频、轨迹 CSV、纠错 CSV，均在浏览器下载目录落盘，MP4 哈希与结果视频一致。正式 8000 API 的纠错/复核均仍为 `[]`，隔离服务已停止，8000/5173 保持运行。证据、限制见 `docs/2026-10-15-browser-interaction-acceptance.md`；本轮接手基线后端 648 passed / 4 skipped、前端 27 passed。

- 2026-10-15：定位网页羊视频无法播放的根因：交付 OpenCV 结果为 MPEG-4 `mp4v`，Chrome 报 `DEMUXER_ERROR_NO_SUPPORTED_STREAMS`。新增结果视频和证据片段的 FFmpeg `libx264` 转换，成功时原子替换为 H.264，失败时保留原文件供下载。本机旧羊结果已备份并转码，`ffprobe` 确认 H.264 / 99 帧。Chrome 打开历史任务后 `readyState=4`、11 秒时长，播放 5 秒后进度到 4.9 秒且未暂停；页面截图在被忽略的 `data/verification/sheep-browser-playback.png`。同一浏览器“公开数据评测中心”卡片显示 `development`、1,956 GT、TP 2 / FN 1,954、Recall 0.1%、F1 0.2%，截图 `data/verification/sheep-browser-evaluation.png`。结果标题已从误导性的“已追踪 1 只羊”改为“视频内 Track ID：1 个”，前端 27 passed、构建成功，Chrome 重放成功。后端全量 648 passed / 4 skipped；服务已重启，代码 `51d4c21`、`6d2fec4`。详细记录见 `docs/2026-10-15-web-sheep-acceptance.md`。

- 2026-10-15：管理看板口径修正：`/api/dashboard` 取最近一次已完成牛视频的 Track ID 数及处理时间，未找到牛视频返回 `null`（页面显示“暂无记录”），真实零轨迹仍显示 0；高风险与未处理规则提示按历史未处理记录条数计。首页告警明示“视频内 ID”，“牛只档案”不再按跨视频临时 ID 自动合并。交付验收脚本、README、API 与前端测试同步更新。后端全量 646 passed / 4 skipped，前端 27 passed，构建成功。交付服务用 `AGRINEBULA_PYTHON=F:\deepl\anaconda1\envs\pytorch\python.exe` 重启后，真实 API 返回最近牛视频 26 个 ID、处理时间 `2026-09-29T17:47:46+08:00`、历史未处理提示 84 条；网页 HTTP 200。浏览器实际点击仍未核对。

- 2026-10-15：从网页上传 ICAERUS `crop_23.11.23-12.MP4` 创建任务 `b6584849f10c403c8a1404e8f91748b8`（羊、ByteTrack、conf 0.25、NMS IoU 0.45）。本地任务完成 99 帧、1 个 Track ID、0 牛规则告警；网页显示结果播放器、事件、纠错、复核和下载入口。浏览器文件选择器中断后，使用同一 `POST /api/evaluations` 接口导入 GT，评测 `9cc4bc9791364cfdbf9329e8e7a0dc2b` 返回 1956 GT / TP 2 / FP 0 / FN 1954 / Recall 0.102%，与离线默认模型值一致。结果视频 HTTP 200 且可解码 99/99 帧；详见 `docs/2026-10-15-web-sheep-acceptance.md`。`7890c0a` 记录证据、将已使用样本改标为 development，并忽略运行时评测标注文件。接手基线后端 644 passed / 4 skipped、前端 26 passed。
- 2026-10-15：核查官方羊 YOLO11n 模型说明和仓库 LICENSE：仓库为 GPL-3.0，模型未见单独许可；官方列出五个 Roboflow 数据集及 Zenodo 18889623 羊图像集作为训练来源，没有明确列出本次 12094356 视频，但同项目原始素材的重叠无法逐帧排除。结论与官方链接追加至 `docs/2026-10-15-web-sheep-acceptance.md`；仍不安装到网页默认模型或声称独立验证。

- 2026-10-14 在 ICAERUS `crop_23.11.23-12.MP4`（99 帧、1,956 GT 框）实跑两次：本项目默认检测模型 TP=2、FN=1954、Recall=0.10%；ICAERUS 官方 YOLO11n 羊权重 TP=1722、FP=257、FN=234、Precision=87.01%、Recall=88.04%、F1=87.52%、匹配帧 ID 切换 2（本项目 pipeline + ByteTrack；评测 IoU≥0.5）。官方权重 Git blob 校验通过，未替换产品默认权重。`27284a2` 新增可复用羊视频证据面板渲染器与测试；H.264 视频 `data/verification/icaerus_sheep_20261014/icaerus_yolo11n/crop_23.11.23-12_demo.mp4` 共 99 帧并全部解码，面板显示小号框、ID、部分置信度、逐帧计数、未补偿镜头运动的画面位移及边界。完整测量与哈希见 `docs/2026-10-14-icaerus-sheep-model-demo.md`，`evaluation.json` 在同一验证目录。最后全量后端 `644 passed, 4 skipped`、前端 26 passed、构建成功。

- 2026-10-14 下载并核对官方 [Zenodo 12094356](https://zenodo.org/records/12094356) 数据包：157,760,285 字节，MD5 `1ec2048d4975f5d68e04c3229cb03d40` 与官方一致，ZIP CRC 无错误；内有四段羊 MP4（合计 639 帧）及同后缀 MOT 标注（合计 14,365 框）。四段均逐帧完整解码，GT 覆盖相应全部帧，框在画面内且同帧 ID 不重复。生成四份本项目评测 CSV（MOT 帧号减一、羊类 ID 0、像素框归一化），原始包与衍生文件均在被 Git 忽略的 `data/external/sheep_zenodo_12094356/`；完整路径、各视频/CSV SHA-256、许可和转换规则见 `docs/2026-10-14-icaerus-sheep-video-download.md`。下载步骤未跑模型；随后的实跑结果见本节首条。

- 2026-10-14 顺序完成五项产品功能：`fed76dc` 视频事件时间轴与约 6 秒证据片段下载（有秒数的规则观察、行为变化及复核）；`ac260af` 暂停视频画框纠错、漏检/ID/牛行为纠错持久化和 CSV 导出；`3f035c4` 公开数据评估中心（导入真值 CSV，记录数据集出处/版本/许可/划分、输入哈希，计算检测 P/R/F1 与匹配帧 ID 切换）；`7ae19e8` 羊轨迹半秒窗口位移的低活动/移动/快速移动摘要；`678e70b` 人工关联个体后跨视频的牛规则风险分数或羊移动时间比例趋势。页面、API、README 与相应测试同步更新。
- 上述评估中心目前只在用户实际导入标注时产生测量值；仓库没有声称公开数据指标。Mendeley 羊视频公开文件接口返回 401；Zenodo 12094356 的约 158 MB 压缩包下载中断于约 44 MB，残缺文件已删除，未解析、未验收。羊五类行为标签属于视频级且片段可混合活动，不能自动转成逐羊逐帧真值；当前没有训练或验证羊五分类模型。
- 本轮最后验证：后端全量 `643 passed, 4 skipped`；羊半秒平滑改动后的聚焦测试 10 passed；前端全量 26 passed，`npm run build` 成功。`yolo26n.pt` 为原有未跟踪文件，本轮未改动。

- 2026-10-14 开放数据检索：候选、入口、许可与使用边界整理到 `docs/2026-10-14-cattle-sheep-open-data-shortlist.md`。优先候选为 Mendeley 羊行为原视频、ICAERUS 羊通道视频、CattleEyeView/MooTrack360 牛追踪基准、MmCows 跨日多模态数据；牛跛行专家评分资料需进一步核对文件访问。仅核对公开页面，本轮未下载或处理数据。

- 2026-10-14 按产品顺序完成两项功能提交：`15bbaef` 增加最近视频任务、刷新后重开结果和人工复核记录（漏检、ID 切换、误告警、现场关注，可记 Track ID 与秒数）；`e569f74` 增加人工确认的跨视频个体编号关联、按日期汇总视频证据与复核、现场回访及带出处的兽医结论录入。牛羊不能共用同一个个体编号；没有声称自动跨天重识别或疾病预测。跟踪结果新增 `track_ids`，供新视频的牛羊关联使用。
- 本轮完整验证：后端 `631 passed, 4 skipped`，前端 `21 passed`，`npm run build` 成功。已有三个历史上传 AVI 与既有 `waid_cattle_static_acceptance.avi` SHA-256 完全相同（`8A7C40A3CF8C2996BB1B4085EF222B3D39695A1D7D56B05D773861A55BFBA68C`）；未找到可作新牧场牛羊验收的独立视频。本轮仅验证接口、页面及既有开发链路，没有生成新的牧场泛化指标。

- 2026-10-14 产品演示增强：牛只视频结果增加逐 Track ID 的“观察证据 → 规则评分 → 复核建议”图谱（告警含视频秒数；低平均速度单独计分时标注全视频证据）；羊类别可在网页选择并进入同一视频检测追踪链路，羊视频不加载牛行为模型、不执行牛健康规则或牛群异常检测，首页不把羊计作牛，页面和羊报告明确提示尚未验证。README 已增演示步骤和边界。
- 本轮验证：新增链路聚焦 `pytest` 20 passed；前端 `npm test -- --run` 20 passed，`npm run build` 成功；完整后端 **628 passed / 4 skipped**。仓库内 210 帧牛只验收视频用交付检测权重实跑，输出 210 帧、26 个 Track ID、26 条规则告警、26 个图谱对象，产物在已忽略的 `data/verification/results_health_graph_20261014/`。这只验证既有牛样例的运行链路，不代表羊或新牧场泛化效果。
- 修复两项既有外部行为 CLI 测试：测试将临时目录显式传入 `--project-root`，使输出路径符合原有越界保护；未放宽生产安全校验。两项聚焦通过，完整后端因此恢复绿色。

- 主线：Unicode 路径兼容系列修复与原子发布验证（至 `4d058a7`）。
- 实验分支 `codex/cross-domain-behavior`：CBVD4 两种初始化训练已完成；validation Macro-F1 为 Kinetics 0.839844、CVB-transfer 0.840723，仅按 validation 冻结选择 CVB-transfer。
- 一次性三臂 test 已完成（`test_read_count=1`）：冻结 CVB12 / Kinetics / CVB-transfer 的 Macro-F1 分别为 0.022472 / 0.878173 / 0.830761；逐源视频 2,000 次 bootstrap 与独立数值复算完成。
- 冻结候选因站立反刍 F1=0.588235 低于预设 0.60 门槛，`promoted=false`；未安装 CBVD4 模型、未运行上传视频演示。推广 CLI 已提交（`b7d30e1`）。
- 正式结果、数据操作台账和计划状态已发布（`6add827`）：`docs/experiments/2026-08-24-cbvd4-domain-adaptation-results.md`。
- 下一阶段多 seed validation 已预注册并启动：设计 `4ca0746`、计划
  `ba8ac6e`；development-only loader/CLI、六单元矩阵和聚合核心已提交
  （`bd5b06b`、`8779ab1`、`cd8c900`、`1589d5d`）。33 项聚焦测试
  通过，真实 preflight 与两种初始化 smoke 均通过。
- validation-only 逐样本推理和六单元汇总工具已提交（`38a4517`），输出
  `validation_predictions.csv`、`validation_metrics.csv`、`aggregate.json`
  和 `report.md`，保留 checkpoint/validation manifest 哈希且不作晋级决定；
  之后通过三轮失败关闭审查加固（`30ed5f8`、`7cba9f5`、`e7723b3`）：
  六单元先整体校验 checkpoint/矩阵绑定后才推理，正式 test 路径在任何读取前
  拒绝，新训练仅允许 train/val 哈希。最终 60 项聚焦测试通过，规格与质量
  复审均无剩余 Critical/Important；计划状态提交为 `ed91bbb`。
- 多 seed 矩阵第 1 条新增臂 Kinetics seed 20260901 已完成：2026-09-23 20:57 写出
  `validation_metrics.json`/`history.csv`/`best.pt`（epoch 0--18 共 19 轮），
  validation Macro-F1=0.8530158904，`best.pt` SHA-256=
  `ecc4ccd176ef172c2ce9061ed242abce210d05d659627512b6b613a723c36654`，
  `test_metrics_read=false`；恢复日志
  `outputs/cbvd4/paper_20260922/logs/kinetics_seed_20260901_resume_20260923.stdout.log`。
- 多 seed 矩阵第 2 条新增臂 CVB-transfer seed 20260901 已完成：2026-09-30 18:37:50 正常
  收尾（`resume_exit=0`，**epoch 11 早停**，patience=6；最佳在 epoch 5），写出
  `validation_metrics.json`/`metrics.json`/`history.csv`/`best.pt` 等完整产物。
  validation Macro-F1=0.8325412642、accuracy=0.9146341463，最佳 `best.pt` SHA-256=
  `3f28cca2d984c1133d860afbae7e0d20de321cae0669c49b241a8a6a8ccb9857`，
  `test_metrics_read=false`，清单哈希与冻结矩阵一致（train `43dda22a…` / val `8a8a7d08…`）。
  逐类 F1：grazing 0.9292 / drinking 0.8167 / ruminating-standing 0.6012 /
  ruminating-lying 0.9831（站立反刍仍是最弱类，混淆主要在它与 grazing 之间）。日志
  `outputs/cbvd4/paper_20260922/logs/cvb_transfer_seed_20260901_resume_20260930.stdout.log`。
  参照：两条 20260824 旧臂为 Kinetics 0.8398443 / CVB-transfer 0.8407228，即本 seed 下
  Kinetics 升、CVB-transfer 降——只是稳定性观察，**六格齐全并跑完汇总前不作任何选择**。
- 多 seed 矩阵第 3 条新增臂 Kinetics seed 20260908 已完成：2026-10-01 22:34:22 正常收尾
  （`resume2_exit=0`，**epoch 13 早停**，patience=6；epoch 13 的 0.8424501 差一点点没刷新
  epoch 7 的最佳），共 14 轮。validation Macro-F1=0.8436268208、accuracy=0.9126016260，
  最佳 `best.pt` SHA-256=`5802f043d5a177b7cd1a3c90106254a22e176817d8918f86fdf1e8af1de4318d`
  （与 `validation_metrics.json` 记录一致，已独立复算），`test_metrics_read=false`，
  清单哈希与冻结矩阵一致。逐类 F1：grazing 0.9139 / drinking 0.8467 /
  ruminating-standing 0.6178 / ruminating-lying 0.9961。日志
  `outputs/cbvd4/paper_20260922/logs/kinetics_seed_20260908_resume2_20261001.stdout.log`。
  至此 Kinetics 臂三个 seed 齐全：0.8398443 / 0.8530159 / 0.8436268（均值 0.8455，
  样本标准差 0.0068）；CVB-transfer 臂还差 seed 20260908。
- 多 seed 矩阵第 4 条（也是最后一条）新增臂 **CVB-transfer seed 20260908 已完成**：
  2026-10-03 13:58:09 正常收尾（`resume_exit=0`，**epoch 10 早停**，共 11 轮；中途按用户
  要求在 epoch 8 暂停、次日 12:25:27 `--resume` 恢复）。validation Macro-F1=
  **0.8266304027953745**（最佳 epoch 4）、accuracy=0.8943089431，最佳 `best.pt` SHA-256=
  `0d3b19161a482fd3021ee843e75623b979a5f0b99d0180f9468b9d9aa604380e`
  （与 `validation_metrics.json` 一致），`test_metrics_read=false`，清单哈希与冻结矩阵一致。
  逐类 F1：grazing 0.8886 / drinking 0.8571 / **ruminating-standing 0.5607** /
  ruminating-lying 1.0000。日志
  `outputs/cbvd4/paper_20260922/logs/cvb_transfer_seed_20260908_resume_20261002.stdout.log`。
  **至此六格齐全**（两臂 × 三 seed，全部 `test_metrics_read=false`）：

  | 初始化 | 20260824 | 20260901 | 20260908 | 均值 | 样本标准差 |
  | --- | --- | --- | --- | --- | --- |
  | Kinetics | 0.8398443 | 0.8530159 | 0.8436268 | 0.84550 | 0.0068 |
  | CVB-transfer | 0.8407228 | 0.8325413 | 0.8266304 | 0.83330 | 0.0071 |

  即两个初始化的 seed 波动同量级（≈0.007），Kinetics 三个 seed 一致高于 CVB-transfer
  （平均高约 0.0122）。**这仍是 validation 稳定性观察；按预注册，做选择前必须跑完
  计划 Task 7 汇总，且不得读取正式 test。**
- WAID4500 YOLO11s 可复现包已入库（分支 `codex/waid-reproducibility`，现共 10 个提交，
  即 Codex 的 8 个加本次的 `f18bd4d` 修复与 `842b1bd` 交接）：
  manifest 合约、原子重建、本地资产导入、可移植训练入口、证据验证器、
  一键 PowerShell 工作流，以及中文指南 `docs/WAID4500_REPRODUCIBILITY.md`。
  `reproducibility/waid4500/` 跟踪 4,720 条清单（train 4500 / valid 200 / test 20）、
  类别统计、环境、运行摘要、训练配置与 `checksums.sha256`。
- WAID 真实资产验证（`--project-root F:\new大创`）：check-only `status=ready`
  （torch 2.0.0、ultralytics 8.4.22、device 0，`yolo11s.pt` SHA-256=
  `85a76fe86dd8afe384648546b56a7a78580c7cb7b404fc595f97969322d502d5`）；
  verifier `status=passed`，归档 `run/weights/best.pt` 与交付模型
  `models/detection/yolo11s-waid.pt` 同为
  `46d734cba7553f31e89e739156f50e9a675b176f798c70159838497531771a64`，
  选中 epoch 89（P 0.94186 / R 0.91602 / mAP50 0.95385 / mAP50-95 0.584）。
- WAID 真实 1 epoch 冒烟训练（2% 训练集 90 张 + 200 张验证）通过：输出
  `outputs/training/waid4500_yolo11s/reproduced/smoke_e1`，
  `best.pt`/`last.pt` 为 strip 后的 19,266,131 字节检查点，退出码 0。
- 修复 `f18bd4d`：非 ASCII 路径下 `torch.save` 会让训练在 `final_eval` 抛
  `RuntimeError: Parent directory ... does not exist`（详见「决策与坑」）。
- 测试证据：`tests/test_waid_repro.py` 45 项通过；完整 `pytest` 588 通过 /
  4 跳过 / 2 失败——两项失败在 `integration` 上同样复现
  （`delivery_tests/test_external_behavior_cli.py` 把临时输出放在 `project_root`
  外被安全校验拒绝），与本次改动无关；前端 `npm test` 16 项通过、
  `npm run build` 成功（2178 modules）。
- 完整评估：`docs/2026-08-24-new-dachuang-complete-project-assessment.md`；
  路线图（P0/P1/P2 与执行顺序）：worktree 内 `docs/2026-08-24-project-status-and-roadmap.md`。

## 进行中

- 局部放大只验证了开发牛视频中的加载和人工复核链路；独立牧场视频的可判读提升、遮挡与模糊情况仍需现场人员核对。

- 2026-10-22：功能 3 的短片流程候选已找到，尚无区域进出人工真值或同机位多日长视频；功能 4 尚无可核对穿线方向和台账的本地素材。不要从行为标签推定空间进出事实。

- 2026-10-22：演示入口已可操作；短视频无法检验同机位多日趋势、采食饮水区域或栏门计数准确率。本次没有给未核实画面虚构区域和现场标签。

- 2026-10-22：新空间统计只在已有上传视频上运行；正式库尚无用户绘制的采食区/饮水区/栏门线记录。现有公开视频短、机位不固定，不能用于 10 分钟以上同机位多日趋势或现场计数准确率结论。手机入口是响应式网页，不含短信或第三方推送。

- 2026-10-22：三项短期功能已合入主线，旧视频和公开羊样例完成基础浏览器验收。真实牧场牛羊原视频、现场操作反馈和实际打印/PDF 查看仍待进行。

- 2026-10-22：用户希望短期丰富大创产品功能，目前在比较处置闭环、可复核巡检摘要和视频质量提示的价值与成本；尚未决定具体实现，也没有新增产品功能代码。现场牛羊原视频和真实台账仍缺失。

- 圈舍存栏核对、历史视频证据导航、全局历史分页筛选和视频内按任务查询均完成隔离浏览器验收；当前缺少授权牧场原视频、真实圈舍台账和现场人员复点，因此尚不能评估误差率、漏拍率或真实防丢失效果。下一项应做现场数据验收，而不是继续用开发视频生成结论。

- 演示产物与单段公开样本测量已完成；交付网页仍使用原默认检测模型，尚未配置官方羊专用权重或将证据面板集成到常规任务结果。ICAERUS 模型与视频属于同一项目，训练数据关联尚未排除，不得声称独立外部泛化。无人机镜头运动使位移量不能直接视为羊的行为。

- 公开羊视频源文件及标注已取得，且通过本项目 pipeline 做了两模型实跑和结果视频检查；网页任务与评测接口已有真实记录，页面呈现仍待复核。新牧场固定机位验收与具体疾病推断仍需另外的数据。

- 产品外部验收待素材：公开羊视频/真值已就绪；仍需未参与开发的真实牧场牛羊原视频。当前无运行中的训练任务；羊活动摘要并非羊五分类行为识别，个体趋势也不是疾病预测。

- 产品方向待外部素材：用户记不清真实牧场视频位置，授权先搜索并使用已有合适文件；当前只找到已暴露的历史验收/开发视频。待用户上传新的牛羊原视频和带诊疗结论的病例；羊健康规则与具体疾病预测没有验证依据。本次没有开启模型训练。

- WAID 复现加固**已完成并合并回 `integration`**（分支 `codex/waid-repro-hardening`，
  worktree `.worktrees/waid-repro-hardening`，基于 `integration` 416b90e；用户 2026-10-02
  审阅后合并）：
  `2ea7dc6` 导入的冻结数据集 `data.yaml` 不再保留源机绝对根（原先写死
  `E:\大创\WAID_YOLO11\waid4500_v1`），并与 PowerShell `rebuild` 默认输出改为独立目录
  `derived\waid4500_rebuilt`（原先默认指向冻结目录本身，该模式必然失败）；
  `733cbbb` 续训前校验检查点内记录的输出根，越界即 fail-closed（Ultralytics
  `trainer.check_resume` 会用检查点参数覆盖全部参数，归档检查点记录的是
  `E:\大创\WAID_YOLO11\runs`，否则会静默写到旧 E 盘）——已用真实检查点验证：归档
  checkpoint 被拒、`reproduced` checkpoint 被接受；
  `7080174` 五类资产改为**整批事务**：先全部暂存校验、再一起发布，任一环节失败则回滚
  已发布组件并恢复被替换的旧资产；
  `f6e6df7` 证据强度补齐：`verify_reproduction()` 现在逐条校验全部 4,720 个样本
  （存在性 + 标签内容与清单元数据一致）、冻结划分成员集合（`splits/*.txt` 对
  4,500/200/20），并重算 `reproducibility/waid4500/dataset_samples.sha256` 里 4,720 条
  逐样本内容摘要（新增生成器 `scripts/reproducibility/write_waid_sample_hashes.py`）。
  **真实端到端实测**（`--project-root F:\new大创`）：`status=passed`，样本 4,720/4,720、
  划分 4,500/200/20、内容哈希 4,720/4,720，六层全通过。
  测试：聚焦 58 passed；worktree 全量 **601 passed / 4 skipped / 2 项既有失败**（与
  `integration` 相同）。至此复核的 6 项 Important 全部处理完毕，可声明"完整复现证据
  全部通过"——但声明措辞仍需用户确认后再写进 README/指南之外的对外材料。
- WAID 独立复核结论为 WARN（Critical=0、Important=6）：聚焦测试、真实 check-only、
  当前哈希/血缘 verifier 和既有 smoke 产物均通过，但“完整可移植复现”的声明仍需加固。
  已确认：verifier 未完整验证 4,720 个样本及固定划分；缺少逐样本内容哈希；导入的
  `data.yaml` 仍指向旧 E 盘；Ultralytics 续训会恢复检查点内旧 `save_dir`；PowerShell
  `rebuild` 默认目标已存在；五类资产导入不是整批事务。本轮未修改生产代码，等待用户
  确认采用完整加固还是缩小声明范围。CVB 长训练仍在运行，本轮没有启动 WAID GPU 训练。
- `codex/waid-reproducibility` 已快进合并到 `integration`（`1a8d033`，集成后完整
  `pytest` 588 通过 / 4 跳过 / 2 项既有失败，verifier `status=passed`）。worktree 仍在
  `C:\Users\Mrda\.codex\worktrees\waid-reproducibility\`（Codex 应用托管，未擅自删除），
  分支也保留，需要时再 `git worktree remove` + `git branch -d`。
- WAID 大资产只在本机且被忽略：`data/external/waid/{raw,derived,cache}`、
  `outputs/training/waid4500_yolo11s/{run,logs}`；训练会在冻结数据集目录内新增
  Ultralytics `*.cache`（已被忽略，重建对比时排除，勿手工删除或提交）。
- 多 seed validation 矩阵：新一代 4 条臂已完成 3 条——Kinetics seed 20260901
  （0.8530158904）、CVB-transfer seed 20260901（0.8325412642）与 Kinetics seed 20260908
  （0.8436268208，14 轮、最佳 epoch 7）；详见「已完成」。**最后一格 CVB-transfer
  seed 20260908 已于 2026-10-02 14:44:46 启动**（PID 28468，用户 10-02 决定开跑，此前自
  10-01 起暂缓）。形态与隔离自检：`--source-checkpoint models/behavior/cvb_x3d_v2_best.pt`
  （哈希 `731c6ed3…`，与 seed_20260901 臂同一来源）、无 `--kinetics-checkpoint`、
  `--seed 20260908`；协议 `test_data_read=false`、`evaluation_scope=train_val_only`、
  清单哈希与冻结矩阵一致。日志 `outputs/cbvd4/paper_20260922/logs/cvb_transfer_seed_20260908.{stdout,stderr}.log`、
  PID 文件同名 `.pid`（均在 `.worktrees/cross-domain-behavior` 下），输出
  `outputs/cbvd4/paper_20260922/multiseed_validation/cvb_transfer_init/seed_20260908`。
  **该臂已于 2026-10-03 13:58:09 完成**（epoch 10 早停，共 11 轮，validation Macro-F1
  0.8266304028；中途 10-02 22:45 曾在 epoch 8 边界按用户要求暂停，10-03 12:25:27
  `--resume` 恢复）。逐轮 val_macro_f1：0.5183 / 0.5657 / 0.7873 / 0.7994 / **0.8266** /
  0.7573 / 0.8087 / 0.7510 / 0.7544 / 0.8017 / 0.8181；最佳之后连续 6 轮未刷新即早停。
  日志 `.../logs/cvb_transfer_seed_20260908_resume_20261002.stdout.log`（7262 字节最终摘要）。
  **六格矩阵已全部有 validation 结果**；**计划 Task 7 汇总已于 2026-10-03 14:49 完成**
  （14:08:23 启动，PID 17112，`--mode summarize --device cuda --batch-size 4 --workers 0`，
  日志 `outputs/cbvd4/paper_20260922/logs/multiseed_summarize_20261003.{stdout,stderr}.log`）。
  产物：`validation_metrics.csv`（6 行）、`aggregate.json`
  （39.6 KB，含每格 984 条逐样本预测路径与按源视频错误计数）、`report.md`，另有
  `analysis/<初始化>/seed_<seed>/validation_predictions.csv`。
  **结果**：Kinetics 均值 **0.845496**（样本标准差 0.006782）vs CVB-transfer **0.833625**
  （0.006623）；配对差值 cvb−kinetics = **+0.000878 / −0.020475 / −0.016016**（旧 seed 微正、
  两个新 seed 明显为负 → 符号反转）；`test_data_read=false`（`aggregate.json` 里唯一的
  "test" 字样就是这个布尔键），六格全部 validation-only。
  注意一处 0.001 量级差异：最后一格在训练内记录的 0.8266304028 与汇总统一重算的
  **0.8276105066** 不同（其余五格两者逐位一致）；汇总是对冻结 `best.pt` 的统一重评估，
  跨格比较应以 `validation_metrics.csv` 为准，训练内数字来自内存模型末轮评估。
  另已将结论写入跨域分支的 `docs/data/2026-08-23-public-cattle-video-data-record.md`
  （实验台账 + 假设修正表 + 复现命令），提交 `1606b71`。
  历史启动日志与暂停监视器日志保留在 `.worktrees/cross-domain-behavior` 的
  `outputs/cbvd4/paper_20260922/logs/` 下；识别进程靠完整命令行 + 输出目录，不能只信 PID。
- 运行方式经验（务必遵守）：本环境会静默回收无人托管的进程——2026-09-29 的会话后台任务在
  跑完 epoch 2 后被回收；2026-09-30 用 `Start-Process` 脱离式进程重试也在约 3 分钟后被回收；
  最终仍用**会话托管的后台任务**恢复成功并正常跑完。所以长训练只能走会话托管后台任务，
  中途被回收就用同一命令加 `--resume` 续跑（每 epoch 落一次 checkpoint，已完成轮次不丢）。
  识别进程必须靠完整命令行 + 输出目录，不能只信 PID。
- 该臂产物与日志：输出
  `outputs/cbvd4/paper_20260922/multiseed_validation/cvb_transfer_init/seed_20260901`
  （`history.csv` 每 epoch 一行；`stdout.log` 只在结束时写出最终 JSON 摘要，中途为空正常）；
  日志在 `.worktrees/cross-domain-behavior` 的 `outputs/cbvd4/paper_20260922/logs/`
  （首次 `cvb_transfer_seed_20260901.*`、被回收的两次尝试 `..._resume_20260929.*`、
  最终成功的 `cvb_transfer_seed_20260901_resume_20260930.*`），另有同名 `.pid` 文件。
  **早停属正常收尾**（patience=6：本臂停在 epoch 11，上一臂停在 epoch 18），不要误判为崩溃。
- `codex/cross-domain-behavior` 仍有 3 个用户所有、未提交文档（roadmap、2026-09-12
  选择性数据可行性、2026-09-12 测试来源审计），接手方不得擅自覆盖或提交。
- 主线有未跟踪文件：评估报告、`星牧智控-项目计划书.docx`、`申报-项目概述.txt`、`scripts/make_plan_docx.py`。

## 下一步（P0，按序执行）

- [ ] 用独立牧场视频抽取模型“无法确定”片段，由人工对照完整视频、原帧与局部裁剪，记录裁剪后可判读比例和仍不确定原因；按结果决定是否增加时间轴上的一键定位。
- [ ] 可用 CBVD-5 `272.mp4` 做单段饲槽附近观察区的界面演示，并人工逐帧核对轨迹与区域边界；它不能替代下面的长视频、多日趋势和栏门现场验收。
- [x] 用当前牛开发视频演示检测、追踪和证据回看。切换部署机器时重新上传素材并更新演示任务 ID；继续下面的现场数据验收，不用该视频宣称新牧场效果。
- [ ] 获取授权的固定机位牛/羊视频：同一圈舍与机位、至少连续多日且每段至少 10 分钟，并提供真实拍摄开始时间。先用人工标注核对区域进入、停留和长时间空区提示，再讨论阈值调整。
- [ ] 获取栏门完整经过视频与出入栏台账，逐次核对画线方向、折返、遮挡和 ID 切换；只有通过现场复核后才评估日报能否辅助交接班。
- [ ] 让现场人员在手机浏览器走通“告警证据 → 已查看/误报/已处理 → 备注”，记录完成耗时和误触；若实际需要离线以外的消息通知，再选定牧场使用的具体渠道。

- [x] 上传前拍摄检查：按浏览器读到的时长和分辨率给补拍建议，提示人工检查覆盖与画面稳定性，不阻断识别。
- [x] 一页式巡检摘要：按视频汇总识别帧数/ID、规则提示、人工复核、核查事项与最新处理记录，支持打印，不生成疾病诊断。
- [ ] 用授权牧场视频与真实巡检人员检验三项功能的实用性；记录补拍命中、处置耗时和摘要是否易读。

- [x] 视频问题到人工处置/复查闭环已完成；规则提示只用于预填人工事项，临时 Track ID 不当永久身份，规则提示不称为疾病诊断。

- [x] 取得可完整下载的羊原视频及对应标注，核验出处/许可/版本/哈希和标注粒度，转换评测中心的 GT CSV；已完成 ICAERUS 官方 Zenodo 12094356 的四段视频和 MOT 标注，见 `docs/2026-10-14-icaerus-sheep-video-download.md`。转换规则与原始标注保留；当前转换为一次性数据处理，若要自动重复执行，再补独立脚本。
- [x] 已用上述公开羊视频在本项目 pipeline 实跑默认模型与公开羊专用模型，生成 H.264 证据面板视频和本样例测量，详见 `docs/2026-10-14-icaerus-sheep-model-demo.md`。
- [x] 网页上传任务、同一 API 的 GT 导入、Chrome 评测卡片、播放器实际播放、人工纠错、复核提交和下载操作均已验收（后 3 项使用隔离 SQLite 副本，见 `docs/2026-10-15-browser-interaction-acceptance.md`）。网页默认模型 Recall 0.102%，不能以羊专用演示模型视频冒充该任务结果。
- [x] 修正首页“今日监测牛只”、历史告警和 Track ID 的显示口径；用户确认“最近牛视频 Track ID 数＋处理时间、历史未处理规则提示、无牛视频显示暂无记录”。实现与测试已完成，真实 API 已核对；网页视觉与点击仍待恢复浏览器后复核。
- [x] 按用户确认的推荐方案实现圈舍存栏核对流程；无完整拍摄覆盖时要求补拍，差额先待复点，只有带出入栏核查与现场查找记录的人工复核才能登记丢失。隔离浏览器验收见 `docs/2026-10-15-pen-inventory-browser-acceptance.md`。
- [x] 全局圈舍历史卡片可打开其绑定的视频证据；已验证页面切换、播放器、26 个视频内 Track ID 及同 job ID 的事件/纠错/复核请求，普通导航会清除旧证据。见 `docs/2026-10-16-inventory-video-navigation-acceptance.md`。
- [x] 全局圈舍历史支持每页 20 条、上一页/下一页、圈舍编号和状态筛选，查询可到最近 100 条以外；隔离浏览器验证 25 条记录的 20+5 两页与组合筛选，见 `docs/2026-10-16-inventory-history-pagination-acceptance.md`。
- [x] 视频内嵌盘点面板已按 `job_id` 查询全部关联记录；隔离库用 101 条较新其他任务记录验证旧视频盘点仍可回看，见 `docs/2026-10-16-video-inventory-scope-acceptance.md`。
- [ ] 若用户希望网页使用羊专用模型，先核实官方权重许可与训练数据是否包含本 Zenodo 视频，再设计为显式可选模型、标示来源并做另一来源数据验证；不得静默替换默认权重或把同源结果称为独立评测。
- [ ] 如能取得可信的五类羊行为训练/验证标注，按视频级标签训练、留源视频独立划分并实测；只有评估过关且输出粒度匹配时才接入页面。混合活动片段不可给单只羊强行贴五分类标签。

- [ ] 产品验收（依赖新素材）：取得牧场授权的牛、羊原始视频各至少一段，核对 SHA-256 不属于既有开发/验收视频；从网页上传，播放结果并下载报告，用新增复核表逐条记录漏检、ID 切换、误告警、播放问题。羊只展示检测追踪；旧视频不能算新牧场验收。
- [ ] 产品数据（依赖现场）：用真实耳标核对至少同一牛/羊的跨日视频，关联到稳定个体编号；录入实际回访、兽医诊疗或检验记录出处，并人工核验。当前录入记录只有 `user_recorded` 状态，不能视为确认病例。
- [ ] 疾病模型（依赖足量确认病例）：先定义病例口径、时间窗、对照组和独立验证集，再评估是否能预测疾病或发病时间；未通过验证前保持页面不输出具体疾病预测。

- [x] 合并 `codex/waid-reproducibility` 到 `integration`（2026-09-29 快进完成，
  `1a8d033`；合并后完整 `pytest` 588 通过 / 4 跳过 / 2 项既有失败，verifier
  `status=passed`，指南里的 verify/rebuild/train 命令现可在主线直接运行）。
- [x] WAID 复现加固已完成并合并（2026-10-02，合并提交 `992f64a`）：全量 4,720 样本与固定
  划分校验、逐样本内容哈希、portable `data.yaml`、续训越界 fail-closed、独立 rebuild 输出、
  整批导入事务。真实资产端到端 verifier `status=passed`（六层），此后可以声明"完整复现证据
  全部通过"。
- [x] 多 seed 矩阵四条新臂全部完成（2026-10-03 13:58 最后一格 CVB-transfer seed 20260908
  早停收尾，11 轮、0.8266304028）；六格齐全，全部 `test_metrics_read=false`，两臂 seed
  波动同量级（≈0.007）。当前**没有训练进程在跑**。
- [x] 四条新臂齐后执行计划 Task 7 汇总（2026-10-03 完成）：`validation_metrics.csv`、
  `aggregate.json`、`report.md` 已生成，`test_data_read=false`；Kinetics 均值 0.845496
  （样本标准差 0.006782）vs CVB-transfer 0.833625（0.006623），配对差值 +0.000878 /
  −0.020475 / −0.016016；结论已写入跨域分支数据记录（`1606b71`）。**多 seed 矩阵至此结清，
  且按预注册不作任何候选选择或晋级决定。**
- [x] 主线申报材料与仓库整理入库（2026-10-03）：`AGENTS.md`、额度监听工具
  （`scripts/watch_quota.py` + `启动额度监听.bat`）、申报材料（`docs/申报-项目概述.txt`、
  `docs/星牧智控-项目计划书.docx` + 生成脚本 `scripts/make_plan_docx.py`、完整评估文档）
  已提交（`ae0d828`、`f0f51f7`、`86c033c`）；`data/delivery-processes.json`（运行时 PID
  登记）与 5 个第三方/大文件（`AID.pdf`、`CoastCor-Net.py/.yaml`、`train.zip`、`代码.zip`）
  已加入 `.gitignore`（`360f210`、`4183efb`），**主线工作树现在完全干净**。
- [ ] 数据（**协议与工具已就绪，等素材**）：前瞻性独立确认集的暴露边界机制已实现并提交到
  跨域分支（`323bac3` 模块+CLI+7 项测试、`547cda2` 协议文档
  `docs/experiments/2026-10-03-prospective-confirmation-set-protocol.md`）：新视频必须逐条
  SHA-256 与开发登记表 `manifests/cbvd4/source_videos.csv`（397 条，哈希
  `a0aad746…`）比对，命中即 exit 1 拒绝；实测把真实已暴露的 `10.mp4` 放进候选目录被正确
  拒绝。**本地已确认没有可用的新视频**（CBVD-5 687 个 mp4 属开发语料，E 盘那批属既有项目
  数据），需用户提供新牧场视频才能冻结。
- [x] 论文统计（2026-10-03 完成）：跨域分支 `a89769d`（模块 1707 行 + CLI + 27 项测试）、
  `dc0f3e3`（结果文档 `docs/experiments/2026-10-03-cbvd4-validation-calibration-coverage.md`）。
  已独立核验：聚焦 **27 passed**；`calibration.csv` 的 macro-F1 与既有 `validation_metrics.csv`
  **逐位一致**；`report.md` 明示 test 永不读取、不作选择/晋级决定。关键结果：原始 softmax
  严重过度自信（pooled ECE 0.449 → 交叉拟合温度后 0.034 / cvb 0.442 → 0.052），AURC
  0.0174（kinetics）/ 0.0232（cvb），选择性准确率@0.7 覆盖 0.9840 / 0.9705；配对差值
  +0.000878 / −0.020475 / −0.016016，**三个区间均含 0** → 两臂无已确立差异。
  另修正一处此前说法：`delivery_tests/test_external_behavior_cli.py` 的 2 项失败只出现在
  WAID worktree 与主检出，**本 worktree 为 8/8 通过**；本 worktree 的预存失败是
  `test_cross_domain_behavior_reporting.py::test_committed_result_document_records_verified_
  complete_evidence`（断言文档中缺失的句子，与本批改动无关，子代理未改任何既有文件）。
- [ ] WAID：预注册**草案已写**（`docs/superpowers/specs/2026-10-03-waid-improvement-preregistration-design.md`，
  提交 `70fd90f`）：假设来自仓库自有证据（训练集 zebra 仅 289 图 vs sheep 1041 图），单变量
  规则 H1 类别过采样 / H2 imgsz 960→1280，只读 valid、test 本阶段不读。用户已选 **B 档
  （筛选→确认）**。**真实速度已实测**（2026-10-03 18:30，协议同筛选、仅 `epochs=2`，`probe_exit=0`）：
  epoch 2 = **237.7 s = 3.96 分钟/轮**（累计 time 243.2 → 480.9 s；探测配置与日志在忽略目录
  `outputs/training/waid4500_yolo11s/timing_probe_e2.yaml` 与 `…/logs/timing_probe_e2.*.log`，
  输出 `…/reproduced/timing_probe_e2/`，2 轮后 val mAP50-95=0.4977，基线 120 轮为 0.584）。
  由此回填预算：**筛选 40 轮 × 3 seeds × 3 臂 ≈ 23.8 h**，胜者 120 轮 × 3 seeds 确认 ≈ 23.8 h，
  **B 档完整 ≈ 48 h**（超出草案 20–30 h 的估计，已向用户披露并等待其确认是否按此开跑、
  或缩为 3 臂 × 1 seed 筛选 ≈ 7.9 h）。**批准前不启动正式训练。**
  开跑前还差一件事：H1（类别过采样）在 Ultralytics 8.x 检测训练中无原生支持，需先实现
  LVIS 风格重复因子清单（生成 `train_rf.txt`，运行期 `data.yaml` 指向它）+ TDD 测试；
  H2 仅需新增一份 `imgsz: 1280` 配置变体。
  **H1 已实现**（`cattle_health_app/detection/waid_repeat_factors.py` + `tests/test_waid_repeat_factors.py`
  **10 passed**，提交见分支日志）：`class_image_counts` / `repeat_factors`（`max(1, sqrt(head/n_c))`）
  / `apportion_copies`（最大余数法，确定性）/ `write_repeat_list`。真实数据实测：因子
  zebra 1.8979、kiang 1.4458、camelus 1.3261，清单 4,500 → **5,176 条（+15.0%）**，落在
  `data/external/waid/derived/waid4500_v1/splits/train_rf_h1.txt`（本地产物、未入库）；
  类别计数与冻结的 `class_statistics.csv` **完全一致**（可作交叉校验）。**H1 每轮约慢 15%**
  （≈4.6 分钟/轮），预算按此调整。
  **接线已完成并启动筛选**（2026-10-03 19:46:57）：`load_training_config` 新增可选
  `train_list`（必须落在项目内且为 `.txt`），`write_runtime_data_yaml(..., train=...)`
  支持指向清单，`run_training` 在启动前校验清单存在并算出相对数据集根的条目；
  新增 `tests/test_waid_train_list.py` **7 passed**、既有 WAID 测试 **58 passed** 无回归；
  提交 `2213819`。三份预注册筛选配置入库
  `reproducibility/waid4500/screening/{baseline_e40,h1_repeat_e40,h2_imgsz1280_e40}.yaml`。
  **筛选首夜被环境回收**：链日志只写到 `START baseline_e40`，baseline 跑到 **35/40 轮**
  （`results.csv` 累计 14145 s → 真实均值 ≈ **6.7 分钟/轮**，明显慢于探测的 3.96 分钟/轮，
  故修正预算：baseline 40 轮 ≈4.5 h、H1 ≈5.2 h、H2 ≈8 h，合计 **≈17–18 h**）。2026-10-04
  11:00 起用第二个链（`screening_chain2.log`）**从断点续跑**：先 `--resume` baseline
  （PID 8368；`--resume` 生效、续训越界守卫放行、stderr 无绑定错误），随后串行 H1、H2。
  被回收时按当前臂 `--resume` 续（每轮落 checkpoint），恢复前确认无重复进程。
  已核验 baseline 的运行期 `data.yaml` 为 `train: images/train`；H1 启动后应变为
  `train: splits/train_rf_h1.txt`（接线在真实训练中的端到端证据，接手时必须复核）。
  **更正一条先前记录**：此前写的"配置读取不吃 BOM"**是错的**——实测 PyYAML 会跳过流起始
  BOM，`load_training_config` 能正常加载带 BOM 的配置，当时那次失败重跑也正常通过，
  判定为一次性瞬时故障而非代码缺陷；已保留 BOM 回归测试
  （`tests/test_waid_train_list.py::test_reads_a_config_written_with_a_byte_order_mark`）。
  **baseline 已完成**（2026-10-04 11:19:11，40 轮，`exit=0`）：最佳即最后一轮
  **mAP50-95=0.58312 / mAP50=0.95695 / P=0.94478 / R=0.91767**，与 120 轮冻结基线
  （0.584）基本持平 → **40 轮足以支撑筛选比较**，这是筛选阶段的重要校准点。
  **H1 首启失败已定位并修复**：Ultralytics 对 `.txt` 训练清单的条目是**按训练进程 CWD
  解析**的（不是数据集根），我原先写的是相对路径 → 它去找 `F:\new大创\images\train\...`，
  33 秒后以 `No valid images found` 退出（`exit=1`）。修法：清单改写**绝对路径**
  （提交 `18ac364`，含契约测试），重新生成 5,176 条绝对路径；重启后 stdout 实测
  **扫描 5,176 张图**（`123/5176 … 687/5176`）→ 接线端到端成立。同时清理了失败残留
  （`screening_h1_repeat_e40/`）与 AMP 检查下载残留的仓库根 `yolo26n.pt`。
  第三个链（`screening_chain3.log`，2026-10-04 11:20:58 起）按 **H1 → H2** 串行执行；
  按实测（冷启动前 35 轮均值 ≈6.7 分钟/轮，续跑 5 轮 ≈3.7 分钟/轮）估计剩余
  H1 ≈4–4.6 h、H2 ≈5.7–7.4 h，合计 **≈10–12 h**。
  **筛选三臂已全部完成**（2026-10-04 18:09:12，`chain3 done`，三臂各 40 轮 `exit=0`；
  实测 H1 ≈2.9 h、H2 ≈3.9 h，比估计快）。valid（200 图/1,863 实例）最佳 mAP50-95：

  | 臂 | mAP50-95 | mAP50 | P | R | 与 baseline 差 |
  | --- | --- | --- | --- | --- | --- |
  | baseline_e40 | 0.58312 | 0.95695 | 0.94478 | 0.91767 | — |
  | h1_repeat_e40 | 0.58328 | 0.95264 | 0.93138 | 0.91797 | **+0.00016** |
  | h2_imgsz1280_e40 | **0.59852** | 0.95804 | 0.94807 | 0.91488 | **+0.01540** |

  逐类 mAP50-95（H1 / H2）：sheep 0.471/0.486、cattle 0.689/0.705、seal 0.679/0.700、
  camelus 0.581/0.608、**kiang 0.386/0.380**、zebra 0.695/0.709。**结论**：H1（类别重复因子
  过采样）**无效**（+0.0002，落在噪声内）→ 按预注册记为负结果；H2（imgsz 960→1280）
  +0.0154（相对 +2.6%）且多数类均提升，但 **kiang 未提升**，且单 seed 无法区分其与 seed
  波动 → H2 是唯一值得进确认阶段的候选。baseline 的逐类明细尚未从日志取出（其 stdout 表格
  格式与 H1/H2 不同），若需要可后续独立复算。**下一步待用户定**：H2 按预注册做
  120 轮 × 3 seeds 确认（≈35 h）＋基线同 seeds 配对（再 ≈30 h），或先做 40 轮 × 3 seeds
  的 seed 波动估计（H2+baseline 各 3 seeds ≈ 20 h）以判断 +0.015 是否超噪声。
  **用户选 B（先量 seed 波动）**，2026-10-04 22:41 启动配对链：复用已有 seed 42，另补
  **seeds 43/44**，故只需 4 次运行——`baseline_e40_seed43` → `h2_imgsz1280_e40_seed43` →
  `baseline_e40_seed44` → `h2_imgsz1280_e40_seed44`（按 seed 成对，中途被回收也能拿到完整配对），
  预计 **≈13.6 h**（baseline ≈2.9 h/次、H2 ≈3.9 h/次）。链日志
  `outputs/training/waid4500_yolo11s/logs/seednoise_chain.log`，各臂日志
  `…/logs/seednoise_<name>.{stdout,stderr}.log`，输出 `…/screening/screening_<name>/`。
  配置由两份已入库的筛选配置仅改 `seed`/`name` 生成，落在忽略目录
  `outputs/training/waid4500_yolo11s/screening_configs_seeds/`（生成命令见本节；四份均经
  `load_training_config` 校验通过）。**分析口径**：对每个 seed 算 H2−baseline 的配对差值，
  三个差值同号且幅度稳定 → 判定 +0.0154 超出 seed 波动，再决定是否做 120 轮确认；
  若差值跨 0 → 记为噪声，H2 不进确认阶段。
  **2026-10-04 23:20:42 用户要求暂停，已在 epoch 边界干净停下**：监视器
  `…/logs/seednoise_pause_watcher.log` 在 23:20:37 见第 10 轮落盘、等 15 秒确认后停掉
  PID 5232（`still alive=False`）；链因非零退出码（`END baseline_e40_seed43 exit=-1`）
  **自动停止且未启动下一臂**（`seed-noise chain done`）。当前无训练进程、GPU 空闲。
  **断点**：`screening/screening_baseline_e40_seed43/` 已完成 **10/40 轮**，
  `best.pt`/`last.pt` 均为 23:20:10 写出的同一检查点；已用 `require_portable_resume()`
  核验其记录输出根 `…\waid4500_yolo11s\screening` 在项目内 → **ACCEPTED，可原样 `--resume`**。
  **恢复方式**（工作目录 `/F:/new大创`，命令见本节）：
  `train_waid_yolo11s.py --project-root F:\new大创 --config
  outputs/training/waid4500_yolo11s/screening_configs_seeds/baseline_e40_seed43.yaml
  --resume outputs/training/waid4500_yolo11s/screening/screening_baseline_e40_seed43/weights/last.pt`，
  之后按 seed-noise 链顺序继续未启动的三个臂：`h2_imgsz1280_e40_seed43` →
  `baseline_e40_seed44` → `h2_imgsz1280_e40_seed44`（配置在忽略目录
  `outputs/training/waid4500_yolo11s/screening_configs_seeds/`）。
  **seed 配对差值最终结果**（2026-10-06 12:59:38 最后一臂完成，8 个 run 各 40 轮、全部 `exit=0`；
  valid 最佳 mAP50-95）：

  | seed | baseline | H2（imgsz 1280） | 配对差值 |
  | --- | --- | --- | --- |
  | 42 | 0.58312 | 0.59852 | +0.01540 |
  | 43 | 0.57803 | 0.59924 | +0.02121 |
  | 44 | 0.57939 | 0.59787 | +0.01848 |

  配对差值 **均值 +0.01836、样本标准差 0.00291、最小 +0.01540，三组全为正**；baseline 跨 seed
  sd=0.00264（极差 0.0051）、H2 跨 seed sd=0.00069。**判定：H2 的 +0.018 明显超出 seed 波动
  （最小差值仍是 baseline seed sd 的约 5.8 倍），H2 通过 seed-noise 门**。逐类方面（seed 42
  已有）：camelus +0.027、zebra +0.014、sheep/cattle/seal 也都提升，**唯 kiang 0.386→0.380
  基本持平略降**；seeds 43/44 的逐类明细尚未取出，确认阶段应补。
  **下一步待用户定**：(A) H2 × 3 seeds × 120 轮确认（≈35 h，基线对比用冻结 120 轮 seed42
  0.584 + 本轮 40 轮配对证据）；(B) A 再加 baseline × 3 seeds × 120 轮（≈+30 h，完全配对的
  冻结协议确认，最严格）；(C) 就此以"40 轮筛选协议"结论收尾（较弱，但已完成且可复现）；
  (D) 无论选哪个，**"独立确认"仍必须等第 1 项的新素材**，否则只能声明 validation 提升。
  **用户选 A，2026-10-07 11:08:28 已启动确认链**：H2（imgsz 1280）**120 轮 × seeds 42 → 43 → 44**
  串行（`confirmation_chain.log`），首个 `h2_e120_seed42` 运行中（PID 1860，GPU 5081 MiB；
  运行期 `data.yaml` 的 train/val/test 与冻结划分一致，仅分辨率不同）。确认配置已入库
  `reproducibility/waid4500/confirmation/h2_e120_seed{42,43,44}.yaml`（epochs/patience 120、
  输出到独立目录 `outputs/training/waid4500_yolo11s/confirmation`，三份均过
  `load_training_config` 校验）。**预计 ≈36 h**（≈6 分钟/轮 × 120 轮 × 3 seeds），夜里大概率
  被回收，按当前臂 `--resume` 续（先确认无重复进程），日志
  `…/logs/confirmation_<name>.{stdout,stderr}.log`。
  **对比口径（不可事后更改）**：H2 三 seed 与**冻结基线 120 轮 seed42（valid 0.584）**及本轮
  40 轮配对证据（+0.015~+0.021）联合判断；确认阶段**不读正式 test**，test 留给最终一次性
  确认（且需第 1 项新素材）。
  **2026-10-05 12:16:22 已按用户指示恢复**（链 `seednoise_chain2.log`）：先 `--resume`
  `baseline_e40_seed43`（PID 3400，绑定校验通过、stderr 无错误，自 epoch 11 继续），随后排队
  `h2_imgsz1280_e40_seed43` → `baseline_e40_seed44` → `h2_imgsz1280_e40_seed44`；
  剩余约 **12.6 h**（baseline 余 30 轮 ≈1.9 h、H2 s43 ≈3.9 h、baseline s44 ≈2.9 h、
  H2 s44 ≈3.9 h）。被回收即按当前臂 `--resume`（先确认无重复进程）。
  **2026-10-06 11:05:34 再次恢复**：chain2 在夜里跑完 `baseline s43`（14:07）、`h2 s43`（18:27）、
  `baseline s44`（20:53）后，`h2 s44` 于 23:26:43 停在 23/40 轮被回收；本次用 chain3
  `--resume` 该臂（PID 26060，绑定校验通过、stderr 无错误、GPU 5125 MiB，自 epoch 24 继续），
  余 17 轮 ≈1.8 h。**这是最后一个臂**，完成后即可出 seed-noise 结论。
- [ ] 仅当预注册候选在新的确认集达到 Macro-F1 ≥ 0.70 且每类 F1 ≥ 0.60，才安装 CBVD4 模型并执行上传视频端到端演示。
  → **门控机制其实早已实现且为绿**（`cattle_health_app/behavior/cbvd4_evaluation.py`
  的 `PromotionDecision` 固定 `macro_f1_threshold=0.70`、`per_class_f1_threshold=0.60`；
  `scripts/promote_cbvd4_model.py` 仅当 `promotion.json` 的 `promoted=true` 才落盘交付模型；
  `delivery_tests/test_promote_cbvd4_model.py` + `test_cbvd4_evaluation.py` **13 passed**；
  已有一条真实的 `promoted=false` 拒绝记录）。**因此该项只等前两项产出合格候选**，无需再写代码。

## 决策与坑（不要再踩）

- 2026-10-22：`inspection-frame` 裁剪依据当前帧轨迹 CSV 检测框；若此帧没有所选 ID，返回 404 并提示换时间。人工结论以独立复核记录保存，不能覆盖原行为预测。开发视频不能证明独立牧场效果。

- 2026-10-22：CBVD-5 原视频在跨域实验工作树，主仓库清单路径本身不存在；687 段均约 10 秒，行为标注不能当作区域进出、饮水区边界或栏门穿线真值。`272.mp4` 仅用于饲槽附近观察区的单段功能演示；`camera_id=unknown`，不能假设跨段同机位或同日连续拍摄。没有完整栏门经过与人工台账时，不报告栏门计数准确率。

- 2026-10-22：演示视频是真实拍摄的既有开发素材，源 SHA-256 `8a7c40a3cf8c2996bb1b4085ef222b3d39695a1d7d56b05d773861a55bfba68c`。首页快捷入口绑定本机正式 SQLite 的任务 ID；原视频和结果大文件均被 Git 忽略，换机不能仅靠拉取代码复现入口。必须重新上传并替换前端常量；26 个 Track ID 不代表 26 头稳定身份或疾病个体。

- 2026-10-22：空间统计使用上传视频的轨迹 CSV 与用户手绘坐标，拍摄开始时间由人员填写；历史仅比较同圈舍、同机位、同画区，短于 10 分钟不推算每小时趋势。栏门的“进入/离开”方向由画线方向和反转选项决定，必须现场校准。轨迹 ID 仅在视频内有效，穿线次数和区域停留都可能受漏检、遮挡、折返和 ID 切换影响；不自动修改存栏台账。区域空区/数量下降只是待核查提示，不能称疾病告警。实际浏览器中旧牛结果 MP4 仍不可播放，事件截图和新生成的 H.264 片段可单独查看。

- 2026-10-22：用户明确选择 React + Python，不用 PHP；要求避免防御性编程和过多验证。处置事项只校验基本必填、已完成视频与待复查时间。旧任务 `47de2b7fbb534f948296dbf8dc5dc1c4` 的 MP4 为 MPEG-4，浏览器虽收到 206 仍无法解码；演示播放应选 H.264 结果或重新用现行流程处理，不把此问题归因于新待办功能。

- 2026-10-22：拍摄检查的时长/分辨率阈值是产品提示规则，不是训练或验证过的图像质量模型；它不会判断模糊、遮挡或全部动物是否入镜。一页式摘要仅汇总已有记录，人工复核和处置结论仍由人员负责。

- 2026-10-22：新增功能建议须利用现有视频、证据时间轴、人工纠错/复核和圈舍盘点，避免重复建设已有的识别展示与普通报表。定期核对测试夹具是否依赖固定日期；“比刚创建的记录更新”应相对 `created_at` 构造。

- 2026-10-16：全局历史通过 `/api/inventory-checks/page` 查询，总数和当前页使用相同筛选条件；状态按最新人工复核计算，圈舍编号按字面包含搜索。`/api/inventory-checks` 无参时保留最近 100 条兼容行为；视频结果页传入 `job_id` 时返回该视频全部关联记录。筛选变化要回第一页，旧请求不能覆盖新筛选；隔离验收数据只写入备份库，正式库始终保持不变。

- 2026-10-16：盘点历史记录只保存绑定的 `job_id`；打开视频证据时必须重新读取任务并确认 `status=completed` 且结果含播放器、下载路径和核心统计字段。HTTP 200 但结构异常的响应统一提示“视频证据加载失败”，合法但未完成的任务仍提示尚未完成，二者都留在盘点页。并发点击采用最后一次点击生效；用户通过普通导航离开再回到实时监控时必须清除先前外部选择，避免旧证据被误认为当前任务。隔离验收副本可新增记录，正式库必须保持不变。

- 2026-10-16：圈舍差额只由“登记存栏数 − 人工清点/复点数”计算，视频内 Track ID 数仅用于回看定位。`coverage=partial/unknown` 或首次人工清点为空时不能提交复核；`loss_user_recorded` 还要求丢失数不超过差额、出入栏记录已核对、现场查找已完成。`verification_status=user_recorded` 表示数据来源是人工录入，不表示系统独立确认。浏览器验收记录只写入隔离数据库；新版正式服务启动后创建了空盘点表，接口回读 0 条。开发牛视频的 26 个 ID 不能作为牧场存栏证据。

- 2026-10-15：旧历史牛任务可能没有 `species` 与 `health_evidence`，不能用它们的空图谱证明新流程无效；新管线在隔离环境重跑同一开发视频才得到 26 个证据链。该静态视频既已开发使用，页面截图只证明流程可演示，不能作为真实牧场疾病筛查的独立性能证据。隔离服务复跑新视频会在真实 `data/media` 写入忽略的衍生文件，但 SQLite 与告警仍隔离；正式 dashboard 核对未变化。

- 2026-10-15：浏览器交互验收使用正式 SQLite 的备份副本，测试性“已确认”只存在于隔离副本；正式 API 查询两类记录均为空。浏览器实际下载的文件有内容且视频哈希相同，比仅测 API 200 更强。测试性的确认记录不等于牧场现场确认，不能据此认定动物生病或丢失。临时 8001 服务已停止，本机 `data/verification/browser-acceptance.db` 与下载物均被 Git 忽略。

- 2026-10-15：`video/mp4`、HTTP 200 和 OpenCV 可解码不代表 Chrome 可播放；旧 `mp4v` 文件实测 DEMUXER 错误。新结果经 FFmpeg `libx264` 转 H.264，失败时保留原 `mp4v` 并写日志；其他电脑要有支持 `libx264` 的 FFmpeg。旧羊结果的转码前备份在 `data/verification/sheep-web-original-mp4v.mp4`，转码后 SHA-256 `d3b0ef7ba12991b62f77926174ecab654895a37d8c6171eb965f85ed94818728`。Chrome 播放和评测卡片已实测，但页面纠错、复核与下载尚未操作。截图只做 UI 证据，不提高默认模型的 0.102% 召回率。
- 2026-10-15：羊视频中确有整群羊，但默认模型只产生 1 个视频内 ID；结果标题必须称“Track ID 个数”，不能称“1 只羊”。这也是不能用该模型做存栏盘点/防丢失的直接可见证据。

- 2026-10-15：看板的牛视频数字只代表最新已完成牛视频内的 Track ID 数，不是今日存栏；历史规则提示按记录条数计，不按跨视频 ID 去重。旧任务未存 `species` 时沿用原系统默认牛类别。重启服务必须指定已装 OpenCV 的 PyTorch 环境（`AGRINEBULA_PYTHON`），系统 PATH 上的 Python 通过不了 preflight。Python 测试在受限沙箱会因中文路径乱码无法导入，需在允许的环境运行。现有服务在 8000/5173 运行；不要把 HTTP 200 当作浏览器实际播放验证。

- 2026-10-15：同一 ICAERUS 样本已参与模型对比，不能在评测中心继续登记为独立 `external_test`；本轮标记 `development`。默认权重网页任务实际只找到 1 个视频内 ID、匹配 2/1956 GT，无法用于羊群盘点或防丢失。UI 自动化的标注选择器崩溃不影响同一 API 的评测记录，但不能声称页面播放和评测卡片已验证。运行时 `data/media/evaluations/*` 标注文件已忽略，勿加入 Git。首页接口以最近任务计算牛数，羊任务会显示 0；历史告警仍独立保留，需改产品口径。
- 2026-10-15：ICAERUS YOLO11n 模型 README 未明确使用 Zenodo 12094356 视频，但其训练图像来源 Zenodo 18889623 同属 ICAERUS 2023–2026 年数据积累，无法证明无重复场景。仓库标 GPL-3.0，模型专属许可未见，网页接入/分发须先厘清许可和来源，并在其他来源的视频上独立验证。

- 2026-10-14：交付默认模型在 ICAERUS 俯视羊视频上几乎漏检（99 帧/1956 GT 框仅 2 TP）；Precision=100% 只是 2 个样本的结果。ICAERUS 官方 YOLO11n 权重在同一视频效果较好，但官方模型仓库本身也使用同项目的无人机羊数据，独立性未知。当前 H.264 演示视频由原视频、模型轨迹 CSV 再绘制，不修改原始预测；侧栏“低/中/高”是未做相机运动补偿的画面位移，不是行走/奔跑/健康分类。公开权重存于被忽略的 `data/external/sheep_icaerus_model/raw/`，不提交模型大文件。

- 2026-10-14：Zenodo 12094356 包的官方许可字段是 `metadata.license.id=cc-by-4.0`；原始说明文本把羊标注目录误写成 cows，但四个 `gt/labels.txt` 都是 `sheep`。标注为 MOT 像素左上角框，帧号从 1 开始；评测中心要 0-based 和归一化 xywh。四段视频全是无人机通道视角，不能用作固定牧场机位的泛化结论，更无行为/健康/诊疗标签。原始压缩包已验证后清理分段缓存，保留官方 ZIP 与解压文件；不提交大文件。

- 2026-10-14：公开 Mendeley 羊行为数据存在 standing/walking 与 grazing/running/sitting 视频级类别，论文指出片段可能混有多只羊及多种活动。原始文件 API 返回 401，不能声称已经下载或训练。Zenodo 12094356 官方记录有 `Sheep_video_annotations_datasets.zip`（157,760,285 字节，MD5 `1ec2048d4975f5d68e04c3229cb03d40`），本机下载未完成且服务端 Range 请求不提供续传，残缺文件已删除。无真实数据时评估中心不得显示构造指标。
- 2026-10-14：评估中心以归一化左上角 GT 框和像素中心点的追踪框按 IoU 0.5 匹配；只评估带 GT 标注的帧，未标注帧不计 FP。个体趋势必须有人工耳标关联和至少两个有效视频点。羊位移受镜头运动和遮挡影响，仅是轨迹观察，不能直接解释为采食、躺卧或健康评分。

- 2026-10-14：公开行为/追踪数据与“未来疾病”标签是不同任务。MmCows 虽有健康记录，但尚未证实具有可直接使用的疾病确诊/发病前标签；牛跛行专家评分只支撑跛行筛查评估。CVB/CBVD 已在研发中暴露，不得重命名为独立外部验收集。

- 2026-10-14：本轮任务历史和复核保存在 SQLite；跨视频编号只能由现场人员核对耳标后手动关联，Track ID 本身不稳定。新视频结果含 `track_ids`，旧牛视频可从健康证据回退获取；旧羊视频若无 `track_ids` 无法关联，需重新处理。兽医诊断需填记录出处，但系统无法独立核验，固定标记 `user_recorded`。删除最后一个且已有回访的关联会被拒绝，避免回访记录失去可访问的档案。`yolo26n.pt` 是本轮前就存在的未跟踪模型文件，不得提交或清理。

- 2026-10-14：检测权重含 sheep=0、cattle=1，但原健康规则、行为模型和 Isolation Forest 的产品解释均以牛为对象。羊只可检测追踪，不能直接套用牛阈值或牛行为模型；前端视频“默认牛”映射 class_id=1。健康证据图谱连接既有告警与评分，不是诊断模型。Track ID 仅视频内有效。

- Windows 多进程 DataLoader 会触发 `nvfuser_codegen.dll / WinError 1114`，正式训练必须 `workers=0`。
- 测试集读取有原子记录机制，重复读取会被拒绝；任何调参只允许用验证集。
- 当前冻结 test 中 59 个源视频有 37 个曾出现在历史 strict/extended 研发实验（745/1,032 样本）。这不是本次 train/test 泄漏，但不能声称为研发过程完全未暴露的独立确认集，也不能事后把剩余 22 个视频重组为“干净测试集”。
- Kinetics 臂在 test 上优于冻结候选，但不得在看到 test 后改选；当前结论必须保留为负晋级结果。
- 模型加载绑定 checkpoint 哈希 / 标签空间 / 类别顺序，不一致会拒绝加载；不要手工改 `models/` 目录。
- CBVD-5 零样本 Macro-F1 仅 0.0048，当前行为模型不能跨域直接部署，必须走 CBVD4 域适应路线。
- 当前 CVB 模型在不均衡验证集上 Macro-F1 只有 0.2189，汇报效果禁止只看 Accuracy。
- 仓库路径含中文，脚本必须显式按 UTF-8 处理路径与子进程输出（主线近期一组修复即为此，勿回退）。
- Windows + torch 2.0.0 下 `torch.save` 不能接受非 ASCII 路径：PyTorch 的 C++ 检查点
  写入器用 ANSI 代码页解析父目录，对 `F:\new大创\...` 一律抛
  `RuntimeError: Parent directory ... does not exist`（纯 ASCII 路径正常）。
  Ultralytics 自己的 `save_model` 用 `BytesIO` + `Path.write_bytes` 绕开了这个坑，
  但 `final_eval` → `strip_optimizer` 直接调 `torch.save`，会让训练在跑完所有 epoch
  之后的最后一步失败。WAID 训练现在用 `unicode_safe_torch_save()` 包住
  `YOLO.train()`；动这条链路前先看 `tests/test_waid_repro.py::WaidUnicodeCheckpointTest`。
- `mock.patch.dict(sys.modules, ...)` 会对整张模块表做快照并在退出时恢复，块内新导入的
  模块（例如训练运行时的 `torch`）会被一并清掉，之后再次 `import torch` 会报
  `'_has_torch_function' already has a docstring` / `_C is not defined`。测试里改用
  `installed_ultralytics()`，只替换 `ultralytics` 这一个键。

## 中断点

- 本轮行为局部放大复核已完成并验证；正式本地服务 8000/5173 可用，浏览器已打开演示任务。无半成品。后续需要独立牧场视频和人工可判读性标注。原有未跟踪 `yolo26n.pt` 未改动。

- 本轮是只读素材审计并提交核查文档；未上传候选视频到正式服务，未生成空间报告或修改模型。下一步可先用 `272.mp4` 演示单段画区，再寻找有人工区域/栏门真值的长视频。原有未跟踪 `yolo26n.pt` 未改动。

- 本轮牛训练素材演示已跑通，正式本地 API 8000 与网页 5173 保持运行，页面入口可点击。测试与构建结果见上方新记录；原有未跟踪 `yolo26n.pt` 未改动。下一步需要更长的授权牧场固定机位视频和现场真值。

- 本轮代码、测试与本地服务启动均已完成；没有半成品算法或运行中的训练。正式服务为 API `127.0.0.1:8000`、网页 `127.0.0.1:5173`。待办事项依赖授权固定机位视频和真实台账；旧公开视频只能演示页面入口，不能证明现场计数或趋势效果。`yolo26n.pt` 为接手前未跟踪文件，本轮未改动或提交。

## 中断记录

- 2026-10-22 本轮停点：三项功能均已合入 `integration`。主线 Python 667 passed / 4 skipped、前端 55 passed、构建成功；正式 8000/5173 可访问、待办 0 条，浏览器已实际生成历史羊视频摘要。隔离 8001/5174 已停止。下一步用授权牧场牛羊原视频、现场人员和真实打印/PDF 检验实用性；原有 `yolo26n.pt` 不动。

- 2026-10-22 本轮停点：用户询问短期产品功能建议，建议方向待其选择；本轮没有新增产品功能。接手基线检查暴露日期敏感测试失败，已用 `03f39cf` 修复并完成聚焦及全量验证（Python 664 passed / 4 skipped，前端 49 passed）。原有未跟踪 `yolo26n.pt` 保持不动。

- 2026-10-16 本轮停点：视频结果内按任务查询盘点已提交（`d4473a7` 设计/计划、`a348782` 后端、`89622d6` 前端、`c442492` 说明/验收）。隔离 8001 的 102 条记录完成 Chrome 验收，旧目标记录不在无参最近 100 条里，但结果页通过 `job_id` 请求显示；截图和 JSON 位于被忽略的 `data/verification/video-inventory-scope.{png,json}`。隔离服务已停止。正式 8000/5173 已重启（API PID 4084、Web PID 42924），盘点分页与该任务查询均为 0 条，看板仍为最近牛视频 26 个 ID、84 条历史未处理提示，网页 HTTP 200。全量后端 `664 passed / 4 skipped`、前端 `49 passed`、构建成功。无半成品；下一步需授权牧场牛羊原视频、真实台账与现场复点。原有未跟踪 `yolo26n.pt` 不得提交或清理。

- 2026-10-16 本轮停点：全局圈舍盘点历史分页与筛选已提交（`e746752` 设计/计划、`a49d2b2` 后端、`378a56c` 前端、`721c472` 测试、`78821b1` 说明/验收）。隔离 8001 的 25 条记录完成 Chrome 点击验收，截图和 JSON 在被忽略的 `data/verification/inventory-history-pagination.{png,json}`；隔离服务已停止。正式 8000/5173 已重启（API PID 18408、Web PID 2600），正式盘点分页 API `total=0`，看板仍为最近牛视频 26 个 ID、84 条历史未处理提示，网页 HTTP 200。全量后端 `663 passed / 4 skipped`、前端 `48 passed`、构建成功。下一步优先取得授权牧场视频、真实台账和现场复点；软件后续可按 `job_id` 查询视频内嵌盘点记录。原有未跟踪 `yolo26n.pt` 不得提交或清理。

- 2026-10-16 本轮停点：历史盘点打开视频证据的功能、异常响应校验、审查修复、浏览器验收、README、计划勾选和交接均已完成。功能提交 `962e615`、`0cfd5d8`、`b5b1e07`、`85f94d7`、`4023d75`，验收文档提交 `4643a9a`；截图与结构化请求证据在被忽略的 `data/verification/inventory-video-navigation.{png,json}`，隔离 8001 已停止。正式 8000/5173 已用 PyTorch 环境重启（API PID 36200、Web PID 27496），正式盘点 API 和 SQLite 均为 0，网页 HTTP 200；管理看板为最近牛视频 26 个 ID、84 条历史未处理提示。最终后端 `661 passed / 4 skipped`，前端 `46 passed`，构建成功；没有半成品代码或运行中的训练。下一步等待授权牧场视频、真实台账和现场复点，或实现盘点历史分页。预存未跟踪 `yolo26n.pt` 不得提交或清理。

- 2026-10-16 本轮停点：圈舍盘点实现提交为 `f4794be`、`b7a1ea8`、`d7faddf`，审查修复为 `91a64b3`；隔离 8001 服务已停止，截图保存在被忽略的 `data/verification/inventory-browser.png`，正式数据库无验收盘点记录。最初重启因自动审批额度不足未执行；额度恢复后已用 PyTorch 环境启动新版交付服务：8000 PID 11376、5173 PID 12124，`/api/inventory-checks` 返回 0 条，管理看板返回最近牛视频 Track ID 26、处理时间 `2026-09-29T17:47:46+08:00`、历史未处理提示 84，网页 HTTP 200。预存未跟踪 `yolo26n.pt` 不得提交或清理。

- 2026-10-15 本轮后续停点：圈舍核对建议稿 `d8d1ef6` 已提交，牛视频隔离复跑与 Chrome 图谱验收记录见 `docs/2026-10-15-cattle-browser-health-acceptance.md`；8001 已停止，正式 8000/5173 仍运行，`yolo26n.pt` 是唯一既有未跟踪文件。用户路线/设计选择的异步问题尚未收到答复；若答复同意推荐方案，从规格定稿、实施计划与 TDD 开始。不要将默认羊模型的 1 个 ID 或牛开发视频的 26 个 ID 用作真实存栏真值。

- 2026-10-15 本轮停点：浏览器纠错、复核和三项下载已在隔离数据库副本验收，正式数据库未写入测试记录，8001 已停；只有原有未跟踪 `yolo26n.pt`，未清理。下一步推进圈舍存栏核对设计，优先防止视频漏拍/漏检造成误报；用户对圈舍数或耳标优先路线的答复仍待取得。详情 `docs/2026-10-15-browser-interaction-acceptance.md`。

- 2026-10-15 本轮新增停点：提交 `51d4c21` 修复浏览器视频编码、`6d2fec4` 修正 Track ID 标题，交付服务已以 PyTorch 环境重启。Chrome 无头真实打开羊任务，视频播放进度从 0 到 4.9 秒，评测卡片也显示同源 `development` 指标；最新截图在 `data/verification/sheep-browser-{playback,evaluation}.png`。下一步在浏览器操作人工纠错、复核保存与下载链接，然后依用户回复设计防丢失核对。其他实验与模型权重未改动。

- 2026-10-15 本轮停点：看板 API/前端修正、README、测试及实施记录已完成并验证；交付服务已重启，新 API 在真实数据上返回 26 个最近牛视频 Track ID（2026-09-29 处理）及 84 条历史未处理提示。本机 Chrome 无头渲染 DOM 也出现新标签、处理时间及 26/84 数值；截图只拍到首屏，网页评测卡片、视频实际播放、人工纠错和下载操作尚未交互复核。下一步先复核这些浏览器交互；防丢失功能仍等用户对圈舍数/耳标方案的答复。预存未跟踪 `yolo26n.pt` 不得提交或清理。

- 2026-10-15 本轮停点：提交 `7890c0a` 保存网页羊视频实测记录与 `.gitignore`，`9bb30a8` 更新交接；后续补充公开模型来源/许可调查。本地 API/网页曾在 `127.0.0.1:8000/5173` 启动，是否仍运行须重新检查，不凭 PID 文件判断。任务 ID `b6584849f10c403c8a1404e8f91748b8`、评测 ID `9cc4bc9791364cfdbf9329e8e7a0dc2b`，原始/结果/GT 均保留本机；浏览器自动化连接崩溃，页面上的评测卡片、播放、纠错仍待实际观察。下一步先处理上一节未完成的网页复核和首页口径，再推进防丢失流程。`yolo26n.pt` 为原有未跟踪文件，不要清理。

- 2026-10-14 本轮停点：功能提交 `27284a2`；视频、两模型轨迹和 `evaluation.json` 均在 `data/verification/icaerus_sheep_20261014/`，可直接观看 H.264 `icaerus_yolo11n/crop_23.11.23-12_demo.mp4`。无运行中的推理/下载/训练任务。下一步如继续产品化，从交付网页真实上传及评测中心导入开始；当前主线只有原有未跟踪 `yolo26n.pt`。

- 2026-10-14 本轮停点：数据下载、整包 MD5/ZIP CRC、四段视频逐帧解码、MOT 帧号/框/ID 核对和四份评测 CSV 已完成；原始与衍生文件位置见 `docs/2026-10-14-icaerus-sheep-video-download.md`。没有下载或训练进程待恢复，尚未上传公开视频运行模型或生成外部指标。下一步按上方待办第二项，从最短 `crop_23.11.23-12.MP4` 开始真实评测。用户原有未跟踪文件 `yolo26n.pt` 保留。

- 2026-10-14 本轮停点：主线五个功能提交依次为 `fed76dc`、`ac260af`、`3f035c4`、`7ae19e8`、`678e70b`；最终全量测试为后端 `643 passed, 4 skipped`、前端 26 passed、前端构建成功。无训练、下载或服务进程需恢复。公开羊原视频下载受接口认证和网络中断阻碍，未生成外部评估结果。工作树仅有预先存在、用户所有的未跟踪 `yolo26n.pt`。下一步是获取可核验的公开羊视频和标注，再跑真实导入验收；新牧场验收仍待用户素材。

- 2026-10-14 本轮停点：`integration` 已提交 `15bbaef`、`e569f74`；对应测试和构建全绿。没有正在运行的任务或半成品代码。后续从上方产品验收第一项继续；必须先拿到新的真实牧场牛羊视频。当前工作树仅保留预先存在的未跟踪 `yolo26n.pt`。

- 2026-10-14：本轮测试修复提交 `4c7e711`，产品演示提交 `7bc6df8`，均在 `integration`；无训练或服务进程需恢复。未跟踪的 `yolo26n.pt` 在接手时已存在，未纳入本轮。完整后端 `pytest -q -p no:cacheprovider --tb=line` 为 **628 passed / 4 skipped**；本轮聚焦测试 20 passed、前端 20 passed、构建成功。后续真实牧场验证待用户提供素材。

- 2026-09-30：WAID 复核重新运行真实 check-only、verifier 和聚焦测试：
  `status=ready`、当前 verifier `status=passed`、45 项聚焦测试通过；前端 16 项通过且
  构建成功；全量 Python 588 通过 / 4 跳过 / 2 项既有失败。代码审查发现 0 个
  Critical、6 个 Important，并用真实路径和 Ultralytics 8.4.22 源码逐项复现或确认。
  当前停在设计选择前，尚未修改生产实现；下一步需用户确认“完整加固”或“缩小复现声明”。
- 2026-09-22：CBVD4 冻结实验与正式报告已收尾。实验分支 HEAD=`6add827`；无训练进程需要恢复。下一执行点是“开发集多 seed/站立反刍改进方案 + 新前瞻性确认数据”，不是重跑当前 test。实验 worktree 仅剩 3 个用户所有的未跟踪文档，保持原样。
- 2026-09-22 13:27：多 seed 第一条新增训练已启动。实验分支 HEAD=
  `4869354`。当前训练在首轮尚未写出 history 时已确认进程存活；协议仅含
  train/val。旧自动化 ID `cbvd4` 在 Codex app 中已不存在，未自动新建。
- 2026-09-23：Kinetics seed 20260901 在完成 epoch 11 后曾无最终摘要退出；
  `last.pt` 与 binding 哈希一致，确认无重复进程后按冻结参数 `--resume`，
  当前识别到 PID 6164。最后检查已完成 epoch 12，尚无最终摘要。汇总实现
  `38a4517` 及审计加固 `30ed5f8`/`7cba9f5`/`e7723b3` 已通过 60 项聚焦测试，
  计划更新 `ed91bbb`；下一
  动作是等待本臂正常结束，核验最终摘要后串行启动 CVB-transfer seed
  20260901，不得并行占用单 GPU，也不得读取正式 test。
- 2026-09-29：WAID4500 收尾。Codex 停在 `f510859`（Task 9 未执行，卡在等审批时额度耗尽）。
  本次在同一 worktree 补齐 Task 9：聚焦/全量 Python 测试、真实 check-only、真实
  verifier、真实 1 epoch 冒烟训练、前端测试与构建。冒烟首次运行暴露上述非 ASCII
  路径缺陷（Codex 从未跑到这一步），已按 TDD 修复并提交 `f18bd4d`；随后冒烟退出码 0。
  未做：合并到 `integration`、剩余三条多 seed 臂。上一条 2026-09-23 记录的
  Kinetics seed 20260901 已于当日 20:57 正常结束（见「已完成」）。
- 2026-09-29 20:02：WAID 收尾已提交并快进合并（`integration` HEAD=`1a8d033`），随后
  启动多 seed 矩阵第 2 条新增臂 CVB-transfer seed 20260901，PID 6152，工作目录
  `.worktrees/cross-domain-behavior`，完整命令行：

  ```powershell
  & 'F:\deepl\anaconda1\envs\pytorch\python.exe' -u -X utf8 -m scripts.train_cbvd4_behavior `
    --mode train --development-only --project-root . `
    --manifest-root data/external/cbvd5/manifests/cbvd4 `
    --output-root outputs/cbvd4/paper_20260922/multiseed_validation/cvb_transfer_init/seed_20260901 `
    --initialization cvb_transfer_init --source-checkpoint models/behavior/cvb_x3d_v2_best.pt `
    --device cuda --epochs 30 --batch-size 8 --accumulation-steps 2 --learning-rate 3e-4 `
    --weight-decay 1e-4 --patience 6 --workers 0 --seed 20260901 --freeze-backbone-epochs 2
  ```

  启动时已核对：GPU 空闲（0 MiB/8188 MiB）、无其他 python 进程、两个起训权重与
  train/val 清单及视频数据齐备、目标输出目录不存在；`training_protocol.json`
  `test_data_read=false`。中断处理：确认无重复进程后，用上面完全相同命令加
  `--resume`；不得删除失败运行或换种子。
- 2026-09-29 22:44：上述进程在写完 epoch 2 后**静默消失**（`history.csv` 止于 epoch 2，
  `stdout.log` 一直为 0 字节，`stderr.log` 停在上一次启动时刻）。排查证据：应用程序日志与
  系统日志在该时间窗内没有任何 python.exe 错误、AppCrash 或内存耗尽记录，系统日志只有
  显卡 RTD3 电源状态事件 → 判定为外部终止（把训练当普通后台任务跑，被会话/系统回收），
  不是训练代码缺陷。这也解释了上一臂 2026-09-23「完成 epoch 11 后无最终摘要退出」的同类
  现象。
- 2026-09-30 11:49：第一次尝试从断点恢复 CVB-transfer seed 20260901。命令与上面完全相同，
  只追加 `--resume`；改用 **`Start-Process` 脱离式独立进程**（PID 29912），日志
  `cvb_transfer_seed_20260901_resume_20260929.{stdout,stderr}.log`。自检时（+3 分钟）GPU
  已升到 4356 MiB、`resume_binding.json` 校验通过、无绑定错误；但命令返回后不久该进程
  又被静默回收（`stdout` 0 字节、`stderr` 只有 TypedStorage 警告、无回溯），断点文件未被
  破坏。**教训：本环境会把手动脱离的子进程当游离进程回收，脱离式启动不可用。**
- 2026-09-30 11:52:54：第二次恢复，改用**会话托管的后台任务**（本会话唯一能长跑的形态），
  PID 3368，命令同前（含 `--resume`），日志
  `cvb_transfer_seed_20260901_resume_20260930.{stdout,stderr}.log`，PID 文件已更新为 3368。
  自检：GPU 4356 MiB、利用率 100%（确在训练 epoch 3）、命令行含 `--resume`、无重复进程。
  注意：跑完前 `stdout.log` 为空是正常的，最终 JSON 摘要只在结束时写出；进度看 `history.csv`。
  若该后台任务再被回收，按同一命令加 `--resume` 重启即可，已完成 epoch 不丢。
  当天另有**另一个 Codex 会话**在按 `docs/WAID4500_REPRODUCIBILITY.md` 跑 check-only →
  verifier → pytest（只读，不占显存）；它若继续跑文档 §6 的 WAID 冒烟/完整训练，会与本臂
  争抢 8 GB 显存，本臂结束前不要启动。
- 2026-09-30 18:37：CVB-transfer seed 20260901 **正常收尾（不是中断）**：后台任务回报
  `resume_exit=0`，`stdout.log` 写出 7758 字节最终 JSON 摘要，patience=6 触发早停，停在
  epoch 11（最佳 epoch 5），validation Macro-F1=0.8325412642、accuracy=0.9146341463，
  `best.pt` SHA-256=`3f28cca2d984c1133d860afbae7e0d20de321cae0669c49b241a8a6a8ccb9857`，
  `test_metrics_read=false`，产物齐全。新一代 4 条臂至此完成 2 条；下一步 Kinetics
  seed 20260908（同命令换 `--output-root …/kinetics_init/seed_20260908`、
  `--initialization kinetics_init`、`--kinetics-checkpoint models/pretrained/X3D_XS.pyth`、
  `--seed 20260908`，去掉 `--source-checkpoint`），必须串行、不得并行占卡。
- 2026-09-30 19:28:36：启动第 3 条臂 Kinetics seed 20260908（PID 5256），工作目录
  `.worktrees/cross-domain-behavior`，完整命令行：

  ```powershell
  & 'F:\deepl\anaconda1\envs\pytorch\python.exe' -u -X utf8 -m scripts.train_cbvd4_behavior `
    --mode train --development-only --project-root . `
    --manifest-root data/external/cbvd5/manifests/cbvd4 `
    --output-root outputs/cbvd4/paper_20260922/multiseed_validation/kinetics_init/seed_20260908 `
    --initialization kinetics_init --kinetics-checkpoint models/pretrained/X3D_XS.pyth `
    --device cuda --epochs 30 --batch-size 8 --accumulation-steps 2 --learning-rate 3e-4 `
    --weight-decay 1e-4 --patience 6 --workers 0 --seed 20260908 --freeze-backbone-epochs 2
  ```

  后台任务形态（本环境唯一能长跑的形态），日志
  `outputs/cbvd4/paper_20260922/logs/kinetics_seed_20260908.{stdout,stderr}.log`，PID 文件同名
  `.pid`。启动自检：无重复进程、协议 `test_data_read=false`、清单哈希与冻结矩阵一致。
  中断处理：确认无重复进程后原命令加 `--resume`；不得删除失败运行或换种子。
- 2026-09-30 22:43：Kinetics seed 20260908 在写完 epoch 2 后**再次被静默终止**（`pwsh-2`
  回报 `killed before exit`，`stdout.log` 0 字节，`stderr` 只有 TypedStorage 警告）。与
  09-29 22:44 那次一致：**两晚都在 22:43--22:44 被杀**，而 22:30--23:00 的系统日志里
  **没有任何睡眠/关机/注销/事件日志重启记录**（已查 Kernel-Power/Kernel-General/User32/
  EventLog/Power-Troubleshooter）→ 判定为会话/服务层面的进程清理（托管任务随会话结束被杀），
  不是系统断电或训练缺陷。**规律：会话每夜停止一次，训练每晚最多推进到 22:43。**
- 2026-10-01 13:20:24：按原命令加 `--resume` 恢复第 3 条臂（PID 3396）。恢复前独立核验：
  `torch.load(last.pt)` 得到 `epoch=2` 且含完整 `model/optimizer/scheduler/scaler/rng/
  history/best_f1/patience`，非截断；`validate_resume_binding()` 用 `last.pt` 的 SHA-256
  与 `resume_binding.json` 比对通过（该函数不一致即抛错）。日志
  `kinetics_seed_20260908_resume_20261001.{stdout,stderr}.log`，PID 文件已更新为 3396。
  用户 2026-10-01 明确决定：**不重跑**（重跑要删既有运行、偏离冻结矩阵，且解决不了夜杀），
  **也不加计划任务/守护脚本**；被回收后由用户叫起、按同命令加 `--resume` 续跑。
- 2026-10-01 21:01：Kinetics seed 20260908 在写完 epoch 12 后**第三次被静默回收**（进程消失、
  `stdout.log` 0 字节、GPU 归零、无回溯）。注意**回收时机并不固定在 22:43**（前两次在
  22:43--22:44，这次在 21:01 之后），所以不能按点预测，只能靠 `history.csv` 与进程/GPU 判断。
  此时进度 13 轮（epoch 0--12），最佳 epoch 7=0.8436268208，自 epoch 7 起连续 5 轮未刷新。
- 2026-10-01 21:47:08：第二次续训（PID 7000），命令同前加 `--resume`，日志改为
  `kinetics_seed_20260908_resume2_20261001.{stdout,stderr}.log`（递增命名，避免覆盖前一次
  日志），PID 文件更新为 7000。自检：GPU 4370 MiB、绑定校验通过、无重复进程。
  **下一步只等 epoch 13**：若它不刷新 0.8436268208，patience=6 触发早停，本臂即收尾并写出
  最终 JSON 摘要（届时核对 `best_val_macro_f1`/`test_metrics_read=false` 与 `best.pt` 哈希）。
- 2026-10-01 22:34：Kinetics seed 20260908 **正常收尾**（`resume2_exit=0`，`stdout.log`
  8736 字节最终摘要）：epoch 13 得 0.8424501，未刷新 epoch 7 的 0.8436268208，patience=6
  触发早停，共 14 轮。核对：`epochs_completed=14`、`best_val_macro_f1=0.8436268208269122`、
  `best.pt` 实际 SHA-256 与 `validation_metrics.json` 记录同为
  `5802f043d5a177b7cd1a3c90106254a22e176817d8918f86fdf1e8af1de4318d`、
  `test_metrics_read=false`、清单哈希与冻结矩阵一致。Kinetics 臂三 seed 齐全
  （0.8398443 / 0.8530159 / 0.8436268）。**六格只剩 CVB-transfer seed 20260908。**

- 2026-10-02：WAID 复现加固第 1 批（3 项，TDD，每项先看 RED）：
  1) 导入可移植性：`import_assets()` 复制冻结数据集后用 `write_runtime_data_yaml()`
     重写 `data.yaml`（并重算该组件清单，保持 file/bytes 统计真实）；`rebuild_dataset()`
     改用同一函数消除重复实现。
  2) PowerShell `rebuild` 默认输出由 `data\external\waid\derived\waid4500_v1`（冻结目录，
     必然已存在 → `rebuild_dataset` 拒绝）改为 `derived\waid4500_rebuilt`，与指南 §4 一致。
  3) 续训越界防护：新增 `recorded_output_root()` / `require_portable_resume()`，在
     `run_training()` 里于任何重活之前校验检查点记录的输出根必须落在配置的
     `project` 之内。证据：归档检查点 `train_args.project=E:\大创\WAID_YOLO11\runs`；
     Ultralytics `engine/trainer.py:845-851` 续训时 `self.args = get_cfg(ckpt_args)`。
     实测：归档 checkpoint REFUSED、`reproduced/smoke_e1` ACCEPTED。
  提交 `2ea7dc6`、`733cbbb`；聚焦 48 passed、worktree 全量 591 passed / 4 skipped /
  2 项既有失败。**下一步**：五类资产整批导入事务；verifier 全量样本/固定划分校验与逐样本
  内容哈希（后两项需用户确认声明口径）。

- 2026-10-02：WAID 复现加固第 2 批（**整批导入事务**，用户指定先做这一项，不动声明口径）：
  `import_assets()` 改为两阶段——先把五类资产全部复制到各自的兄弟暂存目录并逐一校验
  （新增 `_stage_asset()`，替代原先边拷边发布的 `_copy_asset()`），再统一发布；发布阶段任一
  失败即整体回滚：移除已发布组件、把被替换的旧资产从备份恢复，全部成功后才删除备份。
  RED 测试 `test_batch_import_publishes_nothing_when_a_later_component_fails` 先失败
  （原先中途失败会在项目里残留 `data/external/waid/raw`）。提交 `7080174`；聚焦 49 passed、
  全量 592 passed / 4 skipped / 2 项既有失败。**剩余 2 项**（verifier 全量 4,720 样本与固定
  划分校验、逐样本内容哈希）直接决定能否声明"完整复现证据全部通过"，等用户定调。

- 2026-10-02：WAID 复现加固第 3 批（**证据强度两项**，用户选定"两项都做"）：
  `verify_dataset_samples()` 逐条校验全部 4,720 个样本（图片/标签存在、`parse_label` 与
  清单元数据一致）并把 `splits/{train,valid,test}.txt` 的成员集合与清单划分比对；
  `sample_content_hashes()` / `write_sample_hashes()` / `load_sample_hashes()` /
  `verify_sample_hashes()` 记录并重算逐样本内容摘要（图片+标签），新增生成器
  `scripts/reproducibility/write_waid_sample_hashes.py`，跟踪文件
  `reproducibility/waid4500/dataset_samples.sha256`（4,720 行 / 1.2 MB）；verifier CLI 增加
  `--dataset` / `--sample-hashes`，整体 `status` 现聚合六层。RED 测试先失败（缺失 API，
  另有一次测试抓到"哈希文件接受任意相对路径"的真实弱点，已收紧为必须
  `images/<split>/` 前缀）。真实端到端：`status=passed`、样本 4,720/4,720、
  4,500/200/20、内容哈希 4,720/4,720。提交 `f6e6df7`；聚焦 58 passed、全量 601 passed /
  4 skipped / 2 项既有失败。**复核 6 项已全部处理，分支已由用户确认合并回 `integration`。**

- 2026-10-02 14:44:46：启动多 seed 矩阵最后一格 CVB-transfer seed 20260908（PID 28468），
  工作目录 `.worktrees/cross-domain-behavior`，完整命令行：

  ```powershell
  & 'F:\deepl\anaconda1\envs\pytorch\python.exe' -u -X utf8 -m scripts.train_cbvd4_behavior `
    --mode train --development-only --project-root . `
    --manifest-root data/external/cbvd5/manifests/cbvd4 `
    --output-root outputs/cbvd4/paper_20260922/multiseed_validation/cvb_transfer_init/seed_20260908 `
    --initialization cvb_transfer_init --source-checkpoint models/behavior/cvb_x3d_v2_best.pt `
    --device cuda --epochs 30 --batch-size 8 --accumulation-steps 2 --learning-rate 3e-4 `
    --weight-decay 1e-4 --patience 6 --workers 0 --seed 20260908 --freeze-backbone-epochs 2
  ```

  后台任务形态（本环境唯一能长跑的形态），日志
  `outputs/cbvd4/paper_20260922/logs/cvb_transfer_seed_20260908.{stdout,stderr}.log`，PID 文件
  同名 `.pid`。启动自检：无重复进程、GPU 空闲、协议 `test_data_read=false`、
  `evaluation_scope=train_val_only`、`source_checkpoint_sha256=731c6ed3…`（与 seed_20260901
  臂同源）、`kinetics_checkpoint_sha256=null`、清单哈希与冻结矩阵一致。中断处理：确认无
  重复进程后原命令加 `--resume`；不得删除失败运行或换种子。
- 2026-10-02 22:45：按用户要求**在 epoch 8 落盘后暂停**该臂（用户 22:16 指示「下一轮结束后
  暂停」）。做法：挂监视器（`cvb_transfer_seed_20260908.pause-watcher.log`）轮询
  `history.csv`，检测到第 9 行数据（epoch 8 @ 22:44:43）后再等 15 秒确认行数不再变化，
  才 `Stop-Process` 掉 PID 28468，并确认进程已退出（`still alive=False`）。这是**刻意的
  干净暂停**，不是崩溃：`last.pt`/`resume_binding.json`/`history.csv` 同一时刻写出，
  独立 `torch.load` 校验 `epoch=8`、`best_f1=0.8266304`、历史 9 条、
  optimizer/scheduler/scaler/rng 齐全 → 可原样 `--resume`。训练任务的
  `cvb_transfer_seed_20260908_exit=-1`（被主动 kill）与 `stdout.log` 为空都是预期现象，
  不要误判为失败运行。恢复命令即上面 14:44:46 那条命令加 `--resume`。
- 2026-10-03 12:25:27：按用户「继续下一个训练」的指示恢复该臂（**恢复前已确认无重复进程**、
  GPU 空闲，`last.pt` 为 epoch 8 完整状态）。命令 = 2026-10-02 14:44:46 那条原样加
  `--resume`，PID 6240，日志
  `outputs/cbvd4/paper_20260922/logs/cvb_transfer_seed_20260908_resume_20261002.{stdout,stderr}.log`
  （文件名后缀 20261002 只是调用时写的标签，实际启动为 2026-10-03 12:25:27），PID 文件已更新为
  6240。自检：`--resume` 生效、`validate_resume_binding()` 通过（stderr 无绑定错误）、
  GPU 4347 MiB / 100%（确在训练）。本次**未再挂暂停监视器**（用户未要求），训练将继续到
  早停或 30 轮上限。
- 2026-10-03 13:58:09：CVB-transfer seed 20260908 **正常收尾**（不是中断）：
  `cvb_transfer_seed_20260908_resume_exit=0`，恢复日志写出 7262 字节最终 JSON 摘要；
  epoch 9 = 0.8017、epoch 10 = 0.8181 均未刷新 epoch 4 的 0.8266304028，patience=6 触发
  早停，共 11 轮。核对：`val_macro_f1=0.8266304027953745`、`accuracy=0.8943089430894309`、
  `best.pt` 实际 SHA-256 与 `validation_metrics.json` 同为
  `0d3b19161a482fd3021ee843e75623b979a5f0b99d0180f9468b9d9aa604380e`、
  `test_metrics_read=false`、清单哈希与冻结矩阵一致；产物齐全（`metrics.json`、
  `classification_report.csv`、`confusion_matrix.*`、`training_curves.png`）。
  **多 seed 矩阵四条新臂至此全部跑完，六格齐全。** 下一步只剩计划 Task 7 汇总。
- 2026-10-03 14:49:02：计划 **Task 7 汇总完成**（`summarize_exit=0`，14:08:23 启动、耗时约
  41 分钟）：生成 `validation_metrics.csv`（6 行）、`aggregate.json`（39.6 KB）、`report.md`
  与 `analysis/<初始化>/seed_<seed>/validation_predictions.csv`（每格 984 条）。
  核对：`aggregate.json.test_data_read=false`、`seed_count_per_initialization=3`；
  Kinetics 均值 0.8454960（样本标准差 0.0067818）、CVB-transfer 均值 0.8336248
  （0.0066230）；配对差值 +0.0008785 / −0.0204746 / −0.0160163；逐类均值显示
  ruminating-standing 为两臂最弱（kinetics 0.624246 / cvb 0.591244）。
  **一处需知的差异**：最后一格训练内记录 0.8266304028、汇总统一重算为 0.8276105066
  （Δ≈0.00098），其余五格两者逐位一致；跨格比较以统一重算的 CSV 为准。
  本轮为 validation-only，**未读取正式 test**；矩阵至此结清，按预注册不作候选选择。
  `report.md` 亦明确写着 `No promotion decision is made from this validation-only experiment.`

## 还原上一段对话

最近 Codex 会话日志在 `C:\Users\Mrda\.codex\sessions\`（按日期分目录，`rollout-*.jsonl`）。
本次接手读的是 `2026\09\29\rollout-2026-09-29T17-54-22-*.jsonl` 等文件：Codex 已完成
Task 1--8 并提交到 `f510859`，开始 Task 9 后先跑通聚焦 40 项与全量测试（583 通过 /
2 失败）、前端测试与构建，随后临时把分支里的 `reproducibility/` 复制到 `F:\new大创`
以便对真实资产运行 check-only 与 verifier —— 就在这条命令的审批请求处额度耗尽，
Task 9 Step 2 起（真实 check-only、冒烟、verifier、HANDOFF 提交）全部未执行。

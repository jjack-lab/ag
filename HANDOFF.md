# HANDOFF.md — 交接台账

> 谁在干活谁维护。任何 AI 接手第一步：读完本文件 → `git log --oneline -10` + `git status` + `git worktree list` 核对 → 跑测试 → 从「下一步」清单继续。规则见 `AGENTS.md`。

- 最后更新：2026-10-15（管理看板已按最近牛视频与历史规则提示的真实口径修正；页面评测展示和实际播放仍待复核。下方旧实验记录仅作历史参考。）

## 当前阶段目标

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

- 网页真实上传与评测 API 导入已完成，浏览器在标注文件选择器崩溃后当前连接不可用，故尚未在页面确认评测卡片和播放器实际播放。首页看板口径已修正并用真实 API 核对，页面实际交互还未观察。已向用户询问防丢失提醒先按圈舍存栏数还是逐只耳标核对。

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

- [x] 取得可完整下载的羊原视频及对应标注，核验出处/许可/版本/哈希和标注粒度，转换评测中心的 GT CSV；已完成 ICAERUS 官方 Zenodo 12094356 的四段视频和 MOT 标注，见 `docs/2026-10-14-icaerus-sheep-video-download.md`。转换规则与原始标注保留；当前转换为一次性数据处理，若要自动重复执行，再补独立脚本。
- [x] 已用上述公开羊视频在本项目 pipeline 实跑默认模型与公开羊专用模型，生成 H.264 证据面板视频和本样例测量，详见 `docs/2026-10-14-icaerus-sheep-model-demo.md`。
- [ ] 网页上传任务及同一 API 的 GT 导入已完成（见 `docs/2026-10-15-web-sheep-acceptance.md`）；浏览器恢复后核对评测卡片、播放器实际播放、人工纠错交互和下载操作。网页默认模型 Recall 0.102%，不能以羊专用演示模型视频冒充该任务结果。
- [x] 修正首页“今日监测牛只”、历史告警和 Track ID 的显示口径；用户确认“最近牛视频 Track ID 数＋处理时间、历史未处理规则提示、无牛视频显示暂无记录”。实现与测试已完成，真实 API 已核对；网页视觉与点击仍待恢复浏览器后复核。
- [ ] 根据用户对“按圈舍存栏数/逐只耳标”的答复，设计并实现防丢失核对流程；无完整拍摄覆盖或人工确认时不得输出确定丢失结论。
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

## 中断记录

- 2026-10-15 本轮停点：看板 API/前端修正、README、测试及实施记录已完成并验证；交付服务已重启，新 API 在真实数据上返回 26 个最近牛视频 Track ID（2026-09-29 处理）及 84 条历史未处理提示。浏览器自动化仍无可用连接，网页评测卡片、视频实际播放、人工纠错和下载操作尚未目视验证。下一步先复核这些浏览器交互；防丢失功能仍等用户对圈舍数/耳标方案的答复。预存未跟踪 `yolo26n.pt` 不得提交或清理。

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

# 羊检测独立评测实施计划

**目标：**用 AUTH-Sheep 的独立视频与逐帧 HBB 标注，实测现有和候选羊检测模型，保留可审计的失败样例。

**架构：**官方视频与标注保存在 Git 忽略目录。转换器读取 HBB JSON，按原视频帧号生成项目评测 CSV；现有检测评测器在相同帧和 IoU 门槛下计分。结果单独存档，不覆盖历史 ICAERUS 卡片或默认模型。

**技术：**Python 3.8、OpenCV、项目现有检测/评测模块、pytest。

## Task 1：固定来源与权利信息

- [ ] 从 Zenodo `13843376` 获取 `video1_annotations_hbb.json` 与 `ReadMe.txt`，核对 MD5、JSON 结构、视频帧号和许可证信息。
- [ ] 下载 `video1.mp4` 到 `data/external/auth_sheep/raw/`，核对官方 MD5 `df80976b22d869394d823bbaf68d736b`，统计帧数及首尾可解码性。
- [ ] 写 `docs/data/2026-10-25-auth-sheep-record.md`，列出 DOI、文件大小/哈希、权利状态和与 ICAERUS 不同来源的证据。

## Task 2：标注转换（TDD）

- [ ] 在 `delivery_tests/test_auth_sheep_import.py` 先用小型 HBB JSON 样例测试帧号、坐标、类别、越界、空帧转换，运行该测试确认 RED。
- [ ] 新增 `scripts/import_auth_sheep.py`，只实现测试所需转换，输出项目已有 GT CSV 格式和转换清单。
- [ ] 运行聚焦测试并复算真实 video1 标注总数、帧范围，人工查看抽样帧框对齐。

## Task 3：冻结评测

- [ ] 记录模型权重哈希、置信度/NMS/IoU、视频帧范围与评测版本，先运行网站默认模型。
- [ ] 在许可和训练来源核查后，在相同帧上运行 ICAERUS 候选；若候选权利状态不允许交付，仅保留研究比较。
- [ ] 输出每模型 TP/FP/FN、Precision/Recall/F1、视频内 ID 切换与失败样例；不修改已发表的历史数值。

## Task 4：验收和交接

- [ ] 全量 Python/前端测试及前端构建；保留实际退出码和失败项。
- [ ] 更新 `HANDOFF.md` 六节，按可验证单元提交代码、报告和交接记录。

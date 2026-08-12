# 第三方数据、代码与模型登记

更新日期：2026-07-29。

本登记用于大创科研交付的可审计性。标记“未下载”的资源仅是后续计划来源，不随当前交付包分发。

| 资源 | 来源 | 许可证/使用条件 | 本项目用途 | 当前状态 |
|---|---|---|---|---|
| WAID | [xiaohuicui/WAID](https://github.com/xiaohuicui/WAID)，[论文页面](https://www.mdpi.com/2076-3417/13/18/10397) | 本地副本和仓库首页未发现独立 LICENSE；当前仅按大学科研内部使用，公开再分发前须向作者确认 | 航拍动物检测训练与鲁棒性实验；不能解释为健康标签 | 已有本地数据；已训练 YOLO11s |
| CBVD-5 | [Kaggle 数据卡](https://www.kaggle.com/datasets/fandaoerji/cbvd-5cow-behavior-video-dataset/versions/8) | CC0 / Public Domain | 站立、卧倒、采食、饮水、反刍行为模型的主要训练集 | 未下载 |
| CVB | [CSIRO Research Data](https://researchdata.edu.au/cvb-a-video-visual-behaviors/2593248) | CC BY-NC-SA 4.0；仅非商业科研，衍生物保持相同许可并署名 | 行走等行为补充与跨数据集外部验证 | 未下载 |
| Counting cattle MOT | [Mendeley Data](https://data.mendeley.com/datasets/dk54zg67dd/1) | CC BY 4.0 | 多目标追踪、计数和 ID 稳定性外部验证 | 未下载 |
| MmCows | [neis-lab/mmcows](https://github.com/neis-lab/mmcows) | 代码 MIT；数据集 CC BY-NC-SA，具体以数据卡为准 | 行为、位置、健康记录和多模态趋势的外部验证 | 未下载 |
| CattleEyeView | [AnimalEyeQ/CattleEyeView](https://github.com/AnimalEyeQ/CattleEyeView) | 代码仓库 Apache-2.0；数据下载时再次核对数据条款 | 顶视牛只检测、追踪、姿态和评估思路 | 未下载 |
| PySlowFast | [facebookresearch/SlowFast](https://github.com/facebookresearch/slowfast) | Apache-2.0 | X3D/SlowFast 视频行为模型参考实现 | 未集成 |
| Ultralytics | [ultralytics/ultralytics](https://github.com/ultralytics/ultralytics)，[官方许可说明](https://www.ultralytics.com/license) | AGPL-3.0 或商业许可；当前大创科研交付按 AGPL-3.0 开源义务管理 | YOLO11 检测与 ByteTrack 调用接口、训练权重 | 已使用 |
| Lameness detection | [hrussel/lameness-detection](https://github.com/hrussel/lameness-detection) | Apache-2.0 | 跛行研究路线与姿态特征参考，不作为本阶段主模型 | 未集成 |

## 分发要求

- 不把未获明确再分发授权的数据集打包进交付压缩包；
- 论文、答辩 PPT 和演示页面必须区分“已实现”“计划接入”和“仅参考”；
- 数据许可证限制不得被代码许可证覆盖；
- 使用 CC BY 或 CC BY-NC-SA 数据时保留作者、论文、数据版本和访问日期；
- 若项目转为商业或闭源部署，必须重新评估 Ultralytics 和非商业数据集许可。

## Behavior preparation status

Open datasets are not copied into this repository automatically. Before adding
a source row, record the dataset name and concrete license text in the manifest.
CBVD-5 is the primary candidate for feeding, lying, and standing. CVB is
reserved for walking and external validation after its non-commercial
share-alike conditions are confirmed. `unknown` is used when an interval cannot
be assigned reliably.

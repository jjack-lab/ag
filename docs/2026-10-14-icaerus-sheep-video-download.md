# ICAERUS 公开羊视频及逐帧标注下载记录（2026-10-14）

## 来源与许可

- 官方记录：[Drone videos and their annotations of passing sheep](https://zenodo.org/records/12094356)，DOI `10.5281/zenodo.12094356`，Zenodo record `12094356`。官方 API 的 `metadata.license.id` 为 `cc-by-4.0`。使用时应注明原作者与 DOI。
- 原始文件：`Sheep_video_annotations_datasets.zip`，官方大小 `157760285` 字节，官方 MD5 `1ec2048d4975f5d68e04c3229cb03d40`。本机通过官方文件接口分段下载、按 Content-Range 检查每段长度、重组后核对大小与 MD5；本机 SHA-256 为 `fb2dee620a56cdfcd3effc7344940d2acb753e345816465325ff082cca504fb3`。
- 原始压缩包保存在 `data/external/sheep_zenodo_12094356/raw/Sheep_video_annotations_datasets.zip`；解压内容在同目录的 `derived/depot_zenodo_2_annotations/`。大文件与衍生数据被 `.gitignore` 排除，不进入 Git。

## 视频与标注配对

原始 ZIP 的 CRC 全部通过。每个视频均可完整逐帧解码，分辨率均为 1440×1080、9 fps。`MOT1.1/` 下同后缀 ZIP 中的 `gt/gt.txt` 是对应逐帧框和 Track ID；`gt/labels.txt` 为 `sheep`。MOT 帧号从 **1** 开始，覆盖视频全部帧；同一帧内 Track ID 无重复，所有框均在画面内。

| 视频 `Videos/` | 帧数 | MOT 标注行 | 不同 Track ID | 视频 SHA-256 | 评测 CSV SHA-256 |
| --- | ---: | ---: | ---: | --- | --- |
| `crop_23.11.23-10.MP4` | 297 | 4509 | 45 | `3924f576d457523b3e40591d17d26c1c726b5f2f215a52bb066c4af470d58790` | `30d68538dca465ec7dd408103205cac3d04186003329933457a79bf0704c3cb8` |
| `crop_23.11.23-12.MP4` | 99 | 1956 | 47 | `a161bf717ffdc56c6db29465b642a87cee9edf2bfdbf00c86e4d0089b72270e2` | `ece519fcd065005223ab0d1dc47ec85c78eaf6c279c53512e3ce0d923ee170ed` |
| `crop_23.11.23-13.MP4` | 117 | 4024 | 47 | `aed6777296a9ef113ff7d202f1827f72d34bdc43f549baa0120696c33a27d489` | `a9a2b83237aef7e9109f6df41525bf2240bb640cc06afaf0b243cedcc42349ce` |
| `crop_23.11.23-8.MP4` | 126 | 3876 | 47 | `c5caa845f5b9f5d2cb78d51994b827b13dab381738ee5ee8158ce9415218107c` | `d1178b22f81de0c892a827789e552660658a6b1a403736b351687a4fa9bcd3f3` |

总计 **4 段视频、639 帧、14,365 个标注框**。原始 MOT 行格式为 `frame,track_id,x,y,width,height,...`，前六列的框单位为像素、左上角坐标。`derived/ground_truth_csv/` 中另存了四个同名 CSV，列为 `frame_index,class_id,track_id,x,y,width,height`，可供本项目“数据分析 → 公开数据评测中心”导入。转换方法：`frame_index = frame - 1`，`class_id = 0`（本项目羊类），`x,width` 除以 1440，`y,height` 除以 1080；其余原始列保留在原 ZIP 的 `gt.txt` 中。CSV 是从公开标注转换所得，并非模型预测。

推荐先上传最短的 `crop_23.11.23-12.MP4`，识别类别选“羊”，任务完成后导入 `derived/ground_truth_csv/crop_23.11.23-12.csv`，来源 URL 填本页 Zenodo 记录，许可填 `CC BY 4.0`，划分标明为“外部测试”。这只是不同来源的无人机俯视羊群检测/追踪基准，**没有羊行为、健康、诊断或未来疾病标签**，也不代替新牧场固定机位验收。尚未在本轮运行模型评测，因此没有公开数据检测/追踪分数。

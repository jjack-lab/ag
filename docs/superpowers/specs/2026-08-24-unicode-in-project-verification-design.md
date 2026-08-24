# 项目内 Unicode 全量验证修复设计

## 背景与目标

CVB→CBVD-5 主实验、报告和答辩界面已经完成，但 Windows 下从 `F:\new大创` 运行全量 Python 测试时有 37 个失败。失败集中于 PyTorch 2.0 原生路径写入、OpenCV 路径写入、Windows PowerShell 5 对无 BOM UTF-8 脚本的解码，以及受限环境中解析用户主目录。用户最新边界禁止在 `F:\new大创` 外创建 ASCII 临时工作树，因此必须在项目内部获得可信验证。

目标是在不改变冻结模型、外部样本、指标、阈值、质量规则和实验产物的前提下，使测试夹具和真实图像输出支持 Unicode 项目路径，并保持删除/覆盖操作的失败关闭安全边界。

## 方案选择

采用显式兼容层，不采用全局 monkeypatch。

1. 测试夹具保存 PyTorch 对象时打开二进制文件句柄再调用 `torch.save`；生成 OpenCV 图片时先 `cv2.imencode`，再由 `Path.write_bytes` 写入。这样只修复测试准备阶段，不会掩盖产品代码中的直接路径调用。
2. Windows PowerShell 5 测试 harness 使用 `utf-8-sig` 写入，使中文绝对路径按 BOM 正确解码。测试脚本的业务逻辑保持不变。
3. 数据集安全替换仍严格解析实际输出路径；仅对安全根集合中的 `Path.home()` 解析增加受控回退。若实际输出路径无法解析，操作继续失败，不进行覆盖删除。
4. 真实数据集读取与图片识别结果使用项目级 Unicode 安全图像读写函数：读取通过 `Path.read_bytes` 与 `cv2.imdecode`，写入通过 `cv2.imencode` 与 `Path.write_bytes`。这样既避免中文路径下 `cv2.imread` 将有效帧误判为不可解码，也避免 `cv2.imwrite` 静默失败。

不采用以下方案：项目外 ASCII 工作树（违反用户边界）、`subst`（会被 `Path.resolve()` 还原）、全局替换 `torch.save`/`cv2.imwrite`（可能掩盖真实缺陷）。

## 组件与数据流

- `delivery_tests/io_helpers.py`：测试专用 `save_torch_fixture` 与 `write_cv_image_fixture`。
- `cattle_health_app/image_io.py`：产品专用 `read_cv_image` 与 `write_cv_image`；通过 Python 文件 API 读写，并验证扩展名与编码结果。
- `cattle_health_app/behavior/dataset.py`、`cattle_health_app/behavior/cvb_index.py` 与 `cattle_health_app/behavior/validate_index.py`：使用统一读图函数，保留现有不可解码处理语义。
- `cattle_health_app/behavior/prepare_dataset.py`：输出路径保持严格解析；安全根解析失败时使用规范化绝对文本路径进行保守比较。
- `delivery_tests/test_process_lifecycle_races.py`：唯一 PowerShell harness 执行入口改用 BOM。

数据和实验产物不经过这些兼容层重写；本修复只影响测试临时文件与应用新生成的识别图片。

## 错误处理与安全边界

- OpenCV 编码失败或扩展名缺失时抛出 `ValueError`，不留下伪成功结果。
- Unicode 安全读图对文件缺失、空文件、读取异常或无效编码返回 `None`，使数据集与索引校验继续按既有规则报告不可解码帧，而不把兼容层异常扩散为新接口。
- PyTorch 测试夹具创建父目录并使用上下文管理文件句柄。
- `_safe_replace` 对真实输出路径仍调用严格 `resolve()`；失败即中止。仅安全根的比较值允许回退，不扩大可删除范围。
- PowerShell harness 仍有 20 秒超时并捕获输出；只改变文件编码。

## 验证标准

1. 新增 Unicode 图像/torch 夹具与产品图像读写测试先失败后通过；缺失、空和损坏图片的读图语义有回归覆盖。
2. 原 18 个 behavior-model、7 个 training、3 个 data 和 11 个 PowerShell 路径失败分组全部通过。
3. 全量 Python 测试从 `F:\new大创` 内运行无失败；预期环境跳过保留并记录。
4. 跨域 22 项聚焦测试、前端 16 项测试、生产构建与配置了项目 Python 的交付预检继续通过。
5. Git 不跟踪测试临时文件、视频、逐样本预测或原始压力缓存。

## 非目标

- 不更新模型权重或重新推理。
- 不修改 CBVD-5 标签、清单或结果数字。
- 不实现少样本适配、VLM、RGB＋热成像或具身设备联动；这些仍是主实验完成后的最后阶段研究计划。

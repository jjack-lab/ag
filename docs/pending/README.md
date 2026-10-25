# 待实现的设计与测试（不参与测试收集）

这里放"已经写成测试、但对应实现还没做"的规格，避免它们留在 `tests/`、`delivery_tests/`
里让 `pytest` 在收集阶段直接报错。

| 文件 | 诉求 | 状态 |
| --- | --- | --- |
| `2026-10-25-sheep-model-routing-test.py.pending` | 羊视频自动路由到已核验的羊研究候选权重，牛视频继续用交付权重；候选缺失时拒绝静默回退 | 未实现：`cattle_health_app.model_registry` 里没有 `resolve_sheep_research_model` |

启用方式：实现对应函数与 `LocalMediaProcessor` 路由后，把文件改回
`delivery_tests/test_sheep_model_routing.py` 并重命名后缀即可。

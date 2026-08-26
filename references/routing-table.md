# Endpoint 路由表（Human-readable View）

> `references/endpoints.json` 是 Endpoint 配置的**唯一机器权威**。  
> 本文件只供人类阅读、审查和快速定位；程序不得从本 Markdown 解析运行配置。

## 读取方式

程序通过：

```python
from endpoint_registry import EndpointRegistry
registry = EndpointRegistry()
endpoint = registry.get("tikhub", "<platform>", "<capability>")
```

Legacy `research_planner.resolve_endpoint()` 仍保留，但内部已经委托给 `EndpointRegistry`，用于兼容旧 Douyin pipeline。

## 当前 Provider

```text
TikHub
```

TikHub 是当前数据 Provider，不是 `modular-research` Skill 本身。未来可增加其他 Provider Adapter。

## 当前平台能力概览

### Douyin（兼容能力）

当前机器 Registry 包含：

```text
video_detail
video_comments
user_profile
user_batch_profile
video_search
video_list
billboard_low_fan
billboard_hot_video
billboard_topic
billboard_challenge
```

已在旧项目中实测的能力与待验证能力均通过 `status / verified_at / notes` 在 `endpoints.json` 中区分。

### TikTok（V2 Foundation 已登记）

当前已按 TikHub 文档登记：

```text
creator_search_insights
creator_search_insights_detail
creator_search_insights_trend
creator_search_insights_videos
video_search
creator_posts
video_metrics
video_comments
video_detail
ad_keyframe_analysis
```

这些条目当前用于 Profile/Planner Foundation。`status=documented` 表示已核对当前文档中的 method/path，但**不等于已完成真实 API 运行验收，也不等于单价已核实**。

## 新增/修改 Endpoint 的规则

1. 只修改 `references/endpoints.json`；
2. 每个 Endpoint 独立确认 HTTP `method`；
3. 标注 `status=verified|documented|unverified`；
4. 只有真实运行核验后才可升级为 `verified`；
5. 单价未知时使用 `unit_price_usd: null`，不得编造；
6. 若变更影响 Legacy planner，运行 `python scripts/test_skill.py` 回归；
7. 更新本文件仅用于人类可读说明，不构成机器配置变更。

## 采集原则

继续坚持：

```text
先计划和估价
→ 小样本验证
→ 便宜/基础证据优先
→ 再扩大采集
```

具体 stage 顺序由 Research Profile 与后续 stage-based Planner 决定，不再全局写死一个跨平台采集顺序。

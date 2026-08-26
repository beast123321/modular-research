# Modular Research v1.1.1 发布说明

## 状态

`v1.1.1` 是在 v1.1.0 Douyin Video Intelligence 基线之上的 planner efficiency patch，重点修复标准抖音研究计划中过度 fan-out 的付费深挖问题，并让 `ResearchRequest.sample_size_overrides` 真正影响 Douyin network sampling。

本次改动：

- 保留 `douyin-video-intelligence-v1` 的候选发现与参考视频研究链；
- `candidate_limit` 与付费 statistics enrichment 解耦；
- 新增 `statistics_video_limit`，`fetch_video_statistics` 只深挖 shortlist，而不是默认覆盖整个候选池；
- Standard 默认采样调整为：
  - `candidate_limit=200`
  - `statistics_video_limit=20`
  - `creator_limit=6`
  - `comment_video_limit=6`
  - `comment_pages=3`
  - `deep_analysis_limit=8`
- `sample_size_overrides` 现在可覆盖 `candidate_limit`、`statistics_video_limit`、`creator_limit`、`comment_video_limit`、`comment_pages`；
- `statistics_video_limit` 始终不超过有效 `candidate_limit`；
- 非正整数/非法 sampling override 会被 Planner 拒绝，而不是静默扩大预算；
- 新增 `scripts/test_phase9_budget.py` 回归测试并接入 GitHub Actions。

## 标准预算基线

对一个单主题、一个可本地解析的抖音参考视频、Standard 深度、包含 Creator/VOC/Creative goals 的典型请求，当前计划基线为：

```text
REFERENCE_SEED       1
ORGANIC_DISCOVERY    3
STATISTICS          10
CREATOR_POSTS       12
USER_PROFILE         6
VOC expected         6
VOC max             18
-----------------------
EXPECTED_REQUESTS   38
MAX_REQUESTS        50
```

按当前混合定价估算上限约 `$0.050`。实际请求数仍取决于上游是否能取得足够的视频 ID / Creator ID；增加 seed keywords 会增加搜索请求，因此真实执行前仍必须以当次 `plan.max_cost_usd` 为准。

## 自定义采样

Canonical `ResearchRequest` 可以显式缩放网络采样：

```json
{
  "sample_size_overrides": {
    "candidate_limit": 40,
    "statistics_video_limit": 20,
    "creator_limit": 6,
    "comment_video_limit": 6,
    "comment_pages": 1
  }
}
```

`statistics_video_limit` 会自动被 `candidate_limit` 封顶。例如 `candidate_limit=9`、`statistics_video_limit=20` 时，只计划 9 条视频的 statistics enrichment，即最多 5 个 batch-of-two 请求。

## 兼容性

必须继续保持：

- TikTok Video Intelligence 行为不退化；
- `douyin-topic-radar-v1` 旧 Web endpoint contract 不退化；
- Douyin Video Intelligence reference/profile/planner/executor/normalizer/CLI 回归继续通过；
- Legacy Douyin CLI regression 继续通过；
- Evidence/Analysis/Creative/Synthesis 层保持 platform-neutral。

Douyin Video Intelligence V1 **不包含 Ads Intelligence**；`ads_analysis` 与 `retention_analysis` 不路由到该 Profile。

## 证据边界

已确认：

- planner budget optimization 有先 RED 后 GREEN 的自动化测试；
- GitHub Actions 在 Python 3.10 / 3.12 / 3.13 上执行全量离线回归；
- 网络执行默认关闭，真实 ResearchRun 仍需要 `--yes + --max-budget-usd`；
- 直接抖音 ID 的 URL 解析本身不产生 API 请求；
- App V3 comments 固定 `count=20`；
- statistics enrichment 每次最多 2 个作品 ID；
- raw Evidence 落盘前保持脱敏。

尚不能声称：

- Douyin App V3 endpoint 已在本项目当前执行环境完成真实 TikHub Provider live validation；
- Provider 默认价格等同于最终账单；
- Pattern Lift 表示因果关系或保证未来表现。

因此 App V3 Registry 状态保持 `documented`，不能写成 `live_verified`。

## 推荐下一步验收

更新 Agent 中的 Skill 到 `v1.1.1` 后，重新运行同一条抖音参考视频的 plan-only。首先确认 Standard 单主题计划不再出现 160 次 Creator Context fan-out，再配置 TikHub Key 做小额真实 Provider validation。

## License

当前仓库仍未声明许可证；本次 patch 不擅自添加 MIT、Apache-2.0 或其他许可证。

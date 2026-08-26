# Modular Research v1.1.0 发布说明

## 状态

`v1.1.0` 是在 v1.0.0 公共基线之上的 feature release candidate，核心新增 **Douyin Video Intelligence V1** 与参考视频研究入口。

本次新增：

- `ResearchRequest.reference_content`；
- 抖音参考链接本地 ID 解析：`/video/<id>`、`modal_id=<id>`、`aweme_id=<id>`；
- unresolved 短链的 Provider share-url fallback；
- `douyin-video-intelligence-v1` Profile；
- 保留 `douyin-topic-radar-v1` legacy Web contract，不覆盖旧能力；
- Douyin App V3 独立 endpoint capabilities；
- `REFERENCE_SEED → ORGANIC_DISCOVERY → CHEAP_RANKING → CREATOR_CONTEXT → VOC → VIDEO_UNDERSTANDING → PATTERN_MINING → FINDINGS → HYPOTHESES → BRIEFS` 规划链；
- `fetch_video_statistics` 的 `per_video_batch2` enrichment，最多 2 个作品 ID / Provider call；
- Douyin normalizer 与 platform-aware executor；
- repeatable `--reference-url` CLI convenience；
- Agent 使用约定：用户给自然语言目标与参考链接即可，不要求 endpoint/cursor/Profile ID/modal_id。

## 兼容性

必须继续保持：

- TikTok Video Intelligence 行为不退化；
- `douyin-topic-radar-v1` 旧 Web endpoint contract 不退化；
- Legacy Douyin CLI regression 继续通过；
- Evidence/Analysis/Creative/Synthesis 层保持 platform-neutral。

Douyin Video Intelligence V1 **不包含 Ads Intelligence**；`ads_analysis` 与 `retention_analysis` 不路由到该 Profile。

## 证据边界

已确认：

- Phase 9 reference/profile/planner/executor/normalizer/CLI 都有离线自动化测试；
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

## 推荐首次验收

先使用用户自己的公开抖音参考链接运行 plan-only：

```bash
python scripts/run_research.py \
  --topic "<研究主题>" \
  --platform douyin \
  --research-goal hooks \
  --research-goal low_follower_breakouts \
  --research-goal creator_analysis \
  --research-goal voc \
  --reference-url "<抖音参考链接>" \
  --depth quick \
  --plan-only
```

确认 plan、endpoint、request ceiling 与预算后，再在可访问 TikHub 的目标运行环境做小额真实验证。

## License

当前仓库仍未声明许可证；本次 release 不擅自添加 MIT、Apache-2.0 或其他许可证。

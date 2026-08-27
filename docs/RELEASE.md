# Modular Research v1.2.0 发布说明

## 状态

`v1.2.0` 是 TikTok Provider Verification release。它不扩大现有 bounded Research Planner、Standard sampling 或研究 fan-out；本次只把已有真实 Provider + normalizer 证据写回 Endpoint Registry，并加入可回归的 TikTok verification/release gate。

## 真实验证证据

2026-08-27 使用受控 TikHub live-validation harness 对 `standing desk / US` 完成一次真实 TikTok 验证：

```text
CALL_CEILING=12
CALLS_ATTEMPTED=12
CALLS_SUCCEEDED=12
CALLS_FAILED=0
ESTIMATED_MAX_COST_USD=0.012
PRICING_BASIS=provider_default
```

以下 12 个 capability 实际取得 Provider code 200，且对应 normalizer 调用完成：

```text
ad_percentile
ads_detail
ads_search
creator_posts
creator_search_insights
creator_search_insights_trend
top_ads_spotlight
top_contents_list
video_comments
video_detail
video_metrics
video_search
```

因此这些 capability 的 Registry verification metadata 升级为：

```text
status=live_verified
verified_at=2026-08-27
verification_basis=real_provider_response
validation_calls={attempted:12,succeeded:12,failed:0}
normalizer_validation=PASS
```

`PASS` 表示 Provider contract 与 normalizer 执行链完成；它不等价于每一种归一化 Evidence 类型都必须非空。未在真实 run 中调用的 TikTok capability 不据此升级，例如 `creator_search_insights_detail`、`creator_search_insights_videos`、`ad_keyframe_analysis`、`ad_interactive_analysis`、`top_contents_item_detail` 仍保持 `documented`。

## Pricing boundary

`$0.012` 是按 provider-default `$0.001/request` 计算的 hard-budget 规划上界，不是 Provider 最终账单，也不是任何单一 TikTok endpoint 的精确报价。

因此本次 12 个新 `live_verified` TikTok capability 全部继续保持：

```text
unit_price_usd=null
price_source=provider_default
is_endpoint_exact=false
```

需要 endpoint/day-specific 精确报价时，应单独使用 Provider 的价格查询能力，而不是从本次验证预算反推。

## Evidence boundary

公开仓库只保留脱敏 verification manifest：

`references/verifications/tiktok-provider-verification-v1.2.0.json`

其中只包含平台、日期、call summary、pricing basis、promoted/non-promoted capability，不包含 API Key、request payload、raw Provider response 或 response shape。真实 `live-validation.json` 仅用于受控验证与 promotion 过程，不进入 release tree。

## Douyin compatibility

v1.1.3 已验证的六个 Douyin capability 保持不变：

```text
video_detail_v3
video_search
video_comments_v3
user_profile_v3
creator_posts_v3
video_statistics_v3
```

它们仍保持 `verified_at=2026-08-26`、`validation_calls={attempted:6,succeeded:6,failed:0}` 和 `normalizer_validation=PASS`。Douyin share-url fallback 仍只是 `documented` contract。

## TDD / execution evidence

- TikTok real-provider run：GitHub Actions run `33042209247`，批准边界为最多 12 calls / `$0.012`；最终 `12/12` 成功。
- Phase 13 RED：run `33047117651` 精确失败于 `VERSION=1.1.3`，而 v1.2.0 release guard 要求 `1.2.0`。
- Sanitized evidence apply：run `33047369931`，artifact 下载、evidence-gated promotion、file-exact scope guard 与 commit 全部 PASS。
- 最终 PR 前 CI 继续使用 Python `3.10 / 3.12 / 3.13` 的 offline matrix；不注入 TikHub Key，也不执行付费请求。

## Security / repository boundary

本 release **不提交**：

- TikHub API Key；
- 本地 `config.json`；
- raw Provider response；
- `live-validation.json`；
- live-validation 本地输出目录；
- 一次性付费 Provider workflow / trigger marker；
- 一次性 evidence-apply workflow / trigger marker。

常规 CI 保持 offline，不注入 TikHub Key，不产生付费请求。

## License

当前仓库仍未声明许可证；v1.2.0 不添加 MIT、Apache-2.0 或其他许可证。

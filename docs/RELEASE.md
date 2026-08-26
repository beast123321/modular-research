# Modular Research v1.1.3 发布说明

## 状态

`v1.1.3` 是 Douyin Provider Verification Metadata release。它不扩大 v1.1.1 的 bounded Research Planner，也不增加新的付费研究 fan-out；本次只把已经取得真实 Provider 证据的 capability 状态写回 Endpoint Registry，并建立可回归的证据门槛。

## 真实验证证据

2026-08-26 使用 v1.1.2 bounded live-validation harness 完成一次受控 Douyin/TikHub 验证：

```text
CALL_CEILING=6
CALLS_ATTEMPTED=6
CALLS_SUCCEEDED=6
CALLS_FAILED=0
ESTIMATED_MAX_COST_USD=0.006
```

以下六个 capability 实际取得 Provider code 200，且响应通过 `scripts/normalizers/douyin.py`：

```text
video_detail_v3
video_search
video_comments_v3
user_profile_v3
creator_posts_v3
video_statistics_v3
```

Normalizer 在真实响应中分别产生了 video/snapshot/creator/comment 等非空 Evidence bundle；因此这六个 capability 的 Registry 状态升级为：

```text
status=live_verified
verified_at=2026-08-26
verification_basis=real_provider_response
validation_calls={attempted:6,succeeded:6,failed:0}
normalizer_validation=PASS
```

`video_detail_by_share_url_v3` 没有在该次真实验证中被调用，因此仍保持 `status=documented`。

## Pricing boundary

本次 live-validation 报告中的 `$0.006` 是按 `provider_default=$0.001` 计算的预算估算，不是最终账单，也不能用于把 App V3 endpoint 的 `unit_price_usd` 升级为 endpoint 精确报价。

因此：

- `video_detail_v3`
- `video_comments_v3`
- `user_profile_v3`
- `creator_posts_v3`
- `video_statistics_v3`

继续保持 `unit_price_usd=null`，并由 `EndpointRegistry.get_pricing()` 返回 `price_source=provider_default`、`is_endpoint_exact=false`。

`video_search` 保留此前已经登记的 explicit `$0.001` contract；v1.1.3 没有根据 live-validation 估算修改其价格来源。

## Planner / Harness compatibility

保持不变：

- Douyin Standard 典型 Planner 基线：`38 expected / 50 max`；
- 典型计划 max cost 约 `$0.050`，仍只是计划值；
- Douyin live-validation hard call ceiling = 6；
- live-validation plan-only 不联网、不读取 API Key；
- 真实 live-validation 仍要求 `--execute + --yes + --max-budget-usd`；
- `douyin-topic-radar-v1` legacy Web contract 不变；
- TikTok Video Intelligence / live-validation 行为不变；
- Douyin Video Intelligence V1 仍不包含 Ads Intelligence。

## TDD evidence

### RED 1 — Provider status

GitHub Actions run #83 / `32960204628`：

- 新 Phase 11 pricing-boundary test 已 PASS；
- 六个 capability 的 status 测试精确失败，因为 Registry 仍为 `documented/verified`，尚未 `live_verified`。

### GREEN 1 — Registry metadata

Registry 写入六个 `live_verified` 状态后，Phase 11 PASS。旧 Phase 9 测试随后暴露历史硬编码 `status=documented`，因此将 Phase 9 改为只守 method/path/request_location，并允许证据状态向前升级；Phase 11 负责精确状态。

GitHub Actions run #85 / `32960479041`：

```text
Python 3.10=PASS
Python 3.12=PASS
Python 3.13=PASS
Phase 11→Foundation=PASS
Legacy regression=PASS
Compileall=PASS
Release audit=PASS
Core environment=PASS
```

### RED 2 — Release version

GitHub Actions run #86 / `32960594398`：

- Provider metadata 与 pricing-boundary tests PASS；
- 唯一失败为 `VERSION=1.1.2`，而 Phase 11 要求 `1.1.3`。

随后 `VERSION` 升级为 `1.1.3`，并将 Phase 10 的历史 release guard 改为 `>=1.1.2`；Phase 11 精确锁定 `1.1.3`。

## Security / repository boundary

本 release **不提交**：

- TikHub API Key；
- 本地 `config.json`；
- 真实 raw Provider response；
- live-validation 本地输出目录。

CI 继续 offline，不注入 TikHub Key，也不产生付费请求。

## License

当前仓库仍未声明许可证；v1.1.3 不添加 MIT、Apache-2.0 或其他许可证。

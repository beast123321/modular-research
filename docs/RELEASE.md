# Modular Research v1.1.2 发布说明

## 状态

`v1.1.2` 是在 v1.1.1 Douyin bounded-planner 基线之上的 live-provider validation patch。目标不是扩大 ResearchRun，而是让 `scripts/live_validation.py` 能以正确的平台 contract 对 Douyin App V3 做受控、小额、可审计的真实 Provider 验证。

本次改动：

- `LiveValidationRunner.run()` 新增 platform-aware routing，默认仍保持 `platform=tiktok` 兼容；
- Douyin 模式从 `references/endpoints.json` 的 `platform=douyin` capability 读取真实 method/path/request location；
- Douyin 模式使用 `scripts/normalizers/douyin.py`，不再误用 TikTok normalizer；
- 新增 `build_douyin_probes()`；
- Douyin 初始 probe 只包含：
  - `video_detail_v3`：已知参考作品；
  - `video_search`：当前研究主题；
- 成功响应后动态扩展：
  - `video_statistics_v3`；
  - `video_comments_v3`；
  - `user_profile_v3`；
  - `creator_posts_v3`；
- 默认 Douyin live validation call ceiling 固定为 6；
- CLI 新增 `--platform douyin` 与 `--reference-aweme-id`；
- plan-only 不读取 API Key、不联网；
- 真实执行继续要求 `--execute + --yes + --max-budget-usd`；
- 新增 `scripts/test_phase10_live_validation.py` 并接入 Python 3.10 / 3.12 / 3.13 CI。

## Douyin 六接口验证链

推荐第一轮使用一个已本地解析的参考作品 ID：

```text
video_detail_v3
video_search
video_statistics_v3
video_comments_v3
user_profile_v3
creator_posts_v3
```

初始只发 detail + search。其余 capability 从真实响应中的 `aweme_id` / `sec_user_id` 动态得到，不要求用户手工提供 Creator ID。

`video_statistics_v3` 最多把两个已发现作品 ID 合并为一个 `aweme_ids=id1,id2` 请求；comments 保持 Provider contract 的 `count=20`。

## Plan-only

不配置 TikHub Key 也可以先检查将要调用的范围：

```bash
python scripts/live_validation.py \
  --platform douyin \
  --topic "职场高情商接话" \
  --reference-aweme-id "7667541271225140069"
```

默认应得到：

```text
execution_status=PLAN_ONLY
platform=douyin
initial_capabilities=video_detail_v3,video_search
call_ceiling=6
estimated_max_cost_usd=0.006
```

这里的 `$0.006` 使用当前 `provider_default=$0.001/successful request` 作为预算基线，不代表 Provider 最终账单或每个 endpoint 的精确单价。

## 真实验证

真实执行必须显式给出预算：

```bash
python scripts/live_validation.py \
  --platform douyin \
  --topic "职场高情商接话" \
  --reference-aweme-id "7667541271225140069" \
  --max-calls 6 \
  --max-budget-usd 0.01 \
  --execute \
  --yes
```

建议第一次真实验证把 hard budget 设为 `$0.01`，但 call ceiling 仍保持 6；预算不是扩大调用量的授权。

## 兼容性

必须继续保持：

- TikTok live-validation 默认行为兼容；
- TikTok Video Intelligence planner/executor 行为不退化；
- `douyin-topic-radar-v1` legacy Web contract 不退化；
- v1.1.1 的 `38 expected / 50 max` Standard Douyin Research Plan 回归继续通过；
- Douyin reference/profile/planner/executor/normalizer/CLI 回归继续通过；
- Legacy Douyin CLI regression 继续通过；
- Evidence/Analysis/Creative/Synthesis 语义不变。

Douyin Video Intelligence V1 仍**不包含 Ads Intelligence**。

## Evidence boundary

本 release candidate 的自动化验证只能证明：

- Douyin live harness 使用正确的平台 registry 与 normalizer；
- 六接口 fan-out、参数构造、6-call ceiling 与预算 gate 在离线 fixture 中成立；
- DNS/transport failure 与 Provider non-200 response 会被区分；
- Raw response 继续在落盘前脱敏；
- GitHub Actions 不注入 TikHub Key，也不产生付费请求。

在真实 TikHub 请求成功之前，仍不能声称 Douyin App V3 endpoint 已 `live_verified`。Registry 继续保持 `status=documented`；live validation 结果应作为后续 endpoint 状态升级的证据，而不是在代码合并时预先升级状态。

## TDD evidence

第一轮 RED：

- GitHub Actions run #69 / `32944513310`
- 失败原因精确为缺失 `build_douyin_probes` 与 Runner `platform` 参数。

第一轮 GREEN：

- run #70 / `32944682992`
- Python 3.10 / 3.12 / 3.13 全回归通过。

第二轮 RED：

- run #72 / `32944880560`
- Phase 10 probe/runner/CLI 三项 PASS；唯一失败是版本仍为 `1.1.1`。

第二轮 GREEN：

- run #73 / `32944939610`
- `VERSION=1.1.2` 后全回归通过。

## License

当前仓库仍未声明许可证；本次 patch 不添加 MIT、Apache-2.0 或其他许可证。

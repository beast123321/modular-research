---
name: modular-research
description: 独立、可移植、证据优先的模块化研究 Skill。把用户自然语言研究需求与可选参考内容转换为 ResearchRequest，自动选择 Profile、Provider Endpoint、Stage 与预算边界，再输出可追溯 Evidence、确定性分析和语义研究请求。
agent_created: true
---

# modular-research

`modular-research` 是一个独立通用 Research Skill，不绑定某个业务系统、Agent runtime 或固定研究主题。

核心执行链：

```text
User natural-language request
        ↓
Research Intake
        ↓
ResearchRequest
        ↓
Profile Resolver
        ↓
Stage Planner / Cost Gate
        ↓
Endpoint Registry / Provider
        ↓
Evidence Collection
        ↓
Normalization / Deterministic Analysis
        ↓
Host-agent Semantic Synthesis
        ↓
Evidence-backed Outputs
```

研究主题、平台、市场、参考内容、时间范围、视频过滤条件和目标必须来自**当前用户请求**。不得把某个业务场景硬编码进 Core/Profile。

---

## 1. Research Intake

标准入口是自然语言，不是 endpoint 表单。

Agent 应从当前请求构造 `ResearchRequest`。只有缺失信息会实质改变研究结论时才追问；能高置信度推断的内容直接推断，并把假设写进 Research Plan。

### 语义必需参数

- `topic`
- `platform`
- `research_goals`
- 对市场敏感的 Profile：`market`

### 可推断参数

- `language`
- `time_range`
- `content_scope`
- `depth`
- 内部 Profile / Provider

### 可选参数

- `reference_content`
- `audience`
- `seed_keywords`
- `competitors`
- `brands`
- `video_filters`
- `sample_size_overrides`
- `output_preferences`

### 不得要求用户提供内部实现参数

对普通用户，除非其主动做底层调试，否则不得要求用户提供：

- endpoint path；
- pagination cursor；
- Provider category/internal ID；
- Profile identifier；
- Stage 名称；
- 抖音 `modal_id` / `aweme_id`。

用户给出参考链接即可；Skill 负责尽可能本地解析内容 ID。

---

## 2. Canonical ResearchRequest

Schema：

```text
references/schemas/research-request.schema.json
```

Python 模型：

```text
scripts/research_request.py
```

核心示例：

```json
{
  "schema_version": "1.0",
  "topic": "<runtime topic>",
  "platform": "<runtime platform>",
  "market": null,
  "language": null,
  "research_goals": ["hooks", "voc"],
  "reference_content": [
    {
      "platform": "douyin",
      "url": "<runtime reference URL>",
      "content_id": null,
      "role": "style_reference"
    }
  ],
  "time_range": {},
  "content_scope": {},
  "seed_keywords": [],
  "video_filters": {},
  "depth": "standard",
  "outputs": ["evidence", "findings"]
}
```

允许的 `depth`：`quick | standard | deep`。

受控 `research_goals` 以 `scripts/research_request.py` 与 JSON Schema 为准。

---

## 3. Reference Content

参考内容是**研究种子和 Evidence source**，不是复制内容的指令。

抖音 reference resolver：

```text
scripts/reference_resolver.py
```

应优先零网络本地解析：

- `/video/<id>`
- `modal_id=<id>`
- `aweme_id=<id>`
- 用户已给出的 numeric `content_id`

本地解析成功：

```text
provider_fallback_required=false
```

无法本地解析的短链/分享链才允许规划 share-url Provider fallback。

**解析 URL 本身不得产生 API 费用。**

CLI convenience：

```bash
--reference-url "<url>"
```

可重复传入多个 reference。机器调用优先使用 canonical `--request request.json`。

`--request` 不得与 `--reference-url`、`--topic`、`--platform` 等 convenience 参数混用。

---

## 4. Profile Resolver

Profile 是可复用研究策略，不保存某次研究的固定业务参数。

Canonical：

```text
references/profiles/
```

当前 Profiles：

```text
douyin-topic-radar-v1
douyin-video-intelligence-v1
tiktok-video-intelligence-v1
```

Resolver：

```text
scripts/profile_resolver.py
```

路由原则：

- 轻量 Douyin trend-only 请求优先保留 `douyin-topic-radar-v1`；
- Douyin creative/VOC/creator/reference-content 请求使用 `douyin-video-intelligence-v1`；
- 提供 Douyin reference content 时，即使 goal 较轻，也可提升到 Video Intelligence；
- Douyin Video Intelligence V1 不支持 `ads_analysis` / `retention_analysis`；
- TikTok 请求保持 `tiktok-video-intelligence-v1` 行为。

Agent 不应要求普通用户手工选择 Profile。

---

## 5. Endpoint Registry

机器权威：

```text
references/endpoints.json
```

读取器：

```text
scripts/endpoint_registry.py
```

每个 endpoint 独立记录：

- provider / platform / capability；
- method / path / request location；
- required params / defaults / limits；
- price source；
- status / verified_at；
- docs_ref / notes。

不得假设一个 API 家族使用相同 HTTP method。

`status=documented` 只表示文档 contract 已登记，**不等于 live-verified**。

---

## 6. Stage-based Planning

通用顺序：

```text
READ REQUIREMENT
→ BUILD ResearchRequest
→ RESOLVE Profile
→ LOOK UP capabilities/endpoints
→ ESTIMATE COST
→ PLAN
→ COLLECT
→ SAVE RAW EVIDENCE
→ NORMALIZE
→ ANALYZE
→ SYNTHESIZE
→ REPORT
```

Planner：

```text
scripts/stage_planner.py
```

### Douyin Video Intelligence V1

典型阶段：

```text
REFERENCE_SEED (有 reference 时)
→ ORGANIC_DISCOVERY
→ CHEAP_RANKING
→ CREATOR_CONTEXT
→ VOC
→ VIDEO_UNDERSTANDING
→ PATTERN_MINING
→ FINDINGS
→ HYPOTHESES
→ BRIEFS
```

关键约束：

- App V3 与 legacy Web capability 使用独立 registry 名称，不能覆盖 Topic Radar 兼容 contract；
- Search first page 使用 Provider documented search contract；
- `fetch_video_statistics` 是显式 metrics enrichment，每次最多 2 个作品 ID；
- App V3 comments 保持 `count=20`；
- Creator Posts 遵守 Provider count 上限；
- V1 不创建 Douyin Ads stages。

### TikTok Video Intelligence V1

按研究目标启用 Demand、Organic Discovery、Creator Context、VOC、Ads/Retention、Video Understanding、Pattern/Synthesis 等 stages。

每个 API task 必须在 plan 中公开：

- capability / endpoint / HTTP method；
- query 或 JSON body；
- 静态 calls / 动态 fan-out；
- expected/max requests；
- unit price / price source；
- expected/max cost；
- dependencies。

---

## 7. 成本与执行闸门

默认 `plan-only`，不联网。

真实执行必须同时满足：

```text
API Key available
AND --yes
AND --max-budget-usd >= plan.max_cost_usd
```

价格来源：

```text
endpoint_explicit
provider_default
unknown
```

`provider_default` 是预算估算，不得冒充 endpoint 精确报价。

未经用户授权不得扩大付费范围；CI 不得注入 API Key，不得执行付费请求。

---

## 8. Evidence Contract

Raw Provider response 必须先脱敏再保存。

认知层级：

```text
Evidence
Observation
Insight
Hypothesis
```

- Provider response / deterministic metric = Evidence；
- deterministic description = Observation；
- interpretation backed by evidence = Insight；
- testable proposition = Hypothesis。

模型生成的 claim 不得保存为 Source Evidence。

所有 Derived 输出应保留 `raw_evidence_id` 或等价 evidence refs。

---

## 9. Normalization / Executor

Executor：

```text
scripts/research_executor_v2.py
```

Platform normalizers：

```text
scripts/normalizers/tiktok.py
scripts/normalizers/douyin.py
```

统一 Evidence bundle：

```text
videos
video_snapshots
creators
comments
ads
ad_timeseries
search_insights
discoveries
```

Douyin executor 支持：

- static calls；
- `per_creator`；
- `per_video`；
- `per_video_batch2`；
- comments bounded pagination；
- reference share-url fallback；
- platform-aware normalizer routing。

不能因为平台不同而改变 Evidence/Analysis 的通用语义。

---

## 10. Deterministic Analysis 与 Semantic Synthesis

当前已实现：

```text
Raw Evidence + SQLite Evidence Store
→ deterministic metrics
→ cohort ranking
→ VOC taxonomy
→ creative shortlist
→ media/keyframe/OCR/transcript evidence
→ CreativeAnalysis request
→ Pattern Lift
→ synthesis request
→ Insight / Creative Hypothesis / MediaBrief
```

Pattern Lift 只表示 association/correlation evidence，不是 causal proof。

Hypothesis 必须保持可测试；未经真实市场实验不得升级为 Business Truth。

语义推理保持 provider-neutral：Skill 不绑定固定 LLM Provider。

---

## 11. Agent Responsibilities

Agent 负责：

- 理解当前自然语言目标；
- 构造 ResearchRequest；
- 解析用户给出的 reference intent；
- 高置信度推断可推断参数；
- 只在必要时追问会改变研究结果的问题；
- 解释 Evidence；
- 生成 Observation / Insight / Hypothesis。

程序负责：

- Schema validation；
- Profile Resolution；
- Reference local parsing；
- Endpoint Lookup；
- Cost calculation；
- Network requests；
- Redaction；
- Deterministic extraction / metrics；
- Run state / SQLite persistence。

---

## 12. CLI

Canonical machine request：

```bash
python scripts/run_research.py \
  --request request.json \
  --plan-only
```

Reference convenience：

```bash
python scripts/run_research.py \
  --topic "<runtime topic>" \
  --platform douyin \
  --research-goal hooks \
  --research-goal low_follower_breakouts \
  --research-goal creator_analysis \
  --research-goal voc \
  --reference-url "<douyin reference URL>" \
  --depth standard \
  --plan-only
```

真实执行再显式加入：

```text
--yes
--max-budget-usd <hard ceiling>
```

媒体下载另外需要显式：

```text
--download-media
--media-limit <n>
```

---

## 13. Legacy Compatibility

原有 Douyin legacy 参数暂时保留，包括：

```text
--goal
--keywords
--only-free
--with-search
--billboard
--billboard-type
--video-ids
--demo
```

Legacy 是兼容层，不是新架构的默认业务逻辑。

新 Douyin Video Intelligence 必须保持 Topic Radar 与 TikTok 回归测试绿色。

---

## 14. 凭证与安全

推荐：

```text
TIKHUB_API_KEY
```

也可使用系统 Keychain；本地 `config.json` 仅作兼容 fallback，必须保持 gitignored。

不要要求用户把 API Key 粘贴到聊天中。

Raw/log 落盘前必须脱敏。视频下载器必须拒绝 localhost、私网、link-local、reserved IP 和 `file://`。

只采集授权范围内公开数据，不收集密码、Cookie 或 session token。

---

## 15. Live Provider Validation

独立入口：

```text
scripts/live_validation.py
```

默认是 **plan-only**：不联网，也不读取 API Key。

### Douyin

当需要在完整 ResearchRun 前验证 Douyin App V3 Provider contract 时，Agent 应先从用户参考链接通过 `reference_resolver.py` 本地解析 `aweme_id`；仍然不得要求普通用户手工提供 `aweme_id`。

预览：

```bash
python scripts/live_validation.py \
  --platform douyin \
  --topic "<runtime topic>" \
  --reference-aweme-id "<locally resolved aweme_id>"
```

Douyin 默认验证边界：

```text
call_ceiling=6
estimated_max_cost_usd=0.006
```

初始 probes：

```text
video_detail_v3
video_search
```

成功取得真实 detail/search response 后，最多在同一个 6-call ceiling 内动态扩展：

```text
video_statistics_v3
video_comments_v3
user_profile_v3
creator_posts_v3
```

真实验证必须同时提供：

```text
--execute
--yes
--max-budget-usd <hard ceiling>
```

首次 Douyin 验证建议：

```text
--max-calls 6
--max-budget-usd 0.01
```

`--max-budget-usd` 是金额闸门，不代表允许增加调用次数；`--max-calls` 仍是独立硬上限。

### TikTok

TikTok 兼容入口：

```bash
python scripts/live_validation.py \
  --platform tiktok \
  --topic "<runtime topic>" \
  --market US \
  --max-calls 12
```

真实 TikTok 验证同样必须显式加入 `--execute --yes --max-budget-usd <hard ceiling>`。

DNS/transport failure 必须报告为 environment/transport failure，不得误报为 Provider contract failure。

只有 `calls_attempted > 0` 且取得真实 Provider response，才可把对应 endpoint 视为已取得 live-validation 证据；失败或未调用的 endpoint 不得升级状态。

当前 Douyin App V3 contract 已完成离线 fixture/CI 验证，但在真实 TikHub Provider 请求成功之前，Registry 中相关 endpoint 必须继续保持 `status=documented`，不得预先标记为 `live_verified`。

---

## 16. CI / Completion Gate

GitHub Actions 必须在 Python：

```text
3.10
3.12
3.13
```

运行 Phase 10 → Phase 9 → Phase 8 → ... → Foundation 与 Legacy regression，并执行：

```text
compileall
release_check
core environment check
```

CI 必须 offline，不提供 TikHub Key。

任何“完成/可发布”结论都必须基于最新 branch/PR CI，而不是只依据本地测试。

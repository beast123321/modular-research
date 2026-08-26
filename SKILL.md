---
name: modular-research
description: 独立、可移植、证据优先的模块化研究 Skill。把用户在当前窗口中的自然语言研究需求转换为 ResearchRequest，自动选择 Research Profile 与 Provider Endpoint，先规划/估价/校验，再采集公开数据并输出可追溯研究结果。当前兼容既有 Douyin 调研能力，并逐步增加 TikTok Video Intelligence 等可插拔 Profile。
agent_created: true
---

# modular-research

`modular-research` 是一个**独立通用 Research Skill**。它不属于某个业务系统，也不依赖 HCO、Hermes、Shopify 或特定 Agent runtime。

核心原则：

```text
用户当前窗口的自然语言需求
        ↓
Research Intake
        ↓
ResearchRequest
        ↓
Profile Resolver
        ↓
Research Planner
        ↓
Endpoint Registry / Provider
        ↓
Evidence Collection
        ↓
Normalization / Analysis
        ↓
Evidence-backed Outputs
```

`SKILL.md` 只定义研究方法、参数契约和执行边界。**研究什么、哪个市场、什么平台、什么时间范围、什么视频/账号过滤条件，都必须来自当前用户请求，而不是写死在 Skill 中。**

---

## 1. Research Intake

标准入口是用户自然语言，而不是技术表单。

Agent 首先从当前请求中提取并构造 `ResearchRequest`。只有缺失信息会实质改变研究结果时才追问；可高置信度推断的参数应直接推断，并在 Research Plan 中公开假设。

### 语义必需参数

- `topic`：研究对象/主题；
- `platform`：目标平台；
- `research_goals`：研究要回答的问题；
- 对市场敏感的 Profile：`market`。

### 可推断参数

- `language`
- `time_range`
- `content_scope`
- `depth`
- `analysis_modules`
- 内部 Research Profile / Provider

### 可选参数

- `audience`
- `seed_keywords`
- `competitors`
- `brands`
- `video_filters`
- `sample_size_overrides`
- `output_preferences`

### 不得要求用户提供

除非用户主动进行底层调试，否则不得要求用户提供：

- Endpoint path；
- pagination cursor；
- Provider 内部 category ID；
- 内部 Profile identifier；
- 内部 stage 名称。

用户描述目标即可，Skill 负责把意图转换成实现参数。

---

## 2. Canonical ResearchRequest

机器契约：

```text
references/schemas/research-request.schema.json
```

Python 模型：

```text
scripts/research_request.py
```

核心字段：

```json
{
  "schema_version": "1.0",
  "topic": "<runtime topic>",
  "platform": "<runtime platform>",
  "market": "<runtime market or null>",
  "language": "<runtime language or null>",
  "research_goals": ["<controlled goal>"],
  "time_range": {},
  "content_scope": {},
  "audience": null,
  "seed_keywords": [],
  "competitors": [],
  "brands": [],
  "video_filters": {},
  "depth": "standard",
  "outputs": ["evidence", "findings"]
}
```

允许的 `depth`：

```text
quick
standard
deep
```

受控 `research_goals` 见 `scripts/research_request.py` 和 JSON Schema。

---

## 3. Profile Resolver

Profile 是**可复用研究策略**，不是某一次研究的业务参数。

Canonical 目录：

```text
references/profiles/
```

当前初始 Profile：

```text
douyin-topic-radar-v1
tiktok-video-intelligence-v1
```

Agent 不应要求普通用户选择 Profile。`scripts/profile_resolver.py` 根据 `platform + research_goals` 自动选择。

Profile 可以声明：

- 支持哪些 goals；
- 需要哪些 capabilities；
- 默认 content scope；
- depth 对应的默认样本规模；
- stages；
- analysis modules；
- output contracts。

Profile 不得包含固定 topic、固定 market、用户身份、API Key 或特定业务系统 import。

---

## 4. Endpoint Registry

唯一机器权威：

```text
references/endpoints.json
```

读取器：

```text
scripts/endpoint_registry.py
```

`references/routing-table.md` 只用于人类阅读，不再是机器配置源。

每个 Endpoint 独立记录：

- `provider`
- `platform`
- `capability`
- `method`
- `path`
- `free_credit`
- `unit_price_usd`
- `status`
- `verified_at`
- `docs_ref` / `notes`

**不得假设某一 API 家族全部使用同一个 HTTP method。** 每个 Endpoint 必须独立登记和核验。

---

## 5. Stage-based Research Planning

研究顺序必须遵守：

```text
READ REQUIREMENT
→ BUILD ResearchRequest
→ RESOLVE Profile
→ LOOK UP capabilities/endpoints
→ ESTIMATE COST
→ VALIDATE SMALL SAMPLE
→ COLLECT
→ SAVE RAW EVIDENCE
→ NORMALIZE
→ ANALYZE
→ REPORT
```

### Phase 2 Stage Plan

TikTok Video Intelligence 由 `scripts/stage_planner.py` 把当前 `ResearchRequest` 转换为按依赖排序的阶段：

```text
DEMAND (按目标启用)
→ ORGANIC_DISCOVERY
→ CHEAP_RANKING (local)
→ CREATOR_CONTEXT (按目标启用)
→ ADS_DISCOVERY (按目标启用)
→ VOC (按目标启用)
→ CREATIVE_ANALYSIS (Ads/Retention 深挖)
→ PATTERN_MINING / FINDINGS / HYPOTHESES / BRIEFS (local, 后续分析阶段)
```

每个 API task 都必须在计划中公开：

- capability / endpoint / HTTP method；
- 参数进入 query 还是 JSON body；
- 静态调用组合或动态 fan-out 模式；
- expected/max requests；
- unit price 与 price source；
- expected/max cost；
- 上游依赖。

`quick / standard / deep` 控制关键词数、候选量、creator/comment/ad 深挖上限，不把具体 topic/market 写进 Profile。

### 成本闸门

V2 默认只规划，不联网。真实执行必须同时满足：

```text
API Key 可用
AND --yes
AND --max-budget-usd >= plan.max_cost_usd
```

价格来源必须区分：

```text
endpoint_explicit   # endpoint 明确价格
provider_default    # Provider 通用基准估算，不冒充精确报价
unknown             # 当前无法可靠估价
```

- 未经用户授权不得擅自扩大付费范围；
- 动态阶段实际调用数可低于计划上限；
- 单个 capability 首个/后续请求失败后停止该 capability 后续 fan-out，Phase 2 不做无界自动重试；
- 真实采集前由 Endpoint Registry 固定 method、request location、required params 和 limits。

---

## 6. Evidence 原则

原始 Provider 响应必须先脱敏再保存。结论必须能回指原始证据。

认知层级严格区分：

```text
Evidence
Observation
Insight
Hypothesis
```

模型推断不能保存为 Source Evidence。

例如“某模式与高表现样本相关”可以是 Observation/Insight；“使用该模式一定提升转化”在没有实验结果时只能是 Hypothesis。

---

## 7. Agent 与程序的职责边界

### Agent 负责

- 理解自然语言研究目标；
- 构造 `ResearchRequest`；
- 高置信度推断可推断参数；
- 必要时只追问一个会实质改变研究结果的问题；
- 解释 Evidence；
- 形成 Observation / Insight / Hypothesis。

### 程序负责

- Schema 校验；
- Profile Resolution；
- Endpoint Lookup；
- 成本计算；
- 请求发送；
- 脱敏；
- 确定性字段抽取；
- Run State；
- 可复现指标计算。

涉及凭证、费用和不可逆操作时，以代码护栏和明确授权为准。

---

## 8. V2 Phase 2 CLI

推荐用 JSON 请求：

```bash
python scripts/run_research.py \
  --request request.json \
  --plan-only
```

也支持便捷参数：

```bash
python scripts/run_research.py \
  --topic "<topic>" \
  --platform <platform> \
  --market <market> \
  --research-goal <goal> \
  --research-goal <goal> \
  --depth standard \
  --plan-only
```

Phase 1 的 V2 CLI 只完成 Intake + Profile Resolution 计划，不会伪装成已实现完整 TikTok 采集。后续阶段逐步接入 stage-based Research Planner 与 Video Intelligence execution。

---

## 9. Legacy Compatibility

现有 Douyin 流程暂时保留：

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

旧参数继续走原有 pipeline；V2 Foundation 不应破坏已有离线验收。

Legacy 能力是兼容层，不是新架构的业务默认值。

---

## 10. 凭证与安全

推荐 API Key 通过：

```text
TIKHUB_API_KEY
```

或系统 Keychain 读取。

本地 `config.json` 仅作为兼容 fallback，必须被 `.gitignore` 排除。不要要求用户把 API Key 粘贴到聊天中。

所有 raw/log 在落盘前必须经过：

```text
redact_payload
redact_url
```

只采集授权范围内的公开数据，不收集密码、Cookie 或会话令牌。

---

## 11. 当前 V2 Phase 2 边界

已建立：

- `ResearchRequest` / Intake Contract；
- Profile Loader / Resolver；
- Endpoint Registry（含 method / request location / pricing provenance）；
- Stage-based TikTok Research Planner；
- TikTok Organic Search / Creator Context / Metrics / Comments 执行路径；
- TikTok Ads Search / Spotlight / Detail / Percentile / Keyframe / Interactive 执行路径；
- 静态调用 → 上游 ID 提取 → 动态 fan-out；
- plan-only 零网络预览；
- `--yes + --max-budget-usd` 硬预算门；
- raw response 脱敏落盘；
- Legacy Douyin 兼容。

尚未实现，不得提前宣称完成：

- TikTok 全部 Endpoint 或 Shop 全链；
- Search Insight query 的 trend/videos 二级 enrichment；
- Provider `calculate_price` 的实时端点报价调用（当前 Provider default 仅为估算）；
- Normalized SQLite Evidence Store；
- CHEAP_RANKING 的新 V2 指标实现；
- 评论 VOC 分类；
- Video ASR / OCR / Vision Understanding；
- Pattern Lift / Findings / Creative Hypothesis / MediaBrief 实际算法。

Phase 2 的 `PATTERN_MINING / FINDINGS / HYPOTHESES / BRIEFS` 目前只作为计划中的 local stage 边界存在。

---

## 12. Phase 3–6 当前能力

当前 V2 已进一步实现：

```text
ResearchRequest
→ Stage Planner / Budget Gate
→ TikHub Evidence Collection
→ Raw Evidence + SQLite Evidence Store
→ Deterministic Metrics / Cohort Ranking / VOC
→ Transparent Creative Shortlist
→ Media / Keyframe / OCR / Transcript Evidence
→ Host-agent CreativeAnalysis Contract
→ Pattern Lift
→ Host-agent Synthesis Contract
→ Insight / Creative Hypothesis / MediaBrief
```

### Pattern Mining

`scripts/analysis/patterns.py` 仅计算可审计的关联统计，不声明因果。默认比较多个独立表现维度的 top cohort 与 baseline，例如：

- `engagement_percentile`
- `share_rate_percentile`
- `follower_leverage_percentile`
- `views_percentile`

对 `hook_type / format / selling_angle / proof_type` 计算：

- top/baseline support；
- top/baseline share；
- lift；
- supporting creator 数；
- organic support；
- ad cross-source support；
- evidence refs。

证据样本不足时返回空结果，不制造 Pattern。

### Insight / Hypothesis / MediaBrief

语义推理继续保持 provider-neutral：Skill 不内置固定 LLM Provider。

程序生成：

```text
reports/pattern_report.json
reports/synthesis_request.json
```

宿主 Agent 根据 `synthesis_request.json` 生成符合契约的 response，再通过：

```bash
python scripts/synthesis_cli.py import-response \
  --run-dir <run_dir> \
  --run-id <run_id> \
  --response <response.json>
```

导入 SQLite：

```text
insights
creative_hypotheses
media_briefs
```

强制边界：

- Pattern Lift = association/correlation evidence，不是 causal proof；
- Insight 必须带 `evidence_refs + confidence + analyzer provenance`；
- Hypothesis 必须保持可测试状态，默认 `PROPOSED`；
- MediaBrief 必须绑定一个 hypothesis；
- 未经真实市场测试，不得升级为 `Business Truth` 或 `Decision`。

### 当前尚未完成

- TikHub 生产环境全 Endpoint live sample validation；
- TikHub Shop profile；
- 内置 ASR provider adapter；
- 跨 ResearchRun 历史 Pattern 趋势；
- 正式发布安装文档与 GitHub release automation。


---

## 13. Phase 7 Live Provider Validation

Phase 7 增加独立的 provider contract 验证入口：

```bash
python scripts/live_validation.py \
  --topic "<runtime topic>" \
  --market US \
  --max-calls 12
```

默认仅输出计划，不联网。真实验证必须同时提供：

```text
--execute
--yes
--max-budget-usd <hard ceiling>
```

标准 probe 使用 bounded one-ID fan-out：先验证 video search / search insights / ads / top contents 根端点，再从真实返回中最多选一个 video / creator / material / insight / top-content ID 验证依赖端点。`max_calls` 是硬调用上限，预算门按调用上限而不是初始 probe 数计算。

输出 `live-validation.json` 只保存 response shape、provider code、method/location、normalizer counts 与错误分类；原始响应单独脱敏落盘。DNS/transport failure 必须标记为 environment/transport，不得误报为 TikHub provider failure。

当前发布环境若无法访问公网，只能验证工具链与环境阻塞行为；只有 `calls_attempted > 0` 且取得真实 Provider response 才可把某 Endpoint 标记为 live-validated。

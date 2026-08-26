# modular-research

> Independent, portable, evidence-first research skill for agents.

`modular-research` 是一个独立、可移植的研究 Skill。用户只需要描述**研究什么、在哪个平台/市场、想解决什么问题，以及可选的参考内容链接**；Skill 会构造 canonical `ResearchRequest`，自动选择 Research Profile、Provider Endpoint、调用顺序和预算边界，再输出可追溯 Evidence、确定性分析和语义研究请求。

当前 Profiles：

- `douyin-topic-radar-v1`：轻量抖音趋势/话题研究，保留旧能力兼容。
- `douyin-video-intelligence-v1`：抖音参考视频、自然内容发现、Creator、播放指标 enrichment、VOC、Video Understanding、Pattern/Hypothesis/Brief。
- `tiktok-video-intelligence-v1`：TikTok 搜索需求、自然内容、Creator、Ads、VOC、视频创意理解、Pattern/Hypothesis/Brief。

## 设计边界

- **不写死研究主题或市场。** `topic`、`market`、`platform`、参考内容、视频条件和 `research_goals` 都来自当前用户请求。
- **Evidence 与推断分层。** Raw Evidence、Observation、Insight、Hypothesis 分开保存。
- **默认不花钱。** 先 plan / cost estimate；真实网络执行必须显式通过预算门。
- **不绑定特定 Agent 或模型。** 视频/语义推理通过标准 request/response contract 交给宿主 Agent 或可插拔 multimodal backend。
- **TikHub 是当前 Provider，不是 Skill 本身。** Provider / Profile / Analysis 彼此分离。
- **参考视频是研究种子，不是复制指令。** Skill 用它扩展同赛道样本、结构和受众证据，不要求复刻原内容。

## 发布状态

当前版本：`1.1.3`。

`1.1.3` 是 Douyin Provider Verification Metadata release。基于 2026-08-26 的一次受控真实 TikHub 验证，以下六个 capability 已取得真实 Provider response，验证结果为 `6 attempted / 6 succeeded / 0 failed`，且 normalizer 均通过，因此 Registry 状态升级为 `live_verified`：

```text
video_detail_v3
video_search
video_comments_v3
user_profile_v3
creator_posts_v3
video_statistics_v3
```

`video_detail_by_share_url_v3` 未包含在该次真实验证中，继续保持 `documented`。验证计划的 `$0.006` 是 provider-default 预算估算，不是 endpoint 精确价格或最终账单。v1.1.1 引入的 bounded Standard sampling 保持不变：典型基线 `38 expected / 50 max`。

## 安装

```bash
git clone https://github.com/beast123321/modular-research.git
cd modular-research
python -m venv .venv
```

Linux/macOS：

```bash
source .venv/bin/activate
```

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
```

安装依赖：

```bash
pip install -r requirements.txt
```

环境检查：

```bash
python scripts/check_environment.py --mode core
python scripts/check_environment.py --mode video
python scripts/check_environment.py --mode full
```

需要 Python `>=3.10`。`full` 模式 OCR 还需要系统 `tesseract` binary；缺失时会明确标记 unavailable，不伪造 OCR 文本。

如果 Agent 支持 Skills，把整个仓库目录安装到 Agent 的 Skill 目录，并保证 `SKILL.md` 位于 Skill 根目录即可。

## TikHub API Key

推荐使用环境变量，不要把 Key 写进仓库或聊天：

Linux/macOS：

```bash
export TIKHUB_API_KEY='YOUR_KEY'
```

Windows PowerShell：

```powershell
$env:TIKHUB_API_KEY='YOUR_KEY'
```

也可以把 `config.example.json` 复制为本地 `config.json`。该文件已被 `.gitignore` 排除。

默认 API base：

```text
中国大陆：https://api.tikhub.dev
海外：https://api.tikhub.io
```

## Agent 使用方式

标准入口是**自然语言研究目标**，不是 endpoint 表单。Agent 应自行把用户意图转换成 `ResearchRequest`。

例如用户说：

> 参考这条抖音视频，研究同类“职场沟通/高情商接话”内容，看看有哪些高表现 Hook、低粉爆款、Creator 模式和评论需求。

Agent 应构造类似：

```json
{
  "topic": "职场沟通与高情商接话",
  "platform": "douyin",
  "research_goals": [
    "hooks",
    "low_follower_breakouts",
    "creator_analysis",
    "voc",
    "creative_patterns"
  ],
  "reference_content": [
    {
      "platform": "douyin",
      "url": "<用户提供的抖音链接>",
      "role": "style_reference"
    }
  ],
  "depth": "standard"
}
```

Agent **不要要求普通用户提供**：

- `modal_id` / `aweme_id`；
- endpoint path；
- pagination cursor；
- Profile ID；
- Stage 名称。

对于包含 `modal_id=<id>`、`/video/<id>` 或明确 `aweme_id` 的抖音 URL，Skill 会本地解析 ID，**解析本身不产生 API 请求**。只有无法本地解析的短链/分享链才计划 Provider share-url fallback。

## CLI：参考抖音视频

最简单的 plan-only 示例：

```bash
python scripts/run_research.py \
  --topic "职场沟通与高情商接话" \
  --platform douyin \
  --research-goal hooks \
  --research-goal low_follower_breakouts \
  --research-goal creator_analysis \
  --research-goal voc \
  --reference-url "https://www.douyin.com/jingxuan/search/x?modal_id=7667541271225140069&type=general" \
  --depth standard \
  --plan-only
```

`--reference-url` 可以重复传入多个参考视频。它会被转换为 canonical `reference_content`。

注意：`--request request.json` 是机器调用的 canonical 入口，不能与 `--reference-url`、`--topic`、`--platform` 等 convenience 参数混用。

## CLI：TikTok 示例

```bash
python scripts/run_research.py \
  --topic "standing desk" \
  --platform tiktok \
  --market US \
  --research-goal hooks \
  --research-goal creative_patterns \
  --research-goal voc \
  --depth standard \
  --plan-only
```

`--plan-only` 会显示 Stage、Endpoint、预计请求量和预算，不发送网络请求。

真正执行必须显式给出：

```text
--yes
--max-budget-usd <硬预算上限>
```

如果预算上限低于 `plan.max_cost_usd`，执行器拒绝启动。

## Douyin Video Intelligence 流程

典型阶段：

```text
REFERENCE_SEED (存在参考内容时)
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

关键实现边界：

- 直接参考 ID 优先本地解析，再调用 App V3 detail；
- 关键词发现使用 Douyin search endpoint；
- `fetch_video_statistics` 用于补充播放表现，最多 **2 个作品 ID / Provider call**；
- App V3 评论请求保持 `count=20`；
- Creator Posts 保持 provider documented count 上限；
- Douyin Video Intelligence V1 **不包含 Ads Intelligence**；`ads_analysis` / `retention_analysis` 不会路由到该 Profile；
- `video_detail_v3`、`video_search`、`video_comments_v3`、`user_profile_v3`、`creator_posts_v3`、`video_statistics_v3` 已有真实 Provider + normalizer 验证证据；短链 share-url fallback 仍只是 documented contract。

### 有界采样与成本

`v1.1.1` 将“候选池”和“付费深挖样本”分开。Standard 默认值：

```text
candidate_limit=200
statistics_video_limit=20
creator_limit=6
comment_video_limit=6
comment_pages=3
deep_analysis_limit=8
```

对**一个主题 + 一个可本地解析参考视频**的典型 Standard 请求，当前回归基线为：

```text
EXPECTED_REQUESTS=38
MAX_REQUESTS=50
MAX_COST_USD<=0.050
```

这是当前混合定价下的计划基线，不是 Provider 最终账单。增加 seed keywords 会增加搜索请求，因此每次真实执行仍应以当次 Plan 为准。

Canonical request 可以覆盖网络采样：

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

`statistics_video_limit` 自动受 `candidate_limit` 封顶。例如 `candidate_limit=9`、`statistics_video_limit=20` 时，只会计划 9 条视频的 statistics enrichment，即最多 5 个 batch-of-two 请求。

## ResearchRequest

机器契约：`references/schemas/research-request.schema.json`。

示例：

```json
{
  "topic": "standing desk",
  "platform": "tiktok",
  "market": "US",
  "language": "en",
  "research_goals": ["hooks", "creative_patterns", "voc"],
  "time_range": {"days": 90},
  "video_filters": {
    "duration": {"max": 30},
    "creator_size": {"max_followers": 100000},
    "minimum_views": 10000
  },
  "depth": "standard"
}
```

然后：

```bash
python scripts/run_research.py --request request.json --plan-only
```

当前受控 `research_goals`：

```text
trend_discovery
content_opportunities
low_follower_breakouts
creative_patterns
hooks
selling_angles
formats
creator_analysis
ads_analysis
retention_analysis
voc
purchase_objections
competitor_analysis
product_validation
```

## Quick / Standard / Deep

- `quick`：快速验证，较小样本和较低 fan-out。
- `standard`：默认研究深度；Douyin 使用 bounded paid enrichment，不再把整个候选池全部深挖。
- `deep`：更多 statistics、Creator/VOC enrichment 与深挖，成本更高。

精确请求上限由 Stage Planner 根据当前 `ResearchRequest` 动态生成，不写死在 `SKILL.md`。如需精确控制 Douyin 网络样本，使用 `sample_size_overrides`。

## Video Creative Understanding

媒体下载默认关闭。真实下载 shortlist 视频必须显式：

```bash
--download-media --media-limit 20
```

Skill 可提取视频探测信息、关键帧、OCR/Transcript Evidence，并生成标准 `CreativeAnalysisRequest`。宿主 Agent 返回结果必须通过 Schema、Taxonomy、Timeline、Confidence 校验后才能进入 SQLite。

## Bounded live validation

TikHub live validation 是独立的小额 Provider Contract 验证，不是完整 ResearchRun。默认只输出计划，不联网，也不要求 API Key。

### Douyin：先预览

```bash
python scripts/live_validation.py \
  --platform douyin \
  --topic "职场高情商接话" \
  --reference-aweme-id "7667541271225140069"
```

默认：

```text
call_ceiling=6
estimated_max_cost_usd=0.006
initial_capabilities=video_detail_v3,video_search
```

真实 Douyin contract validation：

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

成功的 detail/search 响应会在 6-call ceiling 内动态扩展 `video_statistics_v3`、`video_comments_v3`、`user_profile_v3`、`creator_posts_v3`。`$0.006` 是 provider-default 预算估算，不是最终账单。

2026-08-26 的受控验收已使用该边界取得 `6/6` 成功真实响应并通过 normalizer。该事实只支持本次实际调用到的六个 capability；未调用的 endpoint 不得据此升级。

### TikTok

```bash
python scripts/live_validation.py \
  --platform tiktok \
  --topic "standing desk" \
  --market US \
  --max-calls 12
```

真实验证同样必须显式加入：

```text
--execute
--yes
--max-budget-usd <hard ceiling>
```

DNS/transport failure 必须报告为 environment/transport failure；只有实际取得 Provider response 才能把 endpoint 标记为 live-validated。

## 输出

```text
runs/<run_id>/
├── plan.json
├── execution.json
├── raw/
├── run.sqlite
└── reports/
    ├── metrics.json
    ├── rankings.json
    ├── voc.json
    ├── findings.json
    ├── pattern_report.json
    └── synthesis_request.json
```

Raw Evidence 落盘前脱敏；Normalized/Derived 数据通过 `raw_evidence_id` 回指证据。

## 测试

GitHub Actions 在 Python `3.10 / 3.12 / 3.13` 上运行离线测试，不注入 TikHub Key，也不执行付费请求。

```bash
PYTHONPATH=scripts python -m unittest scripts/test_phase11_provider_verification.py
PYTHONPATH=scripts python -m unittest scripts/test_phase10_live_validation.py
PYTHONPATH=scripts python -m unittest scripts/test_phase9_budget.py
PYTHONPATH=scripts python -m unittest scripts/test_phase9_cli.py
PYTHONPATH=scripts python -m unittest scripts/test_phase9.py
PYTHONPATH=scripts python -m unittest scripts/test_phase8.py
PYTHONPATH=scripts python -m unittest scripts/test_phase7.py
PYTHONPATH=scripts python -m unittest scripts/test_phase6.py
PYTHONPATH=scripts python -m unittest scripts/test_phase5.py
PYTHONPATH=scripts python -m unittest scripts/test_phase4.py
PYTHONPATH=scripts python -m unittest scripts/test_phase3.py
PYTHONPATH=scripts python -m unittest scripts/test_phase2.py
PYTHONPATH=scripts python -m unittest scripts/test_foundation.py
python scripts/test_skill.py
python -m compileall -q scripts
python scripts/release_check.py --root .
```

## 安全

仓库默认忽略：

- `config.json` / `.env*`；
- `runs/` / `raw/` / `normalized/` / `media/` / `reports/`；
- SQLite 运行数据库；
- Python cache；
- live validation 输出。

视频下载器拒绝 localhost、私网、link-local、reserved IP 和 `file://`，降低 SSRF/本地文件访问风险。

## License

当前仓库**尚未声明开源许可证**。公开可见不等于自动授予复制、修改和再分发许可。仓库所有者可在后续明确选择 MIT、Apache-2.0 或其他许可证。

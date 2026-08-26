# modular-research

> Independent, portable, evidence-first research skill for agents.

`modular-research` 是一个独立、可移植的研究 Skill：用户在**当前窗口**描述要研究什么、在哪个平台/市场、想解决什么问题，Skill 将其转换为 `ResearchRequest`，再自动选择 Research Profile、Provider Endpoint、调用顺序和预算边界，最后输出可追溯 Evidence、确定性分析和创意研究产物。

当前内置 Profile：

- Douyin Topic Radar V1（兼容原有抖音研究能力）
- TikTok Video Intelligence V1（搜索需求、自然内容、Creator、Ads、VOC、视频创意理解、Pattern/Hypothesis/MediaBrief）

## 设计边界

- **不写死研究主题或市场。** `topic`、`market`、`platform`、视频条件和 `research_goals` 来自当前用户请求。
- **Evidence 与推断分层。** Raw Evidence、Observation、Insight、Hypothesis 分开保存。
- **默认不花钱。** 先 plan / cost estimate；网络执行必须显式确认预算。
- **不绑定特定 Agent 或模型。** 视频/语义推理通过标准 request/response contract 交给宿主 Agent 或可插拔 multimodal backend。
- **TikHub 是当前 Provider，不是 Skill 本身。** Provider / Profile / Analysis 彼此分离。

## 当前发布状态

版本：`1.0.0`

本仓库已通过完整离线回归测试；TikHub 提供 `scripts/live_validation.py` 做小额真实 Provider Contract 验证。由于开发环境曾受 DNS 限制，**不要把离线测试通过理解为所有 TikHub endpoint 已在你的网络环境 live 验证**。生产使用前建议执行下方 bounded live validation。

## 安装

### 1. 克隆

```bash
git clone https://github.com/beast123321/modular-research.git
cd modular-research
```

如果你的 Agent 支持 Skills，把整个仓库目录复制/克隆到该 Agent 的 Skill 目录，确保 `SKILL.md` 位于 Skill 根目录即可。不同 Agent 的 Skill 安装目录不同，本仓库本身不依赖某个特定 runtime。

### 2. Python 环境

需要 Python `>=3.10`。

```bash
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

安装完整依赖：

```bash
pip install -r requirements.txt
```

环境检查：

```bash
python scripts/check_environment.py --mode core
python scripts/check_environment.py --mode video
python scripts/check_environment.py --mode full
```

`full` 模式的 OCR 还需要系统安装 `tesseract` binary；没有 Tesseract 时，Skill 会把 OCR 标成 unavailable，而不是伪造文本。

## TikHub API Key

推荐使用环境变量，不要把 Key 写进仓库：

Linux/macOS：

```bash
export TIKHUB_API_KEY='YOUR_KEY'
```

Windows PowerShell：

```powershell
$env:TIKHUB_API_KEY='YOUR_KEY'
```

也可以把 `config.example.json` 复制为本地 `config.json`。`config.json` 已被 `.gitignore` 排除。

中国大陆默认 API base 可使用：

```text
https://api.tikhub.dev
```

海外可通过 CLI 指定：

```text
https://api.tikhub.io
```

## 第一次使用：先看计划，不发请求

例如研究 TikTok 美国市场的 standing desk 视频，关注 Hook、创意模式和 VOC：

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
--max-budget-usd <你的硬预算上限>
```

例如：

```bash
python scripts/run_research.py \
  --topic "standing desk" \
  --platform tiktok \
  --market US \
  --research-goal hooks \
  --research-goal voc \
  --depth quick \
  --yes \
  --max-budget-usd 0.10
```

如果预算上限低于计划的最大成本，执行器会拒绝启动。

## ResearchRequest

也可以直接提交机器可读的 `ResearchRequest`：

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

当前受控 `research_goals` 包括：

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

- `quick`：快速验证，较小样本和较低 API fan-out。
- `standard`：默认业务研究深度。
- `deep`：更多 query / cohort / enrichment，成本和运行时间更高。

精确请求上限由 Stage Planner 根据当前 ResearchRequest 生成，不在 `SKILL.md` 里写死。

## Video Creative Understanding

媒体下载默认关闭。需要真实下载 shortlist 视频时必须显式：

```bash
--download-media --media-limit 20
```

Skill 可以提取视频探测信息、关键帧和 OCR/转录 Evidence，并生成标准 `CreativeAnalysisRequest`。宿主 Agent 或 multimodal backend 返回的结果必须通过 Schema/Taxonomy/Timeline/Confidence 校验后才能进入 SQLite。

## Bounded TikHub live validation

正式使用前建议在**可以访问公网**的机器上跑小额验证：

先预览：

```bash
python scripts/live_validation.py \
  --topic "standing desk" \
  --market US \
  --max-calls 12 \
  --max-budget-usd 0.012
```

确认后执行：

```bash
python scripts/live_validation.py \
  --topic "standing desk" \
  --market US \
  --max-calls 12 \
  --max-budget-usd 0.012 \
  --execute \
  --yes
```

这不是完整 ResearchRun，只用于验证真实 TikHub request/response contract。预算示例基于 Provider 默认估算，实际计费以 TikHub 当前规则为准。

## 输出

典型 ResearchRun：

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

Raw Evidence 保留 Provider 原始响应（落盘前脱敏），Normalized/Derived 数据通过 `raw_evidence_id` 保持可追溯关系。

## 测试

```bash
PYTHONPATH=scripts python -m unittest \
  scripts/test_phase8.py \
  scripts/test_phase7.py \
  scripts/test_phase6.py \
  scripts/test_phase5.py \
  scripts/test_phase4.py \
  scripts/test_phase3.py \
  scripts/test_phase2.py \
  scripts/test_foundation.py \
  scripts/test_skill.py
```

另外：

```bash
python -m compileall -q scripts
python scripts/release_check.py --root .
```

GitHub Actions 只运行离线测试，不会自动执行 TikHub 付费请求。

## 安全

仓库默认忽略：

- `config.json` / `.env*`
- `runs/` / `raw/` / `normalized/` / `media/` / `reports/`
- SQLite 运行数据库
- Python cache
- live validation 输出

视频下载器拒绝 localhost、私网、link-local、reserved IP 和 `file://`，降低 SSRF/本地文件访问风险。

## License

当前仓库**尚未声明开源许可证**。公开可见不等于自动授予复制、修改和再分发许可。仓库所有者可在后续明确选择 MIT、Apache-2.0 或其他许可证。

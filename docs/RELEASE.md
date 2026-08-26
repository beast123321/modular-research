# Modular Research v1.0.0 发布说明

## 状态

`v1.0.0` 是第一个面向公开仓库与独立 Agent 使用的发布基线。

它包含：Research Intake / ResearchRequest、Profile Resolver、Endpoint Registry、Stage Planner、预算门、TikHub Evidence acquisition、SQLite Evidence Store、确定性 Metrics/Cohort/VOC、Video Creative Understanding contract、Pattern Mining、Insight/Hypothesis/MediaBrief synthesis contract，以及 bounded live-validation harness。

## 证据边界

已确认：

- 完整离线测试与编译可以自动重复执行。
- 网络执行默认关闭，付费 ResearchRun 需要 `--yes + --max-budget-usd`。
- 分发规则排除本地凭证、raw/media/runtime state。
- Phase 7 live-validation harness 能在 DNS/网络不可用时以 `BLOCKED_ENVIRONMENT` 停止，且不计为 Provider failure。

尚不能仅根据开发环境证据声称：

- 所有 TikHub endpoint 已完成真实生产网络 live validation。
- 文档中的 Provider 默认单价等同于用户最终账单。
- Pattern Lift 表示因果关系或保证未来视频表现。

## 发布前推荐动作

1. 在目标运行环境执行 `python scripts/check_environment.py --mode core`。
2. 执行 `python scripts/release_check.py --root .`。
3. 配置 `TIKHUB_API_KEY`。
4. 先执行 `scripts/live_validation.py` 的 plan 模式，再用小额硬预算 live probe。
5. 第一次业务研究先使用 `quick + --plan-only`。

## License

当前未声明许可证；此项由仓库所有者单独决策。

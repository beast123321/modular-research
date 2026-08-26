# 分析规格说明（analysis-spec.md）

本文件是**分析逻辑层的数据驱动配置**。引擎 `analysis_engine.py` 本身与平台无关，
它读这里的字段映射、阈值和分类法来工作。要支持新平台或新赛道，只改本文件，不改代码。

---

## 1. 字段映射（724 原始字段 → ~20 分析字段）

裸 API 响应有几百个字段，分析只保留下面这些。路径是"点分路径"，
末尾 `[*]` 表示收集该列表的全部元素。

| 规范字段 | 原始路径（Douyin/TikHub） | 含义 |
|---|---|---|
| `aweme_id` | `data.aweme_detail.aweme_id` | 视频 ID |
| `desc` | `data.aweme_detail.desc` | 文案 |
| `create_time` | `data.aweme_detail.create_time` | 发布时间（Unix） |
| `author_uid` | `data.aweme_detail.author.uid` | 作者 UID |
| `author_name` | `data.aweme_detail.author.nickname` | 作者名 |
| `follower_count` | `data.aweme_detail.author.follower_count` | **粉丝数（低粉判定依据）** |
| `total_favorited` | `data.aweme_detail.author.total_favorited` | 总获赞 |
| `digg_count` | `data.aweme_detail.statistics.digg_count` | 点赞 |
| `comment_count` | `data.aweme_detail.statistics.comment_count` | 评论数 |
| `share_count` | `data.aweme_detail.statistics.share_count` | 分享 |
| `collect_count` | `data.aweme_detail.statistics.collect_count` | 收藏 |
| `duration_ms` | `data.aweme_detail.duration` | 时长 |
| `hashtags` | `data.aweme_detail.text_extra[*].hashtag_name` | 话题标签 |

> 换平台时：把右侧路径改成新平台的等价字段即可。规范字段名保持不变，
> 下游所有分析逻辑（低粉判定、痛点聚类、选题空位）都不用改。

---

## 1.5 榜单模式字段（billboard）

榜单模式**免关键词、免付费搜索**，直接拉官方榜单发现视频池。它与第 1 节的
单视频字段映射共用同一套规范字段，但**入参不同、信封结构不同**。

### 1.5.1 入参：billboard_type

| billboard_type | 含义 | 适用场景 |
|---|---|---|
| `billboard_low_fan` | 低粉爆款榜（默认） | 发现"小号也能爆"的供给空白，**本 skill 主用** |
| `billboard_hot_video` | 热门视频榜 | 看大盘爆款风向 |
| `billboard_topic` | 热门话题榜 | 找上升期话题 |
| `billboard_challenge` | 挑战榜 | 找可参与的玩法 |

### 1.5.2 响应信封（多 key 容错，已线上验证）

TikHub 各榜单端点返回的视频列表嵌套在不同 key 下，`extract_billboard_list`
**先尝试单层、再尝试双层信封**（已对 `billboard_low_fan` 实测），按以下顺序
取第一个 list 值（无则空）：

```
# 单层
data.list / data.video_list / data.data_list / data.aweme_list / data.challenge_list
若 data 本身已是 list，则直接用
# 双层信封（低粉爆款榜实测真实形状）
data.data.objs          ← 真实榜单视频列表就在这里
data.data.{上述 list key}
```

> 实测：`billboard_low_fan` 真实响应为
> `data → {code, data:{page, objs}, extra}`，视频列表在 **`data.data.objs`**
> （每个元素是**扁平对象**，见 1.5.3，非 `aweme_detail` 嵌套）。

### 1.5.3 单条视频 → 规范字段（线上验证为扁平结构）

`normalize_billboard_videos` 对每条做多路径 `_dig`，**扁平**与**嵌套 aweme_detail**
两种形状都能解析（已在真实低粉榜上验证扁平路径可用）：

| 规范字段 | 尝试路径（真实扁平路径加粗） |
|---|---|
| `aweme_id` | **`item_id`** / `aweme_id` / `aweme_detail.aweme_id` |
| `desc` | **`item_title`** / `desc` / `aweme_detail.desc` / `title` / `share_title` |
| `author_uid` | `author.uid` / `aweme_detail.author.uid` / `uid`（**真实榜单无此字段，为 None**） |
| `author_name` | **`nick_name`** / `author.nickname` / `aweme_detail.author.nickname` |
| `follower_count` | **`fans_cnt`** / `author.follower_count` / `aweme_detail.author.follower_count` |
| `digg_count` | **`like_cnt`** / `statistics.digg_count` / `aweme_detail.statistics.digg_count` |
| `play_count` | **`play_cnt`** / `statistics.play_count` / `view_count` |
| `comment_count` / `share_count` / `collect_count` | 同上 statistics 族（真实榜单不含，为 None） |
| `score` | **`score`**（榜单热度分，用于排序） |
| `publish_time` | **`publish_time`** / `create_time` |
| `hashtags` | `text_extra[*].hashtag_name` / `aweme_detail.text_extra[*].hashtag_name` / `hashtags[*].name`（真实榜单不含） |

> 重要修正：**低粉爆款榜真实返回已含 `fans_cnt`（粉丝数）与 `like_cnt`（点赞）**，
> 因此 `follower_count` / `digg_count` 可直接用于第 2 节低粉爆款判定，**无需**
> 第 1.5.4 节的批量补查。批量补查按 `author_uid` 回填，而真实榜单不含 `uid`，
> 故对 billboard 模式为空操作（容错跳过），不影响判定。

### 1.5.4 批量用户补查（回填粉丝数）

发现视频池后，`run_research._enrich_records_followers` 收集所有 `author_uid`，
按 ≤50/批调用 `user_batch_profile`（逗号分隔 `sec_user_ids`），把粉丝数回填到
每条视频。补查响应经 `extract_user_list` 解析（`uid` / `nickname` / `follower_count`，
容错 `fan_count` / `sec_uid` 别名）。补查失败不影响其余已命中的记录。

### 1.5.5 去重与判定

- **去重**：按 `aweme_id` 去重（`dict.fromkeys` 保序）
- **低粉爆款判定**：完全复用第 2 节规则（follower_count ≤ 50000 且 digg_count ≥ 1000）
- **与搜索模式区别**：榜单模式不需要你提供关键词，也不消耗付费搜索额度；
  它用"官方已验证的爆款信号"替代"关键词召回"，更适合零基础起号时找方向。

---

## 2. 多源关联规则：低粉爆款判定

"低粉爆款"是教程的核心卖点，但搜索端点不返回粉丝数，**必须靠本规则补查账号资料后关联**。

```
判定条件（同时满足）:
  follower_count <= follower_threshold   (默认 50000)
  digg_count      >= engagement_min       (默认 1000)
排序指标: engagement_per_follower = digg_count / follower_count (降序)
```

- `follower_threshold`：低于此值视为"小账号"
- `engagement_min`：高于此值视为"表现超常"
- 可调：宠物小众赛道可调低 `follower_threshold`；泛娱乐赛道可调高

---

## 3. 痛点聚类分类法（宠物防滑袜示例）

评论区是金矿。把几百条评论映射到下面这个分类法，得到"用户真实痛点"而非情绪噪音。
每条是 `(标签, [触发关键词])`：

| 标签 | 触发词 |
|---|---|
| 防滑/打滑 | 防滑、打滑、滑倒、摔 |
| 尺码/不合脚 | 尺码、大小、不合、松、掉、脱落 |
| 透气/舒适 | 闷、透气、舒服、痒、过敏 |
| 价格/性价比 | 贵、便宜、性价比、划算、值 |
| 购买/在哪买 | 哪买、链接、同款、购买、下单 |
| 安装/使用 | 怎么穿、套不上、穿法、使用 |

> 分类法是**数据**，不是代码。做新赛道时替换这张表即可。
> 未命中任何标签的评论归入"其他"，用于发现新痛点。

---

## 4. 选题空位识别

给定一组"候选角度"关键词，统计每个角度在已抓取视频的文案/话题里被覆盖的次数。
覆盖数低 = 供给少 = 潜在空位（需结合外部搜索量判断需求）。

```
gap_score = 1 - coverage / total_records   (升序排列，越靠前越空)
```

---

## 5. 输出约束（结论必须可溯源）

所有洞察报告必须能回指原始数据：

- 报告里每一条"热门视频"都带 `aweme_id`，可回到 `raw/` 验证
- 每一条"痛点"都带示例评论原文，可回到评论原始数据验证
- 不允许只写"互动很好""内容不错"这类无出处的结论

详见 `references/output-schema.md`（如有）或本 skill 的 `SKILL.md`。

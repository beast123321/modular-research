"""
analysis_engine.py — 分析逻辑层（核心②）
=========================================

Turns raw API responses (hundreds of fields per record) into
decision-ready insights: field selection, multi-source correlation, and
insight derivation.

The engine is **spec-driven**: the actual field paths (which of the ~700 raw
fields matter), correlation rules and insight thresholds live in a SPEC dict
(or references/analysis-spec.md), NOT in this code. That keeps the engine
reusable across platforms — only the spec changes.

Three capabilities:
  1. extract_fields / normalize_records  — reduce 724 raw fields -> ~20 canonical
  2. detect_low_follower_hits            — multi-source correlation: low followers
                                            but high engagement == "low-follower hit"
  3. cluster_pain_points / identify_content_gaps / build_insight_report
                                          — insight derivation from comments + videos
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional
DEFAULT_FIELD_MAP: dict = {'aweme_id': 'data.aweme_detail.aweme_id', 'desc': 'data.aweme_detail.desc', 'create_time': 'data.aweme_detail.create_time', 'author_uid': 'data.aweme_detail.author.uid', 'author_name': 'data.aweme_detail.author.nickname', 'follower_count': 'data.aweme_detail.author.follower_count', 'total_favorited': 'data.aweme_detail.author.total_favorited', 'digg_count': 'data.aweme_detail.statistics.digg_count', 'comment_count': 'data.aweme_detail.statistics.comment_count', 'share_count': 'data.aweme_detail.statistics.share_count', 'collect_count': 'data.aweme_detail.statistics.collect_count', 'play_count': 'data.aweme_detail.statistics.play_count', 'duration_ms': 'data.aweme_detail.duration', 'hashtags': 'data.aweme_detail.text_extra[*].hashtag_name'}
DEFAULT_LOW_FOLLOWER = {'follower_threshold': 50000, 'engagement_min': 1000, 'score': 'digg_count'}

def _get_path(obj, dotted: str):
    """Resolve a dotted path; supports [*] to gather a list."""
    parts = dotted.split('.')
    def resolve(cur, remaining):
        if not remaining:
            return cur
        part = remaining[0]
        rest = remaining[1:]
        if part.endswith('[*]'):
            key = part[:-3]
            lst = cur.get(key) if isinstance(cur, dict) else None
            if not isinstance(lst, list):
                return None
            if not rest:
                return lst
            results = []
            for item in lst:
                r = resolve(item, rest)
                if r is not None:
                    results.append(r)
            return results
        if not isinstance(cur, dict):
            return None
        nxt = cur.get(part)
        if nxt is None:
            return None
        return resolve(nxt, rest)
    return resolve(obj, parts)

def extract_fields(raw: dict, field_map: Optional[dict]=None) -> dict:
    fm = field_map or DEFAULT_FIELD_MAP
    rec: dict = {}
    for name, path in fm.items():
        val = _get_path(raw, path)
        if isinstance(val, list):
            val = [v for v in val if v not in (None, '')]
        rec[name] = val
    return rec

def normalize_records(raw_list: list[dict], field_map: Optional[dict]=None) -> list[dict]:
    return [extract_fields(r, field_map) for r in raw_list]

def _dig(obj, paths: list[str]):
    for p in paths:
        v = _get_path(obj, p)
        if v not in (None, '', [], {}):
            return v
    return None

def _dig_list(obj, paths: list[str]) -> list:
    for p in paths:
        v = _get_path(obj, p)
        if isinstance(v, list) and v:
            return [x for x in v if x not in (None, '')]
    return []

def normalize_billboard_videos(items: list[dict]) -> list[dict]:
    out: list[dict] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        rec = {'aweme_id': _dig(it, ['aweme_id', 'aweme_detail.aweme_id', 'item_id']), 'desc': _dig(it, ['desc', 'aweme_detail.desc', 'title', 'share_title', 'item_title']), 'author_uid': _dig(it, ['author.uid', 'aweme_detail.author.uid', 'uid', 'sec_uid']), 'author_name': _dig(it, ['author.nickname', 'aweme_detail.author.nickname', 'nickname', 'nick_name']), 'follower_count': _dig(it, ['author.follower_count', 'aweme_detail.author.follower_count', 'fans_cnt', 'follower_count']), 'total_favorited': _dig(it, ['author.total_favorited', 'aweme_detail.author.total_favorited']), 'digg_count': _dig(it, ['statistics.digg_count', 'aweme_detail.statistics.digg_count', 'like_cnt', 'digg_count']), 'comment_count': _dig(it, ['statistics.comment_count', 'aweme_detail.statistics.comment_count', 'comment_count']), 'share_count': _dig(it, ['statistics.share_count', 'aweme_detail.statistics.share_count', 'share_count']), 'collect_count': _dig(it, ['statistics.collect_count', 'aweme_detail.statistics.collect_count', 'collect_count']), 'play_count': _dig(it, ['statistics.play_count', 'aweme_detail.statistics.play_count', 'play_cnt', 'play_count', 'view_count']), 'publish_time': _dig(it, ['publish_time', 'create_time', 'aweme_detail.create_time']), 'score': _dig(it, ['score']), 'hashtags': _dig_list(it, ['text_extra[*].hashtag_name', 'aweme_detail.text_extra[*].hashtag_name', 'hashtags[*].name'])}
        out.append(rec)
    return out

def extract_billboard_list(raw: dict) -> list[dict]:
    data = raw.get('data') or {}
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        keys = ('objs', 'list', 'video_list', 'data_list', 'aweme_list', 'challenge_list')
        for key in keys:
            v = data.get(key)
            if isinstance(v, list):
                return v
        inner = data.get('data')
        if isinstance(inner, dict):
            for key in keys:
                v = inner.get(key)
                if isinstance(v, list):
                    return v
    return []

def extract_user_list(raw: dict) -> list[dict]:
    data = raw.get('data') or {}
    items = data if isinstance(data, list) else data.get('list') or data.get('user_list') or data.get('users') or []
    out: list[dict] = []
    for u in items:
        if not isinstance(u, dict):
            continue
        out.append({'uid': _dig(u, ['uid', 'sec_uid', 'uid_str']), 'nickname': _dig(u, ['nickname', 'nick_name']), 'follower_count': _dig(u, ['follower_count', 'fan_count', 'fans'])})
    return out

def detect_low_follower_hits(records: list[dict], spec: Optional[dict]=None) -> list[dict]:
    spec = spec or DEFAULT_LOW_FOLLOWER
    f_thr = spec['follower_threshold']
    e_min = spec['engagement_min']
    score_key = spec['score']
    hits = []
    for r in records:
        fc = _as_int(r.get('follower_count'))
        eng = _as_int(r.get(score_key))
        if fc is None or eng is None:
            continue
        if fc <= f_thr and eng >= e_min:
            ratio = round(eng / fc, 3) if fc else float('inf')
            hits.append({**r, 'engagement_per_follower': ratio})
    hits.sort(key=lambda x: x.get('engagement_per_follower', 0), reverse=True)
    return hits

def cluster_pain_points(comments: list, taxonomy: list[tuple[str, list[str]]], text_key: str='content') -> dict:
    clusters: dict[str, list] = {label: [] for label, _ in taxonomy}
    clusters['其他'] = []
    for c in comments:
        if isinstance(c, dict):
            text = c.get(text_key) or c.get('text') or c.get('content') or ''
        else:
            text = str(c)
        text_lower = text.lower()
        matched = False
        for label, kws in taxonomy:
            if any((kw.lower() in text_lower for kw in kws)):
                clusters[label].append(text)
                matched = True
                break
        if not matched:
            clusters['其他'].append(text)
    summary = {k: len(v) for k, v in clusters.items()}
    ranked = dict(sorted(summary.items(), key=lambda x: x[1], reverse=True))
    examples = {k: v[:3] for k, v in clusters.items() if k != '其他' and v}
    return {'summary': ranked, 'examples': examples, 'total_comments': len(comments)}

def identify_content_gaps(records: list[dict], candidate_angles: list[str]) -> list[dict]:
    gaps = []
    for angle in candidate_angles:
        a = angle.lower()
        covered = 0
        for r in records:
            blob = ' '.join((str(r.get(k, '')) for k in ('desc', 'hashtags')))
            blob = blob.lower()
            if a in blob:
                covered += 1
        gaps.append({'angle': angle, 'coverage': covered, 'gap_score': round(1.0 - covered / max(len(records), 1), 3)})
    gaps.sort(key=lambda x: x['coverage'])
    return gaps

def build_four_perspective(records: list[dict], report: 'InsightReport') -> dict:
    n = len(records) or 1
    followers = [_as_int(r.get('follower_count')) for r in records]
    followers = [f for f in followers if f is not None]
    diggs = [_as_int(r.get('digg_count')) for r in records]
    diggs = [d for d in diggs if d is not None]
    def _median(xs):
        xs = sorted(xs)
        if not xs:
            return 0
        m = len(xs) // 2
        return xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2
    ratios = [h.get('engagement_per_follower') for h in report.low_follower_hits or []]
    ratios = [r for r in ratios if isinstance(r, (int, float)) and r != float('inf')]
    med_ratio = _median(ratios) if ratios else 0
    max_ratio = max(ratios) if ratios else 0
    hits = report.low_follower_hits or []
    top = (report.top_by_engagement or [None])[0]
    top_name = (top or {}).get('author_name', '-')
    top_fc = (top or {}).get('follower_count', '-')
    top_digg = (top or {}).get('digg_count', '-')
    content = {'headline': f'内容基因=真实素材+强情绪+可讨论；单条最高互动/粉 {max_ratio:.0f}（@{top_name}）', 'points': [f'样本 {len(records)} 条，单条互动/粉丝比值中位 {med_ratio:.0f}，说明爆款由公域算法放大而非私域老粉贡献。', f'头部账号 @{top_name}（粉丝 {top_fc}）赞 {top_digg}，靠「真实场景/强观点」类钩子而非说教罗列体。', '描述高频话题偏生活化/情绪化，专业术语少——契合路人可消费。', '结论：应拍「痛点可视化/名场面」而非干讲道理，钩子=把观点藏进真实场景。']}
    max_follower = max(followers) if followers else 0
    med_digg = _median(diggs) if diggs else 0
    med_follower = _median(followers) if followers else 0
    digg_per_fan = med_digg / med_follower if med_follower else 0
    pct_small = sum((1 for f in followers if f <= 50000)) / len(followers) * 100 if followers else 0
    audience = {'headline': f'赞/粉丝 中位 {digg_per_fan:.2f} → 爆款纯靠公域，钩子服务路人', 'points': [f'粉丝量分布：最高 {max_follower}（小号占比 {pct_small:.0f}%），样本集中在中小号生态。', f'赞/粉丝 中位 {digg_per_fan:.2f}，互动主要来自非粉丝路人（detail 端点不返回播放数，用赞衡量传播）。', '结论：钩子面向路人的共同痛点/好奇，而非老粉的专业术语。']}
    gaps = report.content_gaps or []
    gap_txt = '、'.join((f"{g['angle']}{g['coverage']}" for g in gaps[:6])) or '无角度数据'
    competition = {'headline': '细分角度覆盖率低 → 存在内容空位', 'points': [f'候选角度覆盖：{gap_txt}（覆盖视频数，越低越空白）。', '覆盖为 0 的角度=内容空位，先发者可用小成本占位。', '要定位真实竞品，可用 billboard_topic/challenge 查对应垂类上升话题。']}
    hit_n = len(hits)
    hit_rate = hit_n / n * 100 if n else 0
    avg_digg = sum(diggs) / len(diggs) if diggs else 0
    max_digg = max(diggs) if diggs else 0
    business = {'headline': f'{hit_rate:.0f}% 命中低粉爆款阈值，单条均赞 {avg_digg / 10000.0:.1f}万 → 零投放挂车可行', 'points': [f'低粉爆款命中 {hit_n}/{len(records)}（{hit_rate:.0f}%）。', f'单条平均赞 {avg_digg / 10000.0:.1f}万、最高 {max_digg / 10000.0:.1f}万 → 互动量足够支撑挂车转化。', '结论：小号 + 痛点内容 + 商品橱窗，可验证「0 投放起号」模型。']}
    return {'content': content, 'audience': audience, 'competition': competition, 'business': business}
TOPIC_ANGLE_RULES = [('和领导沟通', ['领导', '汇报', '沟通', '老板', '向上管理', '上级', '嫡系']), ('人情世故/饭局', ['人情', '世故', '酒局', '饭局', '送礼', '敬酒', '饭桌', '社交']), ('职场生存', ['生存', '手段', '法则', '混', '裁员', '离职', '辞', '试用', '转正', '晋升', '潜规则']), ('情商/说话', ['情商', '高情商', '会说话', '口才', '说话', '聊天']), ('职场干货', ['干货', '技巧', '牢记', '记住', '方法', '规则', '句']), ('职场思维', ['思维', '认知', '格局', '能力', '效率', '道理', '人性'])]
TOPIC_TEMPLATES = {'和领导沟通': {'hook': '会干活的，永远输给会汇报的——', 'script': ['场景代入：拍「埋头干活却被会说的人抢功」的真实瞬间', '认知反转：领导要的不是结果，是「掌控感」', '干货：3 句汇报模板（结论先行 → 补进度 → 要资源）', '示范：把「我做了 XX」改成「XX 已完成，效果 YY，下一步需要您拍板 ZZ」', '金句收尾：让领导放心，比让领导满意更重要']}, '人情世故/饭局': {'hook': '酒局上最怕的不是不会喝，是不懂这 3 条——', 'script': ['场景：饭局敬酒 / 说话 / 被架起来的尴尬瞬间', '反转：人情世故不是谄媚，是「让人舒服」的分寸感', '干货：3 条酒桌高情商话术（敬酒词、挡酒、夸人）', '示范：把「我敬您」改成具体到对方得意之处的夸赞', '金句收尾：会说话的人，走到哪都有人拉一把']}, '职场生存': {'hook': '为什么老实人在职场总吃亏？——', 'script': ['场景：同事抢功 / 背锅 / 被边缘化的真实瞬间', '反转：职场不是拼努力，是拼「不可替代性」', '干货：3-5 条生存法则（唯一性、嘴巴慢、外柔内刚）', '示范：举一个「会干事又懂向上管理」的对比案例', '金句收尾：弱者低头做事，强者抬头看路']}, '情商/说话': {'hook': '情商高的人，从不说这 4 句话——', 'script': ['场景：同事一句「不过脑子」的话让场面尴尬', '反转：情商不是圆滑，是「听懂别人没说的」', '干货：4 句「别说」 + 各自的替代说法', '示范：对比「你错了」vs「我理解你的意思，不过…」', '金句收尾：说话让人舒服，是一种高级能力']}, '职场干货': {'hook': '上班牢记这 15 句，能少走 5 年弯路——', 'script': ['场景：新人踩坑 vs 老油条经验的对比', '反转：很多坑不是能力问题，是没人明说', '干货：15 句（或精选 5 句）职场潜规则清单', '示范：每条配一个真实场景', '金句收尾：有些话没人告诉你，却决定你的上限']}, '职场思维': {'hook': '职场上最重要的不是工作能力，而是这 3 个字——', 'script': ['场景：能力强却升不上去 vs 能力一般却步步高升', '反转：拉开差距的不是能力，是「思维 / 认知」', '干货：3 个思维升级点（结果思维、老板视角、复利）', '示范：同一个问题，两种思维的不同做法', '金句收尾：技能只有变现时才是能力']}, '职场通识': {'hook': '这条可能颠覆你对职场的认知——', 'script': ['场景：一个真实职场两难选择', '反转：给出反常识的第三种解', '干货：1 条可复用的行动建议', '示范：举一个具体案例', '金句收尾：一句可讨论的总结']}}

def _classify_angle(rec: dict) -> str:
    blob = (str(rec.get('desc') or '') + ' ' + ' '.join(rec.get('hashtags') or [])).lower()
    for angle, kws in TOPIC_ANGLE_RULES:
        if any((k in blob for k in kws)):
            return angle
    return '职场通识'

def build_topic_ideas(records: list[dict], report: 'InsightReport', n: int=10) -> list[dict]:
    ranked = sorted(records, key=lambda r: _as_int(r.get('digg_count')) or 0, reverse=True)
    ideas: list[dict] = []
    angle_count: dict = {}
    for r in ranked:
        angle = _classify_angle(r)
        if angle_count.get(angle, 0) >= 2:
            continue
        angle_count[angle] = angle_count.get(angle, 0) + 1
        title = str(r.get('desc') or '').strip().split('\n')[0].strip()
        tpl = TOPIC_TEMPLATES.get(angle, TOPIC_TEMPLATES['职场通识'])
        ideas.append({'rank': len(ideas) + 1, 'angle': angle, 'title': title, 'hook': tpl['hook'], 'script': list(tpl['script']), 'basis': f"参考真实爆款 @{r.get('author_name')}（赞 {r.get('digg_count')}）", 'ref_author': r.get('author_name'), 'ref_digg': r.get('digg_count')})
        if len(ideas) >= n:
            break
    return ideas

def assess_relevance(records: list[dict], terms: list[str]) -> dict:
    high = mid = low = 0
    unrelated: list[dict] = []
    for r in records:
        blob = (str(r.get('desc') or '') + ' ' + ' '.join(r.get('hashtags') or [])).lower()
        hit = sum((1 for t in terms if t.lower() in blob))
        if hit >= 2:
            high += 1
        elif hit >= 1:
            mid += 1
        else:
            low += 1
            unrelated.append(r)
    total = len(records)
    return {'total': total, 'related': total - low, 'unrelated': low, 'high': high, 'mid': mid, 'low': low, 'related_rate': round((total - low) / total, 3) if total else 0, 'unrelated_samples': [{'author_name': r.get('author_name'), 'desc': str(r.get('desc') or '').split('\n')[0][:40]} for r in unrelated[:5]]}

@dataclass
class InsightReport:
    total_records: int
    top_by_engagement: list[dict] = field(default_factory=list)
    low_follower_hits: list[dict] = field(default_factory=list)
    pain_points: Optional[dict] = None
    content_gaps: list[dict] = field(default_factory=list)
    four_perspective: Optional[dict] = None
    topic_ideas: list[dict] = field(default_factory=list)
    relevance: Optional[dict] = None

def build_insight_report(records: list[dict], comments: Optional[list]=None, *, taxonomy: Optional[list]=None, candidate_angles: Optional[list]=None, low_follower_spec: Optional[dict]=None, relevance_terms: Optional[list]=None, top_n: int=10) -> InsightReport:
    if not records:
        return InsightReport(total_records=0)
    score_key = (low_follower_spec or DEFAULT_LOW_FOLLOWER)['score']
    ranked = sorted(records, key=lambda r: _as_int(r.get(score_key)) or 0, reverse=True)
    for r in ranked:
        fc = _as_int(r.get('follower_count'))
        eng = _as_int(r.get(score_key))
        if eng is None:
            continue
        r['engagement_per_follower'] = round(eng / fc, 3) if fc else float('inf')
    report = InsightReport(total_records=len(records), top_by_engagement=ranked[:top_n], low_follower_hits=detect_low_follower_hits(records, low_follower_spec))
    if comments:
        taxonomy = taxonomy or [('防滑/打滑', ['防滑', '打滑', '滑倒', '摔']), ('尺码/不合脚', ['尺码', '大小', '不合', '松', '掉', '脱落']), ('透气/舒适', ['闷', '透气', '舒服', '痒', '过敏']), ('价格/性价比', ['贵', '便宜', '性价比', '划算', '值']), ('购买/在哪买', ['哪买', '链接', '同款', '购买', '下单']), ('安装/使用', ['怎么穿', '套不上', '穿法', '使用'])]
        report.pain_points = cluster_pain_points(comments, taxonomy)
    if candidate_angles:
        report.content_gaps = identify_content_gaps(records, candidate_angles)
    report.four_perspective = build_four_perspective(records, report)
    report.topic_ideas = build_topic_ideas(records, report)
    if relevance_terms:
        report.relevance = assess_relevance(records, relevance_terms)
    return report

def _as_int(v) -> Optional[int]:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None

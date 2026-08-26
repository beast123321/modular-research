"""modular-research skill — 离线端到端测试（无需 API key / 不联网）。

覆盖三层：
  - 配套层 api_research_core：脱敏、阶梯估价、URL 校验、密钥解析降级
  - 核心① research_planner：端点解析、任务拆解估价、小样本校验门
  - 核心② analysis_engine：字段抽取、低粉爆款、痛点聚类、选题空位

真实"批量采集"需要 TikHub key + 付费额度，本测试不覆盖那一步。
"""
import os
import sys
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import api_research_core as core
import research_planner as planner
import analysis_engine as engine
import run_research as runner
PASS, FAIL = (0, 0)

def check(name, cond, detail=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f'  [PASS] {name}')
    else:
        FAIL += 1
        print(f'  [FAIL] {name}  {detail}')
print('=' * 60)
print('配套层 api_research_core')
print('=' * 60)
dirty = {'token': 'abc123', 'data': {'sign': 'xyz789', 'name': 'ok', 'cache_url': 'https://x/f?k=1'}}
clean = core.redact_payload(dirty)
check('redact_payload 脱敏 token', clean['token'] == '<redacted>')
check('redact_payload 脱敏嵌套 sign', clean['data']['sign'] == '<redacted>')
check('redact_payload 脱敏 cache_url', clean['data']['cache_url'] == '<redacted>')
check('redact_payload 保留非敏感字段', clean['data']['name'] == 'ok')
u = core.redact_url('https://api.x.io/fetch?sign=abc123&aweme_id=1&token=z')
check('redact_url 脱敏 query sign', 'sign=%2A' in u)
check('redact_url 保留非敏感 query', 'aweme_id=1' in u)
check('redact_url 不泄露原值', 'abc123' not in u)
c = core.estimate_cost(1200, core.Decimal('0.001'))
check('estimate_cost 总需求数', c['requests'] == 1200)
check('estimate_cost 存在折扣档', c['estimated_total_usd'] < 1200 * 0.001)
check('estimate_cost 平均单价<基准', c['average_unit_price_usd'] < 0.001)
try:
    core.estimate_cost(0, core.Decimal('0.001'))
    check('estimate_cost 拒绝 0 请求', False, '应抛 ValueError')
except ValueError:
    check('estimate_cost 拒绝 0 请求', True)
key, src = core.resolve_api_key(disable_keychain=True)
check('resolve_api_key 无 key 不崩溃', key == '' and src == 'missing')
try:
    core.build_url('https://api.x.io', '//evil', None)
    check('validate_path 拒绝双斜杠注入', False, '应抛 ValueError')
except ValueError:
    check('validate_path 拒绝双斜杠注入', True)
print('=' * 60)
print('核心① research_planner')
print('=' * 60)
plan = planner.decompose_task('宠物防滑袜选题调研', keywords=['宠物防滑袜', '狗狗防滑', '猫打滑'], videos_per_keyword=10, accounts_to_profile=20)
check('decompose 生成 4 个采集步骤', len(plan.steps) == 4)
check('decompose 含 video_search(付费)', 'video_search' in plan.blocked_by_paid)
check('decompose 总费用>0', plan.total_cost_usd > 0)
print('    --- 费用预览 ---')
print(plan.summary())
plan_free = planner.decompose_task('验证用', keywords=['x'], only_free=True, videos_per_keyword=3)
check('only_free 无付费环节', plan_free.blocked_by_paid == [])
valid_video = {'data': {'aweme_detail': {'aweme_id': '7300001', 'desc': '宠物防滑袜测评 #狗狗', 'author': {'uid': 'u1', 'nickname': '小宠日记', 'follower_count': 8000, 'total_favorited': 50000}, 'statistics': {'digg_count': 12000, 'comment_count': 300, 'share_count': 200, 'collect_count': 400}, 'duration': 39000, 'text_extra': [{'hashtag_name': '狗狗'}]}}}
ok, reasons = planner.validate_sample(valid_video, 'video_detail')
check('validate_sample 结构齐全→通过', ok, str(reasons))
bad_video = {'data': {'aweme_detail': {'aweme_id': '2', 'desc': 'x'}}}
ok2, reasons2 = planner.validate_sample(bad_video, 'video_detail')
check('validate_sample 缺字段→拦截', not ok2, str(reasons2))
check('validate_sample 说明缺哪个字段', any(('follower_count' in r for r in reasons2)))
order = planner.collection_order()
check('采集优先级 user_profile 最先', order[0] == 'user_profile')
check('采集优先级 video_search 最后', order[-1] == 'video_search')
print('=' * 60)
print('核心② analysis_engine')
print('=' * 60)
rec = engine.extract_fields(valid_video)
check('extract_fields 取 aweme_id', rec['aweme_id'] == '7300001')
check('extract_fields 取 hashtags', rec['hashtags'] == ['狗狗'])
low_rec = {'aweme_id': '9', 'follower_count': 8000, 'digg_count': 12000, 'author_name': '小号'}
high_rec = {'aweme_id': '10', 'follower_count': 800000, 'digg_count': 5000, 'author_name': '大号'}
hits = engine.detect_low_follower_hits([low_rec, high_rec])
check('detect_low_follower 命中低粉高互动', len(hits) == 1)
check('detect_low_follower 命中小号', hits[0]['aweme_id'] == '9')
comments = [{'content': '我家狗总打滑，这个防滑袜有用吗'}, {'content': '尺码偏大，老是掉'}, {'content': '有点贵，但性价比还行'}, {'content': '在哪买同款'}, {'content': '纯路过围观'}]
tax = [('防滑/打滑', ['防滑', '打滑', '滑倒', '摔']), ('尺码/不合脚', ['尺码', '大小', '不合', '松', '掉', '脱落']), ('价格/性价比', ['贵', '便宜', '性价比', '划算', '值']), ('购买/在哪买', ['哪买', '链接', '同款', '购买', '下单'])]
pp = engine.cluster_pain_points(comments, tax)
check('cluster 总评论数', pp['total_comments'] == len(comments))
check('cluster 命中防滑簇', pp['summary'].get('防滑/打滑', 0) >= 1)
check("cluster 其余进'其他'", pp['summary'].get('其他', 0) >= 1)
gaps = engine.identify_content_gaps([rec], ['老年犬', '猫用', '训练'])
check('identify_content_gaps 返回列表', isinstance(gaps, list) and len(gaps) == 3)
check('identify_content_gaps 按覆盖率升序', gaps[0]['coverage'] <= gaps[-1]['coverage'])
raw_list = [valid_video]
report = engine.build_insight_report(engine.normalize_records(raw_list), comments, taxonomy=tax, candidate_angles=['老年犬', '猫用'])
check('build_report 记录数', report.total_records == 1)
check('build_report 有痛点', report.pain_points is not None)
check('build_report 有选题空位', len(report.content_gaps) == 2)
print('=' * 60)
print('榜单与批量补查（P0 新增覆盖）')
print('=' * 60)
bb_list = [{'aweme_id': 'x1'}, {'aweme_id': 'x2'}]
for key in ('list', 'video_list', 'data_list', 'aweme_list', 'challenge_list'):
    raw = {'data': {key: bb_list}}
    got = engine.extract_billboard_list(raw)
    check(f'extract_billboard_list 识别 {key}', got is bb_list, str(got))
raw_dl = {'data': bb_list}
check('extract_billboard_list data 为 list', engine.extract_billboard_list(raw_dl) is bb_list)
raw_empty = {'data': {'code': 0}}
check('extract_billboard_list 无列表→空', engine.extract_billboard_list(raw_empty) == [])
flat = {'aweme_id': 'B1', 'desc': '低粉爆款 #防滑', 'author': {'uid': 'u1', 'nickname': '小宠日记', 'follower_count': 8000}, 'statistics': {'digg_count': 12000, 'comment_count': 300, 'share_count': 200, 'collect_count': 400}, 'text_extra': [{'hashtag_name': '防滑'}]}
rec = engine.normalize_billboard_videos([flat])[0]
check('normalize 取 aweme_id', rec['aweme_id'] == 'B1')
check('normalize 取 author_uid', rec['author_uid'] == 'u1')
check('normalize 取 follower_count', rec['follower_count'] == 8000)
check('normalize 取 digg_count', rec['digg_count'] == 12000)
check('normalize 取 hashtags[*]', rec['hashtags'] == ['防滑'])
nested = {'aweme_detail': {'aweme_id': 'B9', 'desc': '嵌套', 'author': {'uid': 'u9', 'nickname': 'N', 'follower_count': 5000}, 'statistics': {'digg_count': 3000}, 'text_extra': [{'hashtag_name': '猫用'}]}}
rec_n = engine.normalize_billboard_videos([nested])[0]
check('normalize 嵌套取 aweme_id', rec_n['aweme_id'] == 'B9')
check('normalize 嵌套取 follower_count', rec_n['follower_count'] == 5000)
check('normalize 嵌套取 hashtags', rec_n['hashtags'] == ['猫用'])
ub_raw = {'data': {'list': [{'uid': 'u1', 'nickname': 'A', 'follower_count': 100}, {'uid': 'u2', 'nick_name': 'B', 'fan_count': 200}, 'garbage']}}
ubs = engine.extract_user_list(ub_raw)
check('extract_user_list 数量(跳过非 dict)', len(ubs) == 2, str(ubs))
check('extract_user_list uid', ubs[0]['uid'] == 'u1')
check('extract_user_list follower_count', ubs[0]['follower_count'] == 100)
check('extract_user_list fan_count 别名', ubs[1]['follower_count'] == 200)
plan_bb = planner.decompose_task('低粉爆款榜选题调研', keywords=[], billboard=True, billboard_type='billboard_low_fan')
step_names = [s.data_need for s in plan_bb.steps]
check('decompose billboard 含 billboard_low_fan', 'billboard_low_fan' in step_names)
check('decompose billboard 含 user_batch_profile', 'user_batch_profile' in step_names)
check('decompose billboard 全免费(无付费拦截)', plan_bb.blocked_by_paid == [])
plan_topic = planner.decompose_task('热门话题调研', keywords=[], billboard=True, billboard_type='billboard_topic')
check('decompose billboard_topic 步骤名变化', 'billboard_topic' in [s.data_need for s in plan_topic.steps])
demo = runner._demo_billboard_items()
check('_demo_billboard_items 4 条', len(demo) == 4)
check('_demo_billboard_items 均含 author.follower_count', all((isinstance(d['author']['follower_count'], int) for d in demo)))
demo_raw = {'data': {'list': runner._demo_billboard_items()}}
demo_vids = engine.extract_billboard_list(demo_raw)
demo_recs = engine.normalize_billboard_videos(demo_vids)
demo_hits = engine.detect_low_follower_hits(demo_recs)
check('端到端 低粉命中 2 条', len(demo_hits) == 2, str([h['aweme_id'] for h in demo_hits]))
real_envelope = {'data': {'code': 0, 'data': {'page': 1, 'objs': bb_list}, 'extra': {'now': 'x'}}}
check('extract_billboard_list 双层信封 objs', engine.extract_billboard_list(real_envelope) is bb_list)
real_item = {'item_id': 'R1', 'item_title': '宠物防滑袜实测 #防滑', 'nick_name': '小宠日记', 'fans_cnt': 8000, 'like_cnt': 12000, 'play_cnt': 50000, 'score': 99.5, 'publish_time': 1700000000}
r_real = engine.normalize_billboard_videos([real_item])[0]
check('真实扁平 取 aweme_id←item_id', r_real['aweme_id'] == 'R1')
check('真实扁平 取 desc←item_title', r_real['desc'] == '宠物防滑袜实测 #防滑')
check('真实扁平 取 author_name←nick_name', r_real['author_name'] == '小宠日记')
check('真实扁平 取 follower_count←fans_cnt', r_real['follower_count'] == 8000)
check('真实扁平 取 digg_count←like_cnt', r_real['digg_count'] == 12000)
check('真实扁平 取 play_count←play_cnt', r_real['play_count'] == 50000)
check('真实扁平 取 score', r_real['score'] == 99.5)
real_raw = {'data': {'code': 0, 'data': {'page': 1, 'objs': [{'item_id': 'R1', 'item_title': '低粉爆款', 'nick_name': '小宠', 'fans_cnt': 8000, 'like_cnt': 12000}, {'item_id': 'R2', 'item_title': '大V', 'nick_name': '大V', 'fans_cnt': 800000, 'like_cnt': 5000}]}}}
real_recs = engine.normalize_billboard_videos(engine.extract_billboard_list(real_raw))
check('端到端 真实信封 抽出 2 条', len(real_recs) == 2, str(real_recs))
real_hits = engine.detect_low_follower_hits(real_recs)
check('端到端 真实信封 低粉命中 1 条(R1)', len(real_hits) == 1 and real_hits[0]['aweme_id'] == 'R1', str([h['aweme_id'] for h in real_hits]))
fp_report = engine.build_insight_report(real_recs, None, candidate_angles=['老年犬', '猫用', '训练', '测评', '选购'])
fp = fp_report.four_perspective
check('四视角 返回 4 个视角', set((fp or {}).keys()) == {'content', 'audience', 'competition', 'business'})
for k in ('content', 'audience', 'competition', 'business'):
    sec = (fp or {}).get(k) or {}
    check(f'四视角 {k} 含 headline', bool(sec.get('headline')))
    check(f'四视角 {k} 含 points(≥1)', len(sec.get('points') or []) >= 1)
import run_research as rr
from pathlib import Path
import tempfile
tmp = Path(tempfile.mkdtemp())
(tmp / 'reports').mkdir(parents=True)
(tmp / 'reports' / 'insight_report.json').write_text('{}', encoding='utf-8')
(tmp / '_run_state.json').write_text('{}', encoding='utf-8')

class _A:
    pass
_a = _A()
_a.goal = '测试'
_a.billboard = True
_a.billboard_type = 'billboard_low_fan'

class _R:
    metrics = {'estimated_cost_usd': 0.0, 'key_source': 'config.json'}
_a_dir = tmp
run_id = 'run_test001'
meta = rr._build_meta(_a, 'billboard', run_id, fp_report, {'generated_at': '2026-08-25T00:00:00+00:00'}, _R(), 'config.json')
rr._archive_run(tmp, meta)
hist = tmp / 'history' / run_id
check('归档 目录存在', hist.is_dir())
check('归档 含 meta.json', (hist / 'meta.json').is_file())
check('归档 含 reports/', (hist / 'reports').is_dir())
check('归档 meta.run_id 正确', json.loads((hist / 'meta.json').read_text(encoding='utf-8'))['run_id'] == run_id)
check('归档 目录穿越防护(_build_meta 不报错)', isinstance(meta, dict))
print('=' * 60)
print(f'结果: {PASS} 通过 / {FAIL} 失败')
print('=' * 60)
sys.exit(1 if FAIL else 0)

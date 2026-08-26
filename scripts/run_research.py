from __future__ import annotations
import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import api_research_core as core
import research_planner as planner
import analysis_engine as engine
from research_request import ResearchRequest
from profile_resolver import resolve_profile
from stage_planner import build_stage_plan as _build_stage_plan
from research_executor_v2 import ResearchExecutorV2
DEFAULT_OUT = 'social-research'

def load_research_request_from_args(args) -> ResearchRequest | None:
    request_path = getattr(args, 'request', None)
    topic = getattr(args, 'topic', None)
    platform = getattr(args, 'platform', None)
    market = getattr(args, 'market', None)
    goals = list(getattr(args, 'research_goal', None) or [])
    reference_urls = list(getattr(args, 'reference_url', None) or [])
    depth = getattr(args, 'depth', 'standard') or 'standard'
    convenience_used = bool(topic or platform or market or goals or reference_urls)
    if request_path and convenience_used:
        raise ValueError('cannot mix --request with --topic/--platform/--market/--research-goal/--reference-url')
    if request_path:
        payload = json.loads(Path(request_path).read_text(encoding='utf-8'))
        return ResearchRequest.from_dict(payload)
    if convenience_used:
        payload = {
            'topic': topic,
            'platform': platform,
            'market': market,
            'research_goals': goals,
            'depth': depth,
            'user_goal_text': getattr(args, 'goal', None),
            'reference_content': [
                {'platform': platform, 'url': url, 'content_id': None, 'role': 'style_reference'}
                for url in reference_urls
            ],
        }
        return ResearchRequest.from_dict(payload)
    return None

def build_v2_stage_plan(request: ResearchRequest):
    return _build_stage_plan(request)

def validate_v2_execution_gate(plan, *, yes: bool, max_budget_usd: float | None) -> tuple[bool, str]:
    if not yes:
        return (False, 'V2 真实执行需要显式 --yes。')
    if max_budget_usd is None:
        return (False, 'V2 真实执行需要 --max-budget-usd 预算上限。')
    if float(max_budget_usd) < float(plan.max_cost_usd):
        return (False, f'预算不足：--max-budget-usd={float(max_budget_usd):.6f}，计划最大成本={float(plan.max_cost_usd):.6f} USD。')
    return (True, 'approved')

def build_intake_plan(request: ResearchRequest) -> dict:
    resolution = resolve_profile(request)
    return {'execution_status': 'PLAN_ONLY_FOUNDATION', 'request': request.to_dict(), 'missing_material_fields': request.validate_material_fields(), 'profile': {'profile_id': resolution.profile_id, 'reason_codes': resolution.reason_codes, 'confidence': resolution.confidence, 'warnings': resolution.warnings}}
DEFAULT_CONFIG = HERE.parent / 'config.json'
DEFAULT_TAXONOMY = [('领导/汇报/沟通', ['领导', '老板', '汇报', '沟通', '向上管理', '说话', '聊天', '开会']), ('人情世故/饭局', ['人情', '世故', '酒局', '饭局', '送礼', '饭桌', '敬酒']), ('职场生存/晋升', ['裁员', '绩效', '晋升', '跳槽', '离职', '加薪', '辞退', '试用', '转正']), ('情商/说话艺术', ['情商', '高情商', '低情商', '会说话', '口才', '圆滑']), ('干货/方法论', ['干货', '技巧', '方法', '规则', '牢记', '记住', '建议'])]
RELATED_TERMS = ['职场', '人情', '世故', '领导', '老板', '汇报', '沟通', '向上管理', '情商', '说话', '酒局', '饭局', '社交', '同事', '裁员', '离职', '晋升', '干货', '技巧', '人性', '认知', '思维', '格局', '生存', '手段', '法则', '心眼', '潜规则', '嫡系', '酒桌', '敬酒', '为人', '处事', '处世', '打交道', '关系']
_reporter = None

def set_reporter(reporter) -> None:
    global _reporter
    _reporter = reporter

def log(step: str, msg: str) -> None:
    line = f'[{step}] {msg}'
    print(line)
    if _reporter is not None:
        _reporter.note(line)

class ProgressReporter:
    STEPS = ['plan', 'validate', 'collect', 'normalize', 'report']
    def __init__(self, out_dir: Path):
        self.out_dir = out_dir
        self.state_path = out_dir / '_run_state.json'
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.entries: list[dict] = []
        self.logs: list[str] = []
        self.metrics: dict = {'goal': '', 'mode': '', 'base_url': '', 'total_requests': 0, 'estimated_cost_usd': 0.0, 'blocked_by_paid': [], 'videos': 0, 'comments': 0, 'low_follower_hits': 0}
    def _write(self) -> None:
        payload = {'started_at': self.started_at, 'updated_at': datetime.now(timezone.utc).isoformat(), 'running': self.metrics.get('running', True), 'entries': self.entries, 'logs': self.logs, 'metrics': self.metrics}
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    def set(self, **kw) -> None:
        self.metrics.update(kw); self._write()
    def event(self, name: str, status: str, detail: str='') -> None:
        self.entries.append({'step': name, 'status': status, 'detail': detail, 'at': datetime.now(timezone.utc).isoformat()}); self._write()
    def note(self, line: str) -> None:
        self.logs.append(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {line}"); self._write()

def ensure_dirs(out: Path) -> dict:
    dirs = {name: out / name for name in ('raw', 'normalized', 'media', 'reports')}
    for d in dirs.values(): d.mkdir(parents=True, exist_ok=True)
    return dirs

def save_redacted(dirs: dict, kind: str, ident: str, payload: dict) -> Path:
    safe = core.redact_payload(payload)
    ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    path = dirs['raw'] / f'{kind}_{ident}_{ts}.json'
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding='utf-8')
    return path

def fetch_one(api_key: str, provider: str, platform: str, data_need: str, params: dict | None=None, method: str | None=None, base_url: str | None=None, body: dict | None=None) -> dict:
    spec = planner.resolve_endpoint(provider, platform, data_need)
    return core.request_json(base_url=base_url or core.DEFAULT_BASE_URL, api_key=api_key, method=method or spec['method'], path=spec['path'], params=params, body=body)

def _demo_payloads(video_ids: list[str]):
    samples=[]; comments=[]
    demo_authors=[('u_small','小宠日记',8000,50000,12000),('u_big','宠物大V',800000,5000000,5000),('u_mid','测袜君',42000,200000,980),('u_tiny','萌宠新手',1500,9000,2300),('u_mid2','铲屎官阿强',67000,330000,1500)]
    demo_comments=['我家狗总打滑，这个防滑袜有用吗','尺码偏大，老是掉','脚踝那里有点闷，夏天穿会不会痒','有点贵，但性价比还行','在哪买同款啊求链接','怎么穿上去，套了好久套不上','猫能用吗？我家布偶总在瓷砖上摔','买给老年犬的，它关节不好需要防滑','这个测评很真实，已下单','防滑效果不错，就是价格小贵','掉毛严重，洗完还能用吗','纯围观，我家是布偶猫']
    for i,vid in enumerate(video_ids):
        uid,name,fc,tf,digg=demo_authors[i%len(demo_authors)]
        detail={'data':{'aweme_detail':{'aweme_id':str(vid),'desc':f'宠物防滑袜测评第{i+1}期 #狗狗 #宠物防滑袜 #猫用','author':{'uid':uid,'nickname':name,'follower_count':fc,'total_favorited':tf},'statistics':{'digg_count':digg,'comment_count':len(demo_comments)//2,'share_count':20+i*5,'collect_count':40+i*10},'duration':39000,'text_extra':[{'hashtag_name':'狗狗'},{'hashtag_name':'宠物防滑袜'}]}}}
        samples.append(detail)
        for c in demo_comments[:4+i]: comments.append({'content':c})
    return samples,comments

def _demo_billboard_items():
    return [{'aweme_id':'B1','desc':'低粉爆款：狗狗防滑袜实测 #防滑','author':{'uid':'u1','nickname':'小宠日记','follower_count':8000},'statistics':{'digg_count':12000,'comment_count':300,'share_count':200,'collect_count':400},'text_extra':[{'hashtag_name':'防滑'}]},{'aweme_id':'B2','desc':'猫用防滑袜 #猫用','author':{'uid':'u2','nickname':'萌宠新手','follower_count':1500},'statistics':{'digg_count':2300,'comment_count':120,'share_count':30,'collect_count':90},'text_extra':[{'hashtag_name':'猫用'}]},{'aweme_id':'B3','desc':'老年犬防滑测评','author':{'uid':'u3','nickname':'测袜君','follower_count':42000},'statistics':{'digg_count':980,'comment_count':80,'share_count':10,'collect_count':50},'text_extra':[{'hashtag_name':'老年犬'}]},{'aweme_id':'B4','desc':'防滑袜合集 #狗狗','author':{'uid':'u4','nickname':'宠物大V','follower_count':800000},'statistics':{'digg_count':5000,'comment_count':400,'share_count':100,'collect_count':300},'text_extra':[{'hashtag_name':'狗狗'}]}]

def _emit_report(dirs, report_data, rpt_path, md_path, reporter):
    rpt_path.write_text(json.dumps(report_data,ensure_ascii=False,indent=2),encoding='utf-8'); md_path.write_text(_render_markdown(report_data),encoding='utf-8'); fp=report_data.get('four_perspective')
    if fp:
        (dirs['reports']/'four_perspective.json').write_text(json.dumps(fp,ensure_ascii=False,indent=2),encoding='utf-8'); (dirs['reports']/'four_perspective.md').write_text(_render_four_perspective_md(fp),encoding='utf-8')
    ti=report_data.get('topic_ideas')
    if ti:
        (dirs['reports']/'topic_ideas.json').write_text(json.dumps(ti,ensure_ascii=False,indent=2),encoding='utf-8'); (dirs['reports']/'起号选题清单.md').write_text(_render_topic_ideas_md(ti),encoding='utf-8')

def _render_four_perspective_md(fp:dict)->str:
    labels={'content':'📝 内容视角','audience':'👥 人群视角','competition':'⚔️ 竞品视角','business':'💰 商业视角'}; lines=['# 四视角深度分析（内容 / 人群 / 竞品 / 商业）','']
    for k,label in labels.items():
        sec=fp.get(k) or {}
        if not sec: continue
        lines.append(f'## {label}')
        if sec.get('headline'): lines.append(f"> {sec['headline']}")
        lines.append('')
        for pt in sec.get('points',[]): lines.append(f'- {pt}')
        lines.append('')
    return '\n'.join(lines)

def _render_topic_ideas_md(ti:list[dict])->str:
    lines=['# 起号选题清单（可拍的脚本 / 标题）','',f'> 共 {len(ti)} 条，每条含：标题、开头钩子、5 步脚本、数据依据。','']
    for it in ti:
        lines.append(f"## {it['rank']}. 【{it['angle']}】{it['title']}"); lines.append(''); lines.append(f"- **开头钩子**：{it['hook']}"); lines.append('- **脚本要点**：')
        for s in it.get('script',[]): lines.append(f'  - {s}')
        lines.append(f"- **数据依据**：{it['basis']}"); lines.append('')
    return '\n'.join(lines)

def run(args)->int:
    provider,platform=planner.DEFAULT_PROVIDER,planner.DEFAULT_PLATFORM; out_dir=Path(args.out); reporter=ProgressReporter(out_dir); set_reporter(reporter); run_id='run_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'); mode='demo' if args.demo else 'only-free' if args.only_free else 'billboard' if args.billboard else 'with-search'; reporter.set(goal=args.goal,mode=mode,base_url=args.base_url,running=True,run_id=run_id); reporter.event('plan','running','拆解任务并估算费用'); plan=planner.decompose_task(args.goal,keywords=args.keywords or [],videos_per_keyword=args.videos_per_keyword,accounts_to_profile=args.accounts_to_profile,only_free=args.only_free,billboard=args.billboard,billboard_type=args.billboard_type); reporter.set(total_requests=plan.total_requests,estimated_cost_usd=plan.total_cost_usd,blocked_by_paid=plan.blocked_by_paid); log('计划',plan.summary()); reporter.event('plan','ok',f'总请求 {plan.total_requests}，预估 ${plan.total_cost_usd:.4f}')
    if args.plan_only: reporter.set(running=False); log('计划','仅展示费用预览（--plan-only）。配好 TIKHUB_API_KEY 后去掉该参数即可真实运行。'); return 0
    if args.demo:
        dirs=ensure_dirs(out_dir); log('DEMO','使用合成数据演练编排 I/O（不联网、不花钱、不需要 API Key）。')
        if args.billboard: items=_demo_billboard_items(); records=engine.normalize_billboard_videos(items); comments=[{'content':'狗狗打滑怎么办'},{'content':'尺码偏大老掉'},{'content':'猫能用吗'}]; kind='billboard'
        else: ids=args.video_ids or ['7300001','7300002','7300003']; samples,comments=_demo_payloads(ids); records=engine.normalize_records(samples); kind='detail'
        reporter.event('validate','ok','合成样本字段齐全'); log('校验','合成样本通过校验门'); reporter.event('collect','running',f'模拟批量采集 {len(records)} 条视频（脱敏落盘）')
        for i,rec in enumerate(records): save_redacted(dirs,kind,f'demo{i}',{'data':rec})
        reporter.event('collect','ok',f'落盘 {len(records)} 条 {kind} 到 raw/'); norm_path=dirs['normalized']/'records.json'; norm_path.write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8'); log('清洗',f'结构化 {len(records)} 条 → {norm_path.name}'); report=engine.build_insight_report(records,comments,taxonomy=DEFAULT_TAXONOMY,candidate_angles=args.angles or args.keywords or ['通用'],relevance_terms=RELATED_TERMS); report_data=_report_dict(args.goal,report); rpt_path=dirs['reports']/'insight_report.json'; md_path=dirs['reports']/'insight_report.md'; _emit_report(dirs,report_data,rpt_path,md_path,reporter); reporter.set(videos=len(records),comments=len(comments),low_follower_hits=len(report.low_follower_hits),running=False); log('报告',f'已生成 {rpt_path.name} 与 {md_path.name}'); _archive_run(out_dir,_build_meta(args,mode,run_id,report,report_data,reporter,'demo')); log('归档',f'已归档本次运行到 history/{run_id}/'); log('完成',f'DEMO 演练结束：{len(records)} 视频 / {len(comments)} 评论，证据在 raw/。'); return 0
    if plan.blocked_by_paid and not args.yes: reporter.event('plan','skip',f'付费环节 {plan.blocked_by_paid} 未确认 --yes，已拦停'); reporter.set(running=False); log('拦停',f'存在付费环节 {plan.blocked_by_paid}，需显式传 --yes 确认才会花额度。已退出。'); return 2
    api_key,src=core.resolve_api_key(config_path=args.config)
    if not api_key: reporter.event('validate','fail','未检测到密钥（环境变量与 config.json 均无）'); reporter.set(running=False); log('缺密钥','未检测到密钥。请二选一：① 设置环境变量 TIKHUB_API_KEY；② 编辑 config.json 填入 api_key 字段（路径见 --config）。'); return 2
    log('密钥',f'已从 {src} 读取（值不打印）'); reporter.set(key_source=src); dirs=ensure_dirs(out_dir); log('目录',f'证据将写入 {out_dir.resolve()}/{{raw,normalized,media,reports}}'); reporter.event('validate','running','采集样本验证字段结构')
    if args.billboard:
        try: sample=fetch_one(api_key,provider,platform,args.billboard_type,{},base_url=args.base_url)
        except Exception as e: reporter.event('validate','fail',f'榜单样本请求失败：{e}'); reporter.set(running=False); log('校验',f'榜单样本请求失败（{e}），未联网到下游。退出。'); return 1
        ok,reasons=True,[]
    elif args.video_ids: sample=fetch_one(api_key,provider,platform,'video_detail',{'aweme_id':args.video_ids[0]},base_url=args.base_url); ok,reasons=planner.validate_sample(sample,'video_detail')
    else: ok,reasons=True,[]
    if not ok: reporter.event('validate','fail',str(reasons)); reporter.set(running=False); log('校验',f'样本未通过，先修再批量：{reasons}'); ident=args.video_ids[0] if not args.billboard else args.billboard_type; save_redacted(dirs,'sample_fail',ident,sample); return 1
    reporter.event('validate','ok','样本通过校验门'); log('校验','样本通过，进入批量采集'); reporter.event('collect','running','按成本优先级批量采集'); raw_details=[]; comments=[]; records=[]
    if args.billboard:
        try: resp=fetch_one(api_key,provider,platform,args.billboard_type,{},base_url=args.base_url)
        except Exception as e: reporter.event('collect','fail',f'榜单请求失败：{e}'); reporter.set(running=False); log('采集',f'榜单请求失败（{e}），无证据可分析。退出。'); return 1
        save_redacted(dirs,'billboard',args.billboard_type,resp); items=engine.extract_billboard_list(resp); records=engine.normalize_billboard_videos(items); log('采集',f'榜单返回 {len(records)} 条视频候选')
    else:
        aweme_ids=list(args.video_ids)
        if not args.only_free and args.keywords:
            log('采集','video_search（付费）发现视频池')
            for kw in args.keywords: resp=fetch_one(api_key,provider,platform,'video_search',params=None,method='POST',body={'keyword':kw},base_url=args.base_url); save_redacted(dirs,'search',kw,resp); found=_extract_aweme_ids_from_search(resp); aweme_ids.extend(found[:args.videos_per_keyword])
            aweme_ids=list(dict.fromkeys(aweme_ids)); log('采集',f'搜索共得到 {len(aweme_ids)} 个视频ID')
        for vid in aweme_ids:
            try: resp=fetch_one(api_key,provider,platform,'video_detail',{'aweme_id':vid},base_url=args.base_url)
            except Exception as e: log('详情',f'视频 {vid} 详情请求失败（{e}），跳过继续'); continue
            save_redacted(dirs,'detail',vid,resp); raw_details.append(resp)
        for vid in aweme_ids[:args.comment_videos]:
            try: resp=fetch_one(api_key,provider,platform,'video_comments',{'aweme_id':int(vid)},base_url=args.base_url)
            except Exception as e: log('评论',f'视频 {vid} 评论请求失败（{e}），跳过继续'); continue
            save_redacted(dirs,'comments',vid,resp); comments.extend(_extract_comments(resp))
        records=engine.normalize_records(raw_details)
    enriched=_enrich_records_followers(dirs,api_key,platform,records,args.base_url)
    if enriched: log('采集',f'批量补查 {enriched} 个作者粉丝数')
    reporter.event('collect','ok',f'采集 {len(records)} 视频 / {len(comments)} 评论，均已脱敏落盘'); norm_path=dirs['normalized']/'records.json'; norm_path.write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8'); log('清洗',f'结构化 {len(records)} 条 → {norm_path.name}'); report=engine.build_insight_report(records,comments or None,taxonomy=DEFAULT_TAXONOMY,candidate_angles=args.angles or args.keywords or ['通用'],relevance_terms=RELATED_TERMS); report_data=_report_dict(args.goal,report); rpt_path=dirs['reports']/'insight_report.json'; md_path=dirs['reports']/'insight_report.md'; _emit_report(dirs,report_data,rpt_path,md_path,reporter); reporter.set(videos=len(records),comments=len(comments),low_follower_hits=len(report.low_follower_hits),running=False); log('报告',f'已生成 {rpt_path.name} 与 {md_path.name}'); _archive_run(out_dir,_build_meta(args,mode,run_id,report,report_data,reporter,src)); log('归档',f'已归档本次运行到 history/{run_id}/'); log('完成',f'证据全部可回指 raw/ 原始文件。共采集 {len(raw_details)} 视频 / {len(comments)} 评论。'); return 0

def _extract_aweme_ids_from_search(resp:dict)->list[str]:
    out=[]
    def _id_of(it):
        if not isinstance(it,dict): return None
        aid=it.get('aweme_id') or it.get('aweme_id_str')
        if aid:return str(aid)
        ai=it.get('aweme_info')
        if isinstance(ai,dict):return str(ai.get('aweme_id') or ai.get('aweme_id_str') or '')
        return None
    data=resp.get('data') or {}; dd=data.get('data') if isinstance(data,dict) else None
    if isinstance(dd,list):
        for it in dd:
            aid=_id_of(it)
            if aid:out.append(aid)
    if not out:
        for key in ('aweme_list','video_list','list'):
            items=data.get(key) if isinstance(data,dict) else None
            if isinstance(items,list):
                for it in items:
                    aid=_id_of(it)
                    if aid:out.append(aid)
    seen=set();uniq=[]
    for x in out:
        if x and x not in seen:seen.add(x);uniq.append(x)
    return uniq

def _extract_comments(resp:dict)->list[dict]:
    data=resp.get('data') or {};comments=data.get('comments');return comments if isinstance(comments,list) else []

def _enrich_records_followers(dirs,api_key,platform,records,base_url):
    uids=list(dict.fromkeys([r.get('author_uid') for r in records if r.get('author_uid')]))
    if not uids:return 0
    fetched={}
    for i in range(0,len(uids),50):
        batch=uids[i:i+50]
        try:resp=fetch_one(api_key,'tikhub',platform,'user_batch_profile',{'sec_user_ids':','.join(batch)},base_url=base_url)
        except Exception as e:log('补查',f'批量用户请求失败：{e}');continue
        save_redacted(dirs,'batch_profile',f'b{i}',resp)
        for u in engine.extract_user_list(resp):
            uid=u.get('uid');fc=u.get('follower_count')
            if uid and fc is not None:fetched[str(uid)]=fc
    for r in records:
        uid=r.get('author_uid')
        if uid and str(uid) in fetched:r['follower_count']=fetched[str(uid)]
    return len(fetched)

def _report_dict(goal:str,report)->dict:return {'goal':goal,'generated_at':datetime.now(timezone.utc).isoformat(),'total_records':report.total_records,'top_by_engagement':report.top_by_engagement,'low_follower_hits':report.low_follower_hits,'pain_points':report.pain_points,'content_gaps':report.content_gaps,'four_perspective':report.four_perspective,'topic_ideas':report.topic_ideas,'relevance':report.relevance}

def _archive_run(out_dir:Path,meta:dict)->None:
    hist=out_dir/'history';hist.mkdir(parents=True,exist_ok=True);dest=hist/meta['run_id']
    if dest.exists():shutil.rmtree(dest)
    dest.mkdir(parents=True,exist_ok=True)
    for sub in ('raw','normalized','media','reports'):
        s=out_dir/sub
        if s.is_dir():shutil.copytree(s,dest/sub)
    st=out_dir/'_run_state.json'
    if st.exists():shutil.copy2(st,dest/'_run_state.json')
    (dest/'meta.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')

def _build_meta(args,mode,run_id,report,report_data,reporter,key_source)->dict:return {'run_id':run_id,'goal':args.goal,'mode':mode,'billboard_type':args.billboard_type if args.billboard else None,'generated_at':report_data.get('generated_at'),'total_records':report.total_records,'low_follower_hits':len(report.low_follower_hits),'estimated_cost_usd':reporter.metrics.get('estimated_cost_usd'),'key_source':key_source,'has_four_perspective':bool(report.four_perspective)}

def _render_markdown(r:dict)->str:
    lines=[f"# 选题调研报告：{r['goal']}",'',f"- 生成时间(UTC)：{r['generated_at']}",f"- 样本视频数：{r['total_records']}",'']
    if r['low_follower_hits']:
        lines+=['## 低粉爆款（小号高互动）','']
        for h in r['low_follower_hits'][:10]:lines.append(f"- @{h.get('author_name')}（粉丝 {h.get('follower_count')}） 互动 {h.get('digg_count')} → 互动/粉丝 {h.get('engagement_per_follower')}")
        lines.append('')
    if r['pain_points']:
        lines+=['## 痛点聚类（来自评论）','']
        for label,cnt in r['pain_points']['summary'].items():lines.append(f'- {label}：{cnt}')
        lines.append('')
    if r['content_gaps']:
        lines+=['## 选题空位（覆盖率越低越空白）','']
        for g in r['content_gaps'][:10]:lines.append(f"- {g['angle']}：覆盖 {g['coverage']} 视频，空位分 {g['gap_score']}")
        lines.append('')
    return '\n'.join(lines)

def main()->int:
    p=argparse.ArgumentParser(description='modular-research 流水线编排（SKILL 七步）'); p.add_argument('--goal',required=False,help='Legacy goal text; V2 requests use --request or structured convenience args');p.add_argument('--request',help='V2 ResearchRequest JSON path');p.add_argument('--topic',help='V2 research topic');p.add_argument('--platform',help='V2 platform, e.g. tiktok or douyin');p.add_argument('--market',help='V2 market/region, e.g. US, GB, CA');p.add_argument('--research-goal',action='append',default=[],help='V2 controlled research goal; repeat for multiple goals');p.add_argument('--reference-url',action='append',default=[],help='V2 reference content URL; repeat for multiple references');p.add_argument('--depth',choices=['quick','standard','deep'],default='standard',help='V2 default sampling depth');p.add_argument('--keywords',nargs='*',default=[]);p.add_argument('--videos-per-keyword',type=int,default=10);p.add_argument('--accounts-to-profile',type=int,default=20);p.add_argument('--comment-videos',type=int,default=5,help='取前 N 个视频的评论');p.add_argument('--video-ids',nargs='*',default=[],help='免费路径：已知视频ID（跳过付费搜索）');p.add_argument('--angles',nargs='*',default=[],help='候选选题角度，用于计算选题空位');p.add_argument('--out',default=DEFAULT_OUT);g=p.add_mutually_exclusive_group(required=False);g.add_argument('--only-free',action='store_true',help='免费路径：用 --video-ids 已知ID，不触发付费搜索');g.add_argument('--with-search',action='store_true',help='付费全链路：先 video_search 发现视频池（需付费余额）');g.add_argument('--billboard',action='store_true',help='榜单发现：用低粉爆款榜直接发现视频（免关键词、免费额度）');p.add_argument('--demo',action='store_true',help='离线演练：叠加在以上模式上，用合成数据走完整编排 I/O（不联网不花钱）');p.add_argument('--billboard-type',default='billboard_low_fan',choices=['billboard_low_fan','billboard_hot_video','billboard_topic','billboard_challenge'],help='榜单类型（默认 billboard_low_fan 低粉爆款榜）');p.add_argument('--plan-only',action='store_true',help='只打印费用预览，不发任何请求');p.add_argument('--yes',action='store_true',help='显式确认：允许发起付费请求');p.add_argument('--max-budget-usd',type=float,default=None,help='V2 真实执行的硬预算上限；低于计划 max cost 时拒绝执行');p.add_argument('--download-media',action='store_true',help='V2 创意研究：显式允许下载 shortlist 视频并提取关键帧/OCR；默认仅准备分析请求');p.add_argument('--media-limit',type=int,default=None,help='V2 创意研究：覆盖 Profile 的媒体 shortlist 上限');p.add_argument('--base-url',default=core.DEFAULT_BASE_URL,help='API 域名，默认 api.tikhub.dev（国内加速）；海外用 https://api.tikhub.io');p.add_argument('--config',default=str(DEFAULT_CONFIG),help='密钥配置文件路径（JSON，含 api_key 字段）；默认 ../config.json');args=p.parse_args()
    try:v2_request=load_research_request_from_args(args)
    except (ValueError,OSError,json.JSONDecodeError) as exc:print(f'ResearchRequest 无效: {exc}');return 2
    if v2_request is not None:
        missing=v2_request.validate_material_fields()
        if missing:print(json.dumps({'execution_status':'NEEDS_INPUT','request':v2_request.to_dict(),'missing_material_fields':missing},ensure_ascii=False,indent=2));return 2
        try:stage_plan=build_v2_stage_plan(v2_request)
        except ValueError as exc:print(f'V2 计划生成失败: {exc}');return 2
        print(json.dumps(stage_plan.to_dict(),ensure_ascii=False,indent=2))
        if args.plan_only:return 0
        ok,reason=validate_v2_execution_gate(stage_plan,yes=args.yes,max_budget_usd=args.max_budget_usd)
        if not ok:print(reason);return 2
        api_key,key_source=core.resolve_api_key(config_path=args.config)
        if not api_key:print('未找到 TikHub API Key；请使用 TIKHUB_API_KEY、config.json 或系统 Keychain。');return 2
        print(f'API Key source: {key_source}');executor=ResearchExecutorV2();result=executor.execute(stage_plan,api_key=api_key,base_url=args.base_url,output_root=Path(args.out),download_media=args.download_media,media_limit=args.media_limit);print(json.dumps(result.to_dict(),ensure_ascii=False,indent=2));return 0 if result.status=='completed' else 1
    if not args.goal:print('Legacy 模式需要 --goal；V2 请使用 --request 或 --topic/--platform/--research-goal。');return 2
    if not (args.demo or args.only_free or args.with_search or args.billboard):print('请至少选择一种模式：--demo / --only-free / --with-search / --billboard');return 2
    if args.only_free and not args.video_ids and not args.plan_only and not args.demo:print('提示：--only-free 未提供 --video-ids，且无 API Key 时无法真实拉取；请传 --video-ids 或先 export TIKHUB_API_KEY。');return 2
    return run(args)
if __name__=='__main__':raise SystemExit(main())

"""Stage-based planner for Modular Research V2.

Transforms a canonical ResearchRequest into an auditable sequence of API and
local stages. Planning performs no network I/O.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from datetime import datetime, timezone
from typing import Any
import api_research_core as core
from endpoint_registry import EndpointRegistry
from profile_loader import load_profiles
from profile_resolver import resolve_profile
from research_request import ResearchRequest
_DEPTH = {'quick': {'keyword_limit': 3, 'organic_variants': 2, 'candidate_limit': 50, 'creator_limit': 5, 'comment_video_limit': 5, 'comment_pages': 1, 'ads_limit': 10, 'ad_deep_limit': 3, 'search_insight_enrich_limit': 5, 'top_contents_detail_limit': 5}, 'standard': {'keyword_limit': 8, 'organic_variants': 4, 'candidate_limit': 300, 'creator_limit': 20, 'comment_video_limit': 20, 'comment_pages': 3, 'ads_limit': 30, 'ad_deep_limit': 10, 'search_insight_enrich_limit': 10, 'top_contents_detail_limit': 20}, 'deep': {'keyword_limit': 20, 'organic_variants': 4, 'candidate_limit': 800, 'creator_limit': 50, 'comment_video_limit': 50, 'comment_pages': 5, 'ads_limit': 80, 'ad_deep_limit': 25, 'search_insight_enrich_limit': 20, 'top_contents_detail_limit': 40}}
DEMAND_GOALS = {'trend_discovery', 'content_opportunities'}
CREATOR_GOALS = {'creative_patterns', 'hooks', 'selling_angles', 'formats', 'creator_analysis', 'competitor_analysis'}
ADS_GOALS = {'ads_analysis', 'retention_analysis'}
VOC_GOALS = {'voc', 'purchase_objections', 'product_validation'}
TOP_CONTENT_GOALS = {'creative_patterns', 'hooks', 'selling_angles', 'formats'}
VIDEO_UNDERSTANDING_GOALS = TOP_CONTENT_GOALS | ADS_GOALS | {'competitor_analysis'}

@dataclass
class PlanTask:
    capability: str
    endpoint: str
    method: str
    request_location: str
    mode: str = 'static'
    static_calls: list[dict[str, Any]] = field(default_factory=list)
    variants: list[dict[str, Any]] = field(default_factory=lambda: [{}])
    max_items: int = 0
    pages_per_item: int = 1
    expected_requests: int = 0
    max_requests: int = 0
    unit_price_usd: str | None = None
    price_source: str = 'unknown'
    is_endpoint_exact: bool = False
    dependencies: list[str] = field(default_factory=list)
    def to_dict(self) -> dict[str, Any]: return asdict(self)

@dataclass
class PlanStage:
    name: str
    tasks: list[PlanTask] = field(default_factory=list)
    local_only: bool = False
    @property
    def expected_requests(self) -> int: return 0 if self.local_only else sum(t.expected_requests for t in self.tasks)
    @property
    def max_requests(self) -> int: return 0 if self.local_only else sum(t.max_requests for t in self.tasks)
    def to_dict(self) -> dict[str, Any]: return {'name':self.name,'local_only':self.local_only,'expected_requests':self.expected_requests,'max_requests':self.max_requests,'tasks':[task.to_dict() for task in self.tasks]}

@dataclass
class StageResearchPlan:
    request: ResearchRequest
    profile_id: str
    provider: str
    keywords: list[str]
    stages: list[PlanStage]
    assumptions: list[str]
    pricing_confidence: str
    @property
    def total_expected_requests(self) -> int: return sum(stage.expected_requests for stage in self.stages)
    @property
    def total_max_requests(self) -> int: return sum(stage.max_requests for stage in self.stages)
    @staticmethod
    def _task_cost(task: PlanTask,count: int) -> float:
        if count<=0 or not task.unit_price_usd: return 0.0
        return float(core.estimate_cost(count,Decimal(task.unit_price_usd))['estimated_total_usd'])
    @property
    def expected_cost_usd(self)->float:return round(sum(self._task_cost(t,t.expected_requests) for s in self.stages for t in s.tasks),6)
    @property
    def max_cost_usd(self)->float:return round(sum(self._task_cost(t,t.max_requests) for s in self.stages for t in s.tasks),6)
    def to_dict(self)->dict[str,Any]: return {'request':self.request.to_dict(),'profile_id':self.profile_id,'provider':self.provider,'keywords':list(self.keywords),'stages':[stage.to_dict() for stage in self.stages],'budget':{'total_expected_requests':self.total_expected_requests,'total_max_requests':self.total_max_requests,'expected_cost_usd':self.expected_cost_usd,'max_cost_usd':self.max_cost_usd,'pricing_confidence':self.pricing_confidence},'assumptions':list(self.assumptions)}

def map_tiktok_publish_time(days:int|None)->int:
    days=int(days or 90)
    if days<=1:return 1
    if days<=7:return 7
    if days<=30:return 30
    if days<=90:return 90
    return 180

def map_ads_period(days:int|None)->int:
    days=int(days or 90)
    if days<=7:return 7
    if days<=30:return 30
    if days<=120:return 120
    return 180

def _keyword_universe(request:ResearchRequest,limit:int)->list[str]:
    values=[request.topic,*request.seed_keywords]; out=[]; seen=set()
    for raw in values:
        value=str(raw).strip(); key=value.casefold()
        if value and key not in seen: seen.add(key); out.append(value)
        if len(out)>=limit:break
    return out

def _make_task(registry:EndpointRegistry,provider:str,capability:str,*,mode:str='static',static_calls:list[dict[str,Any]]|None=None,variants:list[dict[str,Any]]|None=None,max_items:int=0,pages_per_item:int=1,expected_requests:int|None=None,max_requests:int|None=None,dependencies:list[str]|None=None)->PlanTask:
    entry=registry.get(provider,'tiktok',capability); pricing=registry.get_pricing(provider,'tiktok',capability); calls=list(static_calls or []); var=list(variants or [{}])
    if expected_requests is None: expected_requests=len(calls) if mode=='static' else max_items*len(var)
    if max_requests is None:max_requests=expected_requests
    return PlanTask(capability=capability,endpoint=entry['path'],method=entry['method'],request_location=entry.get('request_location','query' if entry['method']=='GET' else 'json'),mode=mode,static_calls=calls,variants=var,max_items=max_items,pages_per_item=pages_per_item,expected_requests=int(expected_requests),max_requests=int(max_requests),unit_price_usd=pricing['unit_price_usd'],price_source=pricing['price_source'],is_endpoint_exact=bool(pricing['is_endpoint_exact']),dependencies=list(dependencies or []))
def _scope_on(request:ResearchRequest,key:str)->bool:return request.content_scope.get(key) is True

def build_stage_plan(request:ResearchRequest,profile:dict[str,Any]|None=None,registry:EndpointRegistry|None=None)->StageResearchPlan:
    if request.platform!='tiktok':raise ValueError('Phase 2 stage planner currently supports platform=tiktok')
    missing=request.validate_material_fields()
    if missing:raise ValueError(f'ResearchRequest missing material fields: {missing}')
    reg=registry or EndpointRegistry(); profiles=load_profiles()
    if profile is None:
        resolution=resolve_profile(request,profiles); profile=profiles[resolution.profile_id]
    profile_id=str(profile['id']); provider=str(profile.get('default_provider') or 'tikhub'); preset=_DEPTH[request.depth]; keywords=_keyword_universe(request,preset['keyword_limit']); goals=set(request.research_goals); days=int(request.time_range.get('days') or 90); market=request.market or 'US'; language=request.language or ('en' if market in {'US','GB','CA','AU'} else None); need_demand=bool(goals&DEMAND_GOALS) or _scope_on(request,'trends'); need_creator=bool(goals&CREATOR_GOALS) or _scope_on(request,'creators'); need_ads=bool(goals&ADS_GOALS) or _scope_on(request,'ads'); need_voc=bool(goals&VOC_GOALS) or _scope_on(request,'comments'); stages=[]
    if need_demand:
        demand_calls=[]
        for tab in ('content_gap','all'):
            params={'offset':0,'limit':20,'tab':tab,'creator_source':'general_search','force_refresh':False}
            if language:params['language_filters']=language
            demand_calls.append(params)
        enrich_limit=preset['search_insight_enrich_limit']; demand_tasks=[_make_task(reg,provider,'creator_search_insights',static_calls=demand_calls),_make_task(reg,provider,'creator_search_insights_trend',mode='per_search_insight',variants=[{'from_tab_path':'TRENDING,TOPICS','query_analysis_required':True}],max_items=enrich_limit,dependencies=['creator_search_insights']),_make_task(reg,provider,'creator_search_insights_videos',mode='per_search_insight',variants=[{'offset':0,'count':20}],max_items=enrich_limit,dependencies=['creator_search_insights'])]
        if request.depth!='quick':demand_tasks.append(_make_task(reg,provider,'creator_search_insights_detail',mode='per_search_insight',variants=[{'time_range':'past_90_days'}],max_items=enrich_limit,dependencies=['creator_search_insights']))
        stages.append(PlanStage('DEMAND',demand_tasks))
    publish=map_tiktok_publish_time(days); combos=[(0,publish),(1,publish)]
    if preset['organic_variants']>=4:combos.extend([(0,180),(1,180)])
    combos=list(dict.fromkeys(combos)); organic_calls=[]
    for keyword in keywords:
        for sort_type,publish_time in combos:organic_calls.append({'keyword':keyword,'offset':0,'count':20,'sort_type':sort_type,'publish_time':publish_time,'region':market})
    organic_tasks=[_make_task(reg,provider,'video_search',static_calls=organic_calls)]
    if goals&TOP_CONTENT_GOALS:
        period_end=int(datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0).timestamp()); period_dimension=5 if days>30 else 1; top_calls=[{'period_end_timestamp':period_end,'period_dimension':period_dimension,'country_code':market,'order_by_metric':metric,'organic_only':True,'page':1,'limit':min(100,preset['candidate_limit'])} for metric in (1,2,3)]; organic_tasks.append(_make_task(reg,provider,'top_contents_list',static_calls=top_calls)); organic_tasks.append(_make_task(reg,provider,'top_contents_item_detail',mode='per_top_content',variants=[{'period_end_timestamp':period_end,'period_dimension':period_dimension,'country_code':market}],max_items=preset['top_contents_detail_limit'],dependencies=['top_contents_list']))
    stages.append(PlanStage('ORGANIC_DISCOVERY',organic_tasks)); stages.append(PlanStage('CHEAP_RANKING',local_only=True))
    if need_creator:
        creator_variants=[{'max_cursor':0,'count':20,'sort_type':1}]
        if request.depth!='quick':creator_variants=[{'max_cursor':0,'count':20,'sort_type':0},{'max_cursor':0,'count':20,'sort_type':1}]
        creator_limit=preset['creator_limit']; stages.append(PlanStage('CREATOR_CONTEXT',[_make_task(reg,provider,'creator_posts',mode='per_creator',variants=creator_variants,max_items=creator_limit,dependencies=['ORGANIC_DISCOVERY']),_make_task(reg,provider,'video_metrics',mode='per_video',max_items=min(preset['candidate_limit'],preset['creator_limit']*2),dependencies=['ORGANIC_DISCOVERY'])]))
    if need_ads:
        ad_period=map_ads_period(days); ad_calls=[]
        for keyword in keywords:
            body={'keyword':keyword,'objective':0,'like':0,'period':ad_period,'page':1,'limit':min(50,preset['ads_limit']),'order_by':'for_you','country_code':market,'ad_format':0}
            if language:body['ad_language']=language
            ad_calls.append(body)
        stages.append(PlanStage('ADS_DISCOVERY',[_make_task(reg,provider,'ads_search',static_calls=ad_calls),_make_task(reg,provider,'top_ads_spotlight',static_calls=[{'page':1,'limit':min(20,preset['ads_limit'])}])]))
    if need_voc:
        limit=preset['comment_video_limit']; pages=preset['comment_pages']; stages.append(PlanStage('VOC',[_make_task(reg,provider,'video_comments',mode='per_video',variants=[{'cursor':0,'count':20}],max_items=limit,pages_per_item=pages,expected_requests=limit,max_requests=limit*pages,dependencies=['ORGANIC_DISCOVERY'])]))
    if need_ads:
        deep=preset['ad_deep_limit']; stages.append(PlanStage('CREATIVE_ANALYSIS',[_make_task(reg,provider,'ads_detail',mode='per_ad',max_items=deep,dependencies=['ADS_DISCOVERY']),_make_task(reg,provider,'ad_percentile',mode='per_ad',max_items=deep,variants=[{'metric':'ctr_percentile','period_type':180}],dependencies=['ADS_DISCOVERY']),_make_task(reg,provider,'ad_keyframe_analysis',mode='per_ad',max_items=deep,variants=[{'metric':'retain_ctr'},{'metric':'retain_cvr'}],dependencies=['ADS_DISCOVERY']),_make_task(reg,provider,'ad_interactive_analysis',mode='per_ad',max_items=deep,variants=[{'metric_type':'remain','period_type':180}],dependencies=['ADS_DISCOVERY'])]))
    if goals&VIDEO_UNDERSTANDING_GOALS:stages.append(PlanStage('VIDEO_UNDERSTANDING',local_only=True))
    for name in ('PATTERN_MINING','FINDINGS','HYPOTHESES','BRIEFS'):stages.append(PlanStage(name,local_only=True))
    sources={task.price_source for stage in stages for task in stage.tasks if task.expected_requests or task.max_requests}
    pricing_confidence='exact' if sources=={'endpoint_explicit'} else ('mixed' if 'unknown' in sources and len(sources)>1 else ('mixed' if 'endpoint_explicit' in sources and 'provider_default' in sources else 'estimated'))
    assumptions=['TikHub 未提供端点级单价时按 provider default $0.001/成功请求估算；真实执行前应使用 provider 报价能力复核。','成本按计划请求上限估算，不包含失败请求重试；TikHub 非 200 响应是否计费以 provider 当前规则为准。',f'未指定 time_range.days 时默认使用 90 天；当前映射为 TikTok publish_time={publish}、Ads period={map_ads_period(days)}。','动态阶段的实际请求数取决于上游能提取到的 search insight/video/creator/top-content/ad 标识，可能低于计划上限。']
    return StageResearchPlan(request=request,profile_id=profile_id,provider=provider,keywords=keywords,stages=stages,assumptions=assumptions,pricing_confidence=pricing_confidence)

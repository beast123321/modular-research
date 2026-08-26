"""Legacy-compatible planning layer backed by the machine EndpointRegistry."""
from __future__ import annotations
from dataclasses import dataclass,field
from decimal import Decimal
from typing import Optional
import api_research_core as core
from endpoint_registry import EndpointRegistry
_ENDPOINT_REGISTRY=EndpointRegistry(); DEFAULT_PROVIDER='tikhub'; DEFAULT_PLATFORM='douyin'
COLLECTION_ORDER=['user_profile','user_batch_profile','video_detail','video_comments','video_list','billboard_low_fan','billboard_hot_video','billboard_topic','billboard_challenge','video_search']
@dataclass
class CollectionStep:
    data_need:str; endpoint:str; method:str; count:int; unit_price:Decimal; free_credit:bool; estimate:dict
    @property
    def is_paid_only(self)->bool: return not self.free_credit
@dataclass
class ResearchPlan:
    goal:str; provider:str; platform:str; steps:list[CollectionStep]=field(default_factory=list); notes:list[str]=field(default_factory=list)
    @property
    def total_requests(self)->int:return sum(s.count for s in self.steps)
    @property
    def total_cost_usd(self)->float:return sum((s.estimate.get('estimated_total_usd',0.0) for s in self.steps),0.0)
    @property
    def blocked_by_paid(self)->list[str]:return [s.data_need for s in self.steps if s.is_paid_only]
    def summary(self)->str:
        lines=[f'研究目标: {self.goal}',f'数据源: {self.provider}/{self.platform}',f'总请求数: {self.total_requests}',f'预估总费用: ${self.total_cost_usd:.4f} USD']
        if self.blocked_by_paid: lines.append(f"需付费额度的环节: {', '.join(self.blocked_by_paid)} (免费额度不可用，需充值)")
        for s in self.steps: lines.append(f"  - {s.data_need}: {s.count} 次 × {s.unit_price} USD ({'免费' if s.free_credit else '付费'}) ≈ ${s.estimate.get('estimated_total_usd',0):.4f}")
        lines += [f'注: {n}' for n in self.notes]; return '\n'.join(lines)
def resolve_endpoint(provider:str,platform:str,data_need:str)->dict:
    entry=_ENDPOINT_REGISTRY.get(provider,platform,data_need); price=entry.get('unit_price_usd')
    if price is None: raise ValueError(f'端点尚无可用于成本计划的单价: {provider}/{platform}/{data_need}')
    out=dict(entry); out['unit_price']=Decimal(str(price)); notes=out.get('notes') or []
    if notes and 'verify' not in out: out['verify']='; '.join(str(x) for x in notes)
    return out
def decompose_task(goal:str,*,keywords:list[str],videos_per_keyword:int=10,search_pages_per_keyword:int=1,comment_pages_per_video:int=1,accounts_to_profile:int=20,provider:str=DEFAULT_PROVIDER,platform:str=DEFAULT_PLATFORM,only_free:bool=False,billboard:bool=False,billboard_type:str='billboard_low_fan')->ResearchPlan:
    plan=ResearchPlan(goal=goal,provider=provider,platform=platform)
    if keywords and not only_free:
        spec=resolve_endpoint(provider,platform,'video_search'); n=len(keywords)*search_pages_per_keyword; plan.steps.append(CollectionStep('video_search',spec['path'],spec['method'],n,spec['unit_price'],spec['free_credit'],core.estimate_cost(n,spec['unit_price'])))
    spec=resolve_endpoint(provider,platform,'video_detail'); n_videos=len(keywords)*videos_per_keyword if keywords else videos_per_keyword; plan.steps.append(CollectionStep('video_detail',spec['path'],spec['method'],n_videos,spec['unit_price'],spec['free_credit'],core.estimate_cost(n_videos,spec['unit_price'])))
    spec=resolve_endpoint(provider,platform,'video_comments'); n_comments=int(n_videos*.6)*comment_pages_per_video; plan.steps.append(CollectionStep('video_comments',spec['path'],spec['method'],n_comments,spec['unit_price'],spec['free_credit'],core.estimate_cost(n_comments,spec['unit_price'])))
    spec=resolve_endpoint(provider,platform,'user_profile'); n_accounts=min(accounts_to_profile,max(n_videos//4,1)); plan.steps.append(CollectionStep('user_profile',spec['path'],spec['method'],n_accounts,spec['unit_price'],spec['free_credit'],core.estimate_cost(n_accounts,spec['unit_price'])))
    if only_free: plan.notes.append('已按 only_free=True 生成：未包含需付费的搜索环节，仅用已知视频ID做验证/分析。')
    elif billboard:
        spec=resolve_endpoint(provider,platform,billboard_type); plan.steps.append(CollectionStep(billboard_type,spec['path'],spec['method'],1,spec['unit_price'],spec['free_credit'],core.estimate_cost(1,spec['unit_price']))); spec2=resolve_endpoint(provider,platform,'user_batch_profile'); plan.steps.append(CollectionStep('user_batch_profile',spec2['path'],spec2['method'],1,spec2['unit_price'],spec2['free_credit'],core.estimate_cost(1,spec2['unit_price']))); plan.notes.append('榜单模式：用「低粉爆款榜」直接发现视频池（免关键词），批量补查作者粉丝数用于低粉爆款判定。')
    if plan.blocked_by_paid: plan.notes.append('搜索端点拒绝免费额度，需先充值才能发现视频池；否则只能用已知视频ID走 detail/comments/profile。')
    return plan
DEFAULT_SAMPLE_RULES={'video_detail':{'required_paths':['data.aweme_detail.aweme_id','data.aweme_detail.author.follower_count','data.aweme_detail.statistics.digg_count','data.aweme_detail.desc'],'error_codes':['code']},'video_comments':{'required_paths':['data.comments'],'error_codes':['code']},'user_profile':{'required_paths':['data.user.follower_count','data.user.nickname'],'error_codes':['code']},'video_search':{'required_paths':['data'],'error_codes':['code']}}
def _get_path(obj,dotted:str):
    cur=obj
    for part in dotted.split('.'):
        if part.endswith('[*]'):
            key=part[:-3]; cur=cur.get(key) if isinstance(cur,dict) else None
            if not isinstance(cur,list) or not cur:return None
            cur=cur[0]
        else:cur=cur.get(part) if isinstance(cur,dict) else None
        if cur is None:return None
    return cur
def validate_sample(response:dict,data_need:str,rules:Optional[dict]=None)->tuple[bool,list[str]]:
    rules=rules or DEFAULT_SAMPLE_RULES; spec=rules.get(data_need,{}); reasons=[]
    for path in spec.get('required_paths',[]):
        if _get_path(response,path) is None: reasons.append(f'缺少必要字段: {path}')
    if _get_path(response,'data') is None and data_need!='video_search': reasons.append('响应缺少 data 顶层结构')
    return len(reasons)==0,reasons
def collection_order()->list[str]:return list(COLLECTION_ORDER)

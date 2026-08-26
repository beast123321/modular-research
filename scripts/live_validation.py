"""Bounded TikHub live-validation harness.

This module validates provider contracts; it is not a research workflow. It is
provider-neutral at the semantic layer and never turns live probe results into
Insights or Hypotheses.
"""
from __future__ import annotations
from dataclasses import dataclass
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import socket
from typing import Any, Callable
from urllib.parse import urlparse
import api_research_core as core
from endpoint_registry import EndpointRegistry
from normalizers.tiktok import normalize_capability
from research_executor_v2 import extract_ad_ids, extract_creator_ids, extract_search_insights, extract_top_content_ids, extract_video_ids
@dataclass(frozen=True)
class ProbeSpec:
    capability:str; payload:dict[str,Any]
def summarize_shape(value:Any,*,depth:int=0,max_depth:int=5)->dict[str,Any]:
    if depth>=max_depth:return {'type':type(value).__name__}
    if isinstance(value,dict):return {'type':'dict','keys':sorted(str(k) for k in value.keys()),'children':{str(k):summarize_shape(v,depth=depth+1,max_depth=max_depth) for k,v in value.items()}}
    if isinstance(value,list):
        result={'type':'list','length':len(value)}
        if value:result['item_shape']=summarize_shape(value[0],depth=depth+1,max_depth=max_depth)
        return result
    if value is None:return {'type':'null'}
    return {'type':type(value).__name__}
def build_default_probes(*,topic:str,market:str='US')->list[ProbeSpec]:
    period_end=int(datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0).timestamp());return [ProbeSpec('creator_search_insights',{'offset':0,'limit':5,'tab':'content_gap','creator_source':'general_search','force_refresh':False,'language_filters':'en'}),ProbeSpec('video_search',{'keyword':topic,'offset':0,'count':3,'sort_type':0,'publish_time':30,'region':market}),ProbeSpec('top_contents_list',{'period_end_timestamp':period_end,'period_dimension':1,'country_code':market,'order_by_metric':1,'organic_only':True,'page':1,'limit':3}),ProbeSpec('ads_search',{'keyword':topic,'period':30,'page':1,'limit':3,'country_code':market,'ad_language':'en'}),ProbeSpec('top_ads_spotlight',{'page':1,'limit':3})]
def _host_resolves(base_url:str)->tuple[bool,str|None]:
    host=urlparse(base_url).hostname
    if not host:return False,'invalid_base_url'
    try:socket.getaddrinfo(host,None)
    except OSError as exc:return False,f'dns:{type(exc).__name__}'
    return True,None
class LiveValidationRunner:
    def __init__(self,transport:Callable[...,Any]|None=None,registry:EndpointRegistry|None=None):self.transport=transport or core.request_json;self.registry=registry or EndpointRegistry()
    def run(self,probes:list[ProbeSpec],*,api_key:str,base_url:str,output_dir:Path,max_calls:int,max_budget_usd:float,unit_price_usd:float=.001,skip_dns_check:bool=False)->dict[str,Any]:
        output_dir=Path(output_dir);raw_dir=output_dir/'raw';raw_dir.mkdir(parents=True,exist_ok=True);max_calls=max(0,int(max_calls));estimated=round(max_calls*float(unit_price_usd),6);base_report={'schema_version':'1.0','generated_at':datetime.now(timezone.utc).isoformat(),'initial_probes':len(probes),'call_ceiling':max_calls,'estimated_max_cost_usd':estimated,'unit_price_basis_usd':float(unit_price_usd),'results':[]}
        if estimated>float(max_budget_usd):base_report.update({'status':'BLOCKED_BUDGET','calls_attempted':0,'calls_succeeded':0,'calls_failed':0});(output_dir/'live-validation.json').write_text(json.dumps(base_report,ensure_ascii=False,indent=2),encoding='utf-8');return base_report
        if not skip_dns_check:
            ok,reason=_host_resolves(base_url)
            if not ok:base_report.update({'status':'BLOCKED_ENVIRONMENT','block_reason':reason,'calls_attempted':0,'calls_succeeded':0,'calls_failed':0});(output_dir/'live-validation.json').write_text(json.dumps(base_report,ensure_ascii=False,indent=2),encoding='utf-8');return base_report
        queue=list(probes);queued_caps={p.capability for p in queue};attempted=succeeded=failed=0;results=[]
        def enqueue(capability,payload):
            if capability in queued_caps or len(queue)>=max_calls*3:return
            queued_caps.add(capability);queue.append(ProbeSpec(capability,payload))
        index=0
        while index<len(queue) and attempted<max_calls:
            probe=queue[index];index+=1;entry=self.registry.get('tikhub','tiktok',probe.capability);attempted+=1;kwargs={'base_url':base_url,'api_key':api_key,'method':entry['method'],'path':entry['path'],'params':None,'body':None};location=entry.get('request_location','query' if entry['method']=='GET' else 'json');kwargs['body' if location=='json' else 'params']=dict(probe.payload)
            try:
                response=self.transport(**kwargs);safe=core.redact_payload(response);(raw_dir/f'{attempted:02d}_{probe.capability}.json').write_text(json.dumps(safe,ensure_ascii=False,indent=2),encoding='utf-8');provider_code=response.get('code') if isinstance(response,dict) else None
                if provider_code not in (None,200):failed+=1;results.append({'capability':probe.capability,'method':entry['method'],'request_location':location,'path':entry['path'],'provider_code':provider_code,'shape':summarize_shape(response),'status':'error','error_class':'provider'});continue
                succeeded+=1;bundle=normalize_capability(probe.capability,safe,raw_evidence_id=f'live:{attempted:02d}',request_payload=probe.payload);results.append({'capability':probe.capability,'method':entry['method'],'request_location':location,'path':entry['path'],'provider_code':provider_code,'shape':summarize_shape(response),'normalizer_counts':{k:len(v) for k,v in bundle.items()},'status':'ok'})
                if probe.capability=='video_search':
                    vids=extract_video_ids(response);creators=extract_creator_ids(response)
                    if vids:
                        vid=vids[0];enqueue('video_detail',{'aweme_id':vid,'region':probe.payload.get('region','US')});enqueue('video_metrics',{'item_id':vid});enqueue('video_comments',{'aweme_id':vid,'cursor':0,'count':3})
                    if creators:
                        c=creators[0];cp={'max_cursor':0,'count':3,'sort_type':0}
                        if c.get('sec_user_id'):cp['sec_user_id']=c['sec_user_id']
                        elif c.get('unique_id'):cp['unique_id']=c['unique_id']
                        enqueue('creator_posts',cp)
                elif probe.capability=='creator_search_insights':
                    rows=extract_search_insights(response)
                    if rows:
                        row=rows[0];qid=row.get('query_id');kw=row.get('keyword')
                        if qid:enqueue('creator_search_insights_trend',{'query_id_str':qid,'from_tab_path':'TRENDING,TOPICS','query_analysis_required':True})
                        if kw:enqueue('creator_search_insights_videos',{'keyword':kw,'offset':0,'count':3})
                elif probe.capability in {'ads_search','top_ads_spotlight'}:
                    ids=extract_ad_ids(response)
                    if ids:
                        aid=ids[0];enqueue('ads_detail',{'ads_id':aid});enqueue('ad_percentile',{'material_id':aid,'metric':'ctr_percentile','period_type':180});enqueue('ad_keyframe_analysis',{'material_id':aid,'metric':'retain_ctr'});enqueue('ad_interactive_analysis',{'material_id':aid,'metric_type':'remain','period_type':180})
                elif probe.capability=='top_contents_list':
                    ids=extract_top_content_ids(response)
                    if ids:
                        payload={'item_id':ids[0],'country_code':probe.payload.get('country_code','US')}
                        for k in ('period_end_timestamp','period_dimension'):
                            if k in probe.payload:payload[k]=probe.payload[k]
                        enqueue('top_contents_item_detail',payload)
            except Exception as exc:failed+=1;results.append({'capability':probe.capability,'method':entry['method'],'request_location':location,'path':entry['path'],'status':'error','error_class':'transport','error_type':type(exc).__name__})
        base_report.update({'status':'COMPLETED' if failed==0 else 'COMPLETED_WITH_ERRORS','calls_attempted':attempted,'calls_succeeded':succeeded,'calls_failed':failed,'results':results});(output_dir/'live-validation.json').write_text(json.dumps(base_report,ensure_ascii=False,indent=2),encoding='utf-8');return base_report
def main()->int:
    parser=argparse.ArgumentParser(description='Bounded TikHub live contract validation');parser.add_argument('--topic',required=True);parser.add_argument('--market',default='US');parser.add_argument('--max-calls',type=int,default=15);parser.add_argument('--max-budget-usd',type=float);parser.add_argument('--execute',action='store_true');parser.add_argument('--yes',action='store_true');parser.add_argument('--base-url',default=core.DEFAULT_BASE_URL);parser.add_argument('--config',default=str(Path(__file__).resolve().parent.parent/'config.json'));parser.add_argument('--out',default='live-validation-run');args=parser.parse_args();probes=build_default_probes(topic=args.topic,market=args.market);unit_price=.001;plan={'execution_status':'PLAN_ONLY' if not args.execute else 'READY','topic':args.topic,'market':args.market,'initial_capabilities':[p.capability for p in probes],'call_ceiling':args.max_calls,'estimated_max_cost_usd':round(args.max_calls*unit_price,6),'pricing_basis':'provider_default'}
    if not args.execute:print(json.dumps(plan,ensure_ascii=False,indent=2));return 0
    if not args.yes:print('真实 live validation 需要显式 --yes。');return 2
    if args.max_budget_usd is None:print('真实 live validation 需要 --max-budget-usd。');return 2
    api_key,source=core.resolve_api_key(config_path=args.config)
    if not api_key:print('未找到 TikHub API Key；请使用 TIKHUB_API_KEY、config.json 或系统 Keychain。');return 2
    result=LiveValidationRunner().run(probes,api_key=api_key,base_url=args.base_url,output_dir=Path(args.out),max_calls=args.max_calls,max_budget_usd=args.max_budget_usd,unit_price_usd=unit_price);public=dict(result);public['api_key_source']=source;print(json.dumps(public,ensure_ascii=False,indent=2));return 0 if result['status'] in {'COMPLETED','COMPLETED_WITH_ERRORS'} else 2
if __name__=='__main__':raise SystemExit(main())

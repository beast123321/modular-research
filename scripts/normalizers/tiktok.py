"""TikTok/TikHub response normalization.

This module deliberately extracts only stable evidence fields. It does not
produce observations, insights, hypotheses, scores, or business conclusions.
"""
from __future__ import annotations
import json
from typing import Any

def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values(): yield from _walk(child)
    elif isinstance(value, list):
        for child in value: yield from _walk(child)
def _first(mapping: dict[str, Any] | None, *keys: str) -> Any:
    if not isinstance(mapping, dict): return None
    for key in keys:
        value=mapping.get(key)
        if value not in (None,''): return value
    return None
def _as_text(value: Any) -> str | None:return None if value in (None,'') else str(value)
def _as_int(value: Any) -> int | None:
    if value in (None,''): return None
    try:return int(float(value))
    except (TypeError,ValueError):return None
def _duration_seconds(value: Any) -> float | None:
    if value in (None,''):return None
    try:number=float(value)
    except (TypeError,ValueError):return None
    return round(number/1000.0,3) if number>300 else round(number,3)
def _url(value: Any) -> str | None:
    if isinstance(value,str) and value:return value
    if isinstance(value,dict):
        for key in ('url_list','urlList','urls'):
            urls=value.get(key)
            if isinstance(urls,list) and urls:return _as_text(urls[0])
        for key in ('url','src','uri'):
            if value.get(key):return _as_text(value[key])
    if isinstance(value,list) and value:return _url(value[0])
    return None
def _empty_bundle():return {'videos':[],'video_snapshots':[],'creators':[],'comments':[],'ads':[],'ad_timeseries':[],'search_insights':[],'discoveries':[]}
def _video_candidates(payload: Any):
    for node in _walk(payload):
        if not isinstance(node,dict):continue
        vid=_first(node,'aweme_id','item_id')
        if vid in (None,''):continue
        if not any(k in node for k in ('desc','title','video','video_info','statistics','author','create_time')):continue
        yield node
def _creator_from_author(author,raw_evidence_id):
    uid=_as_text(_first(author,'uid','id','user_id')); sec=_as_text(_first(author,'sec_uid','sec_user_id')); unique=_as_text(_first(author,'unique_id','uniqueId')); creator_id=uid or sec or unique
    if not creator_id:return None
    stats=author.get('stats') if isinstance(author.get('stats'),dict) else {}
    return {'creator_id':creator_id,'sec_user_id':sec,'unique_id':unique,'nickname':_as_text(_first(author,'nickname','nick_name')),'bio':_as_text(_first(author,'signature','bio')),'region':_as_text(_first(author,'region','country')),'verified':1 if bool(_first(author,'verified','is_verified')) else 0,'followers':_as_int(_first(author,'follower_count','followers','followerCount') or _first(stats,'followerCount','followers')),'following':_as_int(_first(author,'following_count','following') or _first(stats,'followingCount','following')),'total_likes':_as_int(_first(author,'total_favorited','total_likes') or _first(stats,'heartCount','diggCount')),'video_count':_as_int(_first(author,'aweme_count','video_count') or _first(stats,'videoCount')),'raw_evidence_id':raw_evidence_id}
def _normalize_videos(payload,raw_evidence_id,request_payload):
    out=_empty_bundle(); seen_videos=set(); seen_creators=set()
    for node in _video_candidates(payload):
        video_id=str(_first(node,'aweme_id','item_id'))
        if video_id in seen_videos:continue
        seen_videos.add(video_id); author=node.get('author') if isinstance(node.get('author'),dict) else {}; creator=_creator_from_author(author,raw_evidence_id) if author else None
        if creator and creator['creator_id'] not in seen_creators:seen_creators.add(creator['creator_id']); out['creators'].append(creator)
        video=node.get('video') if isinstance(node.get('video'),dict) else {}; video_info=node.get('video_info') if isinstance(node.get('video_info'),dict) else {}; stats=node.get('statistics') if isinstance(node.get('statistics'),dict) else {}
        if not stats and isinstance(node.get('stats'),dict):stats=node['stats']
        music=node.get('music') if isinstance(node.get('music'),dict) else {}; hashtags=[]
        for extra in node.get('text_extra',[]) if isinstance(node.get('text_extra'),list) else []:
            if isinstance(extra,dict) and _first(extra,'hashtag_name','hashtagName'):hashtags.append(str(_first(extra,'hashtag_name','hashtagName')))
        for challenge in node.get('cha_list',[]) if isinstance(node.get('cha_list'),list) else []:
            if isinstance(challenge,dict) and _first(challenge,'cha_name','title'):hashtags.append(str(_first(challenge,'cha_name','title')))
        hashtags=list(dict.fromkeys(hashtags)); duration=_first(video,'duration') or _first(video_info,'duration') or _first(node,'duration'); cover=_url(_first(video,'cover','origin_cover','dynamic_cover')) or _url(_first(video_info,'cover')); play=_url(_first(video,'play_addr','download_addr')) or _url(_first(video_info,'video_url','url'))
        out['videos'].append({'video_id':video_id,'creator_id':creator['creator_id'] if creator else None,'caption':_as_text(_first(node,'desc','title','caption')),'create_time':_as_text(_first(node,'create_time','createTime')),'duration_sec':_duration_seconds(duration),'region':_as_text(request_payload.get('region') or request_payload.get('country_code')),'cover_url':cover,'video_url':play,'music_id':_as_text(_first(music,'id','mid','music_id')),'music_title':_as_text(_first(music,'title','music_name')),'hashtags_json':json.dumps(hashtags,ensure_ascii=False),'raw_evidence_id':raw_evidence_id})
        metrics={'views':_as_int(_first(stats,'play_count','view_count','views','video_views','playCount')),'likes':_as_int(_first(stats,'digg_count','like_count','likes','diggCount')),'comments':_as_int(_first(stats,'comment_count','comments','commentCount')),'shares':_as_int(_first(stats,'share_count','shares','shareCount')),'favorites':_as_int(_first(stats,'collect_count','favorite_count','favorites','collectCount')),'author_followers':creator.get('followers') if creator else None}
        if any(value is not None for value in metrics.values()):out['video_snapshots'].append({'video_id':video_id,**metrics,'raw_evidence_id':raw_evidence_id})
        out['discoveries'].append({'video_id':video_id,'source_type':_as_text(request_payload.get('_capability')) or 'video','query_text':_as_text(request_payload.get('keyword')),'source_rank':None,'sort_type':_as_text(request_payload.get('sort_type')),'time_window':_as_text(request_payload.get('publish_time')),'raw_evidence_id':raw_evidence_id})
    return out
def _normalize_video_metrics(payload,raw_evidence_id,request_payload):
    out=_empty_bundle(); video_id=_as_text(request_payload.get('item_id'))
    if not video_id:return out
    data=payload.get('data') if isinstance(payload,dict) and isinstance(payload.get('data'),dict) else payload
    if not isinstance(data,dict):return out
    metrics=data.get('statistics') if isinstance(data.get('statistics'),dict) else data; out['video_snapshots'].append({'video_id':video_id,'views':_as_int(_first(metrics,'views','view_count','play_count')),'likes':_as_int(_first(metrics,'likes','like_count','digg_count')),'comments':_as_int(_first(metrics,'comments','comment_count')),'shares':_as_int(_first(metrics,'shares','share_count')),'favorites':_as_int(_first(metrics,'favorites','favorite_count','collect_count')),'author_followers':None,'raw_evidence_id':raw_evidence_id}); return out
def _normalize_comments(payload,raw_evidence_id,request_payload):
    out=_empty_bundle(); video_id=_as_text(request_payload.get('aweme_id') or request_payload.get('item_id')); seen=set()
    for node in _walk(payload):
        if not isinstance(node,dict):continue
        cid=_as_text(_first(node,'cid','comment_id')); text=_as_text(_first(node,'text','content'))
        if not cid or text is None or cid in seen:continue
        seen.add(cid); user=node.get('user') if isinstance(node.get('user'),dict) else {}; out['comments'].append({'comment_id':cid,'video_id':video_id,'author_id':_as_text(_first(user,'uid','id','user_id')),'text':text,'like_count':_as_int(_first(node,'digg_count','like_count')),'reply_count':_as_int(_first(node,'reply_comment_total','reply_count')),'language':_as_text(_first(node,'language')),'created_at':_as_text(_first(node,'create_time','created_at')),'raw_evidence_id':raw_evidence_id})
    return out
def _normalize_search_insights(capability,payload,raw_evidence_id,request_payload):
    out=_empty_bundle()
    if capability=='creator_search_insights':
        seen=set()
        for node in _walk(payload):
            if not isinstance(node,dict):continue
            query_id=_as_text(_first(node,'query_id','query_id_str')); keyword=_as_text(_first(node,'query','keyword','search_word','query_name'))
            if not query_id or not keyword or query_id in seen:continue
            seen.add(query_id); extras={k:v for k,v in node.items() if k not in {'query_id','query_id_str','query','keyword','search_word','query_name'}}; out['search_insights'].append({'query_id':query_id,'keyword':keyword,'insight_type':_as_text(request_payload.get('tab')),'region':_as_text(request_payload.get('region')),'language':_as_text(request_payload.get('language_filters')),'rank':_as_int(_first(node,'rank','rank_index')),'trend_json':None,'demographics_json':None,'raw_metrics_json':json.dumps(extras,ensure_ascii=False),'raw_evidence_id':raw_evidence_id})
    else:
        query_id=_as_text(request_payload.get('query_id_str')); keyword=_as_text(request_payload.get('_search_keyword')) or _as_text(request_payload.get('keyword'))
        if query_id:out['search_insights'].append({'query_id':query_id,'keyword':keyword or query_id,'insight_type':capability,'region':None,'language':None,'rank':None,'trend_json':json.dumps(payload.get('data') if isinstance(payload,dict) else payload,ensure_ascii=False),'demographics_json':json.dumps(payload.get('data') if capability.endswith('detail') and isinstance(payload,dict) else None,ensure_ascii=False),'raw_metrics_json':None,'raw_evidence_id':raw_evidence_id})
    return out
def _normalize_ads(payload,raw_evidence_id):
    out=_empty_bundle(); seen=set()
    for node in _walk(payload):
        if not isinstance(node,dict):continue
        material_id=_as_text(_first(node,'material_id','ads_id'))
        if not material_id or material_id in seen or not any(k in node for k in ('video_info','brand_name','advertiser_name','ad_title','desc','statistics')):continue
        seen.add(material_id); stats=node.get('statistics') if isinstance(node.get('statistics'),dict) else {}; out['ads'].append({'material_id':material_id,'ads_id':_as_text(_first(node,'ads_id','id')),'video_id':_as_text(_first(node,'aweme_id','item_id')),'ad_title':_as_text(_first(node,'ad_title','title')),'description':_as_text(_first(node,'desc','description')),'brand_name':_as_text(_first(node,'brand_name')),'advertiser_name':_as_text(_first(node,'advertiser_name')),'landing_page':_as_text(_first(node,'landing_page')),'industry_key':_as_text(_first(node,'industry_key')),'objective_key':_as_text(_first(node,'objective_key')),'cost_level':_as_int(_first(node,'cost')),'ctr_raw':_first(node,'ctr'),'likes':_as_int(_first(stats,'likes','like') or _first(node,'like','likes')),'comments':_as_int(_first(stats,'comments') or _first(node,'comment','comments')),'shares':_as_int(_first(stats,'shares') or _first(node,'share','shares')),'create_time':_as_text(_first(node,'create_time')),'raw_evidence_id':raw_evidence_id})
    return out
def _normalize_ad_timeseries(capability,payload,raw_evidence_id,request_payload):
    out=_empty_bundle(); material_id=_as_text(request_payload.get('material_id'))
    if not material_id:return out
    data=payload.get('data') if isinstance(payload,dict) and isinstance(payload.get('data'),dict) else payload
    if not isinstance(data,dict):return out
    rows=[]
    if isinstance(data.get('time_series'),list):
        for point in data['time_series']:
            if isinstance(point,dict):rows.append((_first(point,'time','second'),_first(point,'value','rate')))
    elif isinstance(data.get('time_points'),list) and isinstance(data.get('retention_rates'),list):rows=list(zip(data['time_points'],data['retention_rates']))
    drops={str(x) for x in data.get('drop_points',[]) if x is not None} if isinstance(data.get('drop_points'),list) else set(); highs={str(x) for x in data.get('highlight_points',[]) if x is not None} if isinstance(data.get('highlight_points'),list) else set(); metric=_as_text(request_payload.get('metric') or request_payload.get('metric_type')) or 'unknown'
    for second,value in rows:out['ad_timeseries'].append({'material_id':material_id,'analysis_type':capability,'metric':metric,'second':float(second),'value':float(value) if value is not None else None,'is_drop':1 if str(second) in drops else 0,'is_highlight':1 if str(second) in highs else 0,'raw_evidence_id':raw_evidence_id})
    return out
def normalize_capability(capability,payload,*,raw_evidence_id=None,request_payload=None):
    request=dict(request_payload or {}); request['_capability']=capability
    if capability in {'creator_search_insights','creator_search_insights_trend','creator_search_insights_detail'}:return _normalize_search_insights(capability,payload,raw_evidence_id,request)
    if capability=='video_comments':return _normalize_comments(payload,raw_evidence_id,request)
    if capability=='video_metrics':return _normalize_video_metrics(payload,raw_evidence_id,request)
    if capability in {'ads_search','top_ads_spotlight','ads_detail','ad_percentile'}:return _normalize_ads(payload,raw_evidence_id)
    if capability in {'ad_keyframe_analysis','ad_interactive_analysis'}:return _normalize_ad_timeseries(capability,payload,raw_evidence_id,request)
    if capability in {'video_search','creator_posts','creator_search_insights_videos','video_detail','top_contents_list','top_contents_item_detail'}:return _normalize_videos(payload,raw_evidence_id,request)
    return _empty_bundle()

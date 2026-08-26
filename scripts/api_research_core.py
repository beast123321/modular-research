"""通用、零依赖的「第三方 API 安全调研」核心模块。

从 shengjiang-research Skill 的 tikhub_request.py 中抽取并泛化：
- 去掉 TikHub 专属的 CLI 耦合（不再强制 /api/ 路径、不再 SystemExit）
- 错误处理改为库风格（抛异常而非退出进程）
- base_url / 鉴权方式 / 密钥服务名全部参数化

核心能力只有 5 件：
  1. 安全密钥解析   —— 从环境变量 / macOS Keychain 读 Key，绝不回显
  2. 敏感数据脱敏   —— 存档/日志前自动把 token/sign/cache_url 等替换成 ***
  3. 成本预估       —— 阶梯折扣计费，付费批量前先算账
  4. HTTP 传输      —— GET/POST + Bearer 鉴权 + 错误封装
  5. URL 构造校验   —— 拼安全请求地址，校验路径前缀

仅依赖 Python 标准库。Python 3.10+（用了 str | None 注解）。
"""
from __future__ import annotations
import json, os, platform, subprocess, urllib.error, urllib.parse, urllib.request
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
DEFAULT_BASE_URL='https://api.tikhub.dev'; DEFAULT_TIMEOUT=45; DEFAULT_KEY_ENV='TIKHUB_API_KEY'; DEFAULT_KEYCHAIN_SERVICE='tikhub-api'; DEFAULT_KEYCHAIN_ACCOUNT='tikhub'
SENSITIVE_KEYS={'authorization','token','key','api_key','apikey','secret','sign','cache_url'}
PRICE_TIERS=((1000,Decimal('0')),(5000,Decimal('0.10')),(10000,Decimal('0.20')),(20000,Decimal('0.30')),(30000,Decimal('0.40')),(None,Decimal('0.50')))

def redact_url(url:str)->str:
    parsed=urllib.parse.urlsplit(url); pairs=urllib.parse.parse_qsl(parsed.query,keep_blank_values=True); safe=[(k,'***' if k.lower() in SENSITIVE_KEYS else v) for k,v in pairs]; return urllib.parse.urlunsplit((parsed.scheme,parsed.netloc,parsed.path,urllib.parse.urlencode(safe),''))

def redact_payload(value:Any)->Any:
    if isinstance(value,dict): return {k:'<redacted>' if k.lower() in SENSITIVE_KEYS else redact_payload(v) for k,v in value.items()}
    if isinstance(value,list): return [redact_payload(v) for v in value]
    return value

def estimate_cost(requests:int,unit_price:Decimal)->dict[str,Any]:
    if requests<1: raise ValueError('--estimate-requests must be a positive integer')
    if unit_price<=0: raise ValueError('--unit-price must be greater than zero')
    remaining=requests; lower=0; total=Decimal('0'); breakdown=[]
    for upper,discount in PRICE_TIERS:
        if remaining<=0: break
        capacity=remaining if upper is None else max(0,upper-lower); count=min(remaining,capacity); discounted=unit_price*(Decimal('1')-discount); cost=discounted*count; breakdown.append({'requests':count,'discount_percent':float(discount*100),'unit_price_usd':float(discounted),'cost_usd':float(cost)}); total+=cost; remaining-=count
        if upper is not None: lower=upper
    return {'requests':requests,'base_unit_price_usd':float(unit_price),'estimated_total_usd':float(total),'average_unit_price_usd':float(total/requests),'tiers':breakdown,'disclaimer':'Estimate only. Verify the endpoint price with provider before paid batch requests.'}

def price_preview(requests:int,unit_price_raw:str|None=None)->dict[str,Any]:
    if unit_price_raw:
        try: unit_price=Decimal(unit_price_raw)
        except InvalidOperation as exc: raise ValueError('--unit-price must be a valid decimal') from exc
        return {'exact_input':estimate_cost(requests,unit_price)}
    return {'typical_range':{'low':estimate_cost(requests,Decimal('0.001')),'high':estimate_cost(requests,Decimal('0.01'))},'warning':'Some special endpoints cost more than 0.01 USD/request. Check the selected endpoint.'}

def validate_path(path:str,required_prefix:str='/api/')->None:
    if required_prefix and (not path.startswith(required_prefix) or path.startswith('//')): raise ValueError(f"--path must begin with exactly one '{required_prefix}'")

def build_url(base_url:str,path:str,params:Any)->str:
    validate_path(path)
    if params is not None and not isinstance(params,dict): raise ValueError('--params must be a JSON object')
    url=base_url.rstrip('/')+path
    if params: url+='?'+urllib.parse.urlencode(params,doseq=True)
    return url

def read_keychain(service:str,account:str)->str:
    if platform.system()!='Darwin': return ''
    try: result=subprocess.run(['security','find-generic-password','-s',service,'-a',account,'-w'],check=False,text=True,capture_output=True)
    except FileNotFoundError: return ''
    return result.stdout.strip() if result.returncode==0 else ''

def resolve_api_key(env_name:str=DEFAULT_KEY_ENV,keychain_service:str=DEFAULT_KEYCHAIN_SERVICE,keychain_account:str=DEFAULT_KEYCHAIN_ACCOUNT,config_path:str|None=None,disable_keychain:bool=False)->tuple[str,str]:
    value=os.environ.get(env_name,'').strip()
    if value: return value,f'environment:{env_name}'
    if config_path and os.path.isfile(config_path):
        try:
            with open(config_path,encoding='utf-8') as fh: data=json.load(fh)
            v=(data.get('api_key') or '').strip()
            if v: return v,f'config:{Path(config_path).name}'
        except (json.JSONDecodeError,OSError): pass
    if disable_keychain: return '','missing'
    value=read_keychain(keychain_service,keychain_account)
    return (value,'macOS Keychain') if value else ('','missing')

class APIRequestError(Exception):
    def __init__(self,status:int|None,message:str): self.status=status; self.message=message; super().__init__(f'HTTP {status}: {message}')

def request_json(*,base_url:str=DEFAULT_BASE_URL,api_key:str,method:str='GET',path:str,params:Any=None,body:Any=None,timeout:int|None=None,auth_scheme:str='Bearer',user_agent:str='ApiResearchCore/1.0')->Any:
    url=build_url(base_url,path,params); data=None; headers={'Authorization':f'{auth_scheme} {api_key}','Accept':'application/json','Accept-Language':'zh-CN,zh;q=0.9,en;q=0.8','User-Agent':user_agent}
    if body is not None: data=json.dumps(body,ensure_ascii=False).encode('utf-8'); headers['Content-Type']='application/json'
    request=urllib.request.Request(url,data=data,method=method,headers=headers)
    try:
        with urllib.request.urlopen(request,timeout=int(timeout or DEFAULT_TIMEOUT)) as response: raw=response.read()
    except urllib.error.HTTPError as exc:
        detail=exc.read().decode('utf-8',errors='replace').replace(api_key,'<redacted>'); raise APIRequestError(exc.code,detail[:1000]) from exc
    except urllib.error.URLError as exc: raise APIRequestError(None,str(exc.reason)) from exc
    try: return json.loads(raw)
    except json.JSONDecodeError: return {'raw_text':raw.decode('utf-8',errors='replace')}

def parse_json_arg(raw:str|None)->Any:
    if not raw: return None
    if raw.startswith('@'): return json.loads(Path(raw[1:]).read_text(encoding='utf-8'))
    return json.loads(raw)

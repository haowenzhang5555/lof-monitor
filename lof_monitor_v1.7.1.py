#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# LOF基金监控 v1.7.1

import http.server
import urllib.parse
import urllib.request
import json
import time
import threading
import re

SIM_DATA = [
    {'code': '164205', 'name': '天弘文化新兴产业股票A', 'price': 4.4845, 'prev_close': 4.4845, 'nav': 4.2853, 'nav_prev': 4.26, 'status': '正常申购', 'pct_price': 0.0, 'pct_nav': 0.59, 'premium': 4.65, 'nav_date': '', 'is_estimated': False},
    {'code': '162703', 'name': '广发小盘成长混合(LOF)A', 'price': 2.3477, 'prev_close': 2.3477, 'nav': 2.2620, 'nav_prev': 2.25, 'status': '暂停申购', 'pct_price': 0.0, 'pct_nav': 0.53, 'premium': 3.79, 'nav_date': '', 'is_estimated': False},
    {'code': '501078', 'name': '广发科创主题灵活配置混合(LOF)', 'price': 3.0150, 'prev_close': 3.00, 'nav': 2.9271, 'nav_prev': 2.90, 'status': '限1000万', 'pct_price': 0.5, 'pct_nav': 0.93, 'premium': 3.0, 'nav_date': '', 'is_estimated': False},
    {'code': '160706', 'name': '嘉实沪深300ETF联接A', 'price': 1.2267, 'prev_close': 1.22, 'nav': 2.2620, 'nav_prev': 1.19, 'status': '正常申购', 'pct_price': 0.55, 'pct_nav': 1.2, 'premium': 1.86, 'nav_date': '', 'is_estimated': False},
    {'code': '166009', 'name': '中欧新动力混合(LOF)A', 'price': 3.6063, 'prev_close': 3.58, 'nav': 3.5497, 'nav_prev': 3.52, 'status': '限50万', 'pct_price': 0.74, 'pct_nav': 0.84, 'premium': 1.59, 'nav_date': '', 'is_estimated': False},
    {'code': '161226', 'name': '国投瑞银白银期货(LOF)A', 'price': 2.0148, 'prev_close': 1.8838, 'nav': 1.8838, 'nav_prev': 1.8838, 'status': '正常申购', 'pct_price': 6.95, 'pct_nav': -0.46, 'premium': 6.96, 'nav_date': '', 'is_estimated': False},
    {'code': '159876', 'name': '华夏中证动漫游戏ETF', 'price': 0.8512, 'prev_close': 0.8598, 'nav': 0.8496, 'nav_prev': 0.855, 'status': '正常申购', 'pct_price': -1.0, 'pct_nav': -0.63, 'premium': 0.19, 'nav_date': '', 'is_estimated': False},
    {'code': '513100', 'name': '国泰纳斯达克100ETF', 'price': 1.8653, 'prev_close': 1.85, 'nav': 1.8432, 'nav_prev': 1.83, 'status': '限500万', 'pct_price': 0.83, 'pct_nav': 0.72, 'premium': 1.2, 'nav_date': '', 'is_estimated': False},
    {'code': '510300', 'name': '华泰柏瑞沪深300ETF', 'price': 3.9856, 'prev_close': 3.96, 'nav': 3.9820, 'nav_prev': 3.95, 'status': '正常申购', 'pct_price': 0.65, 'pct_nav': 0.81, 'premium': 0.09, 'nav_date': '', 'is_estimated': False},
    {'code': '159995', 'name': '华夏国证半导体芯片ETF', 'price': 1.1234, 'prev_close': 1.11, 'nav': 1.1210, 'nav_prev': 1.115, 'status': '正常申购', 'pct_price': 1.21, 'pct_nav': 1.35, 'premium': 0.21, 'nav_date': '', 'is_estimated': False},
    {'code': '161725', 'name': '招商中证白酒指数(LOF)A', 'price': 1.0987, 'prev_close': 1.09, 'nav': 1.0960, 'nav_prev': 1.092, 'status': '限100万', 'pct_price': 0.8, 'pct_nav': 0.88, 'premium': 0.25, 'nav_date': '', 'is_estimated': False},
]

LIST_NAME = 'LOF/ETF精选基金列表'

_lock = threading.Lock()
_search_cache = None
_search_cache_time = 0
_search_cache_ttl = 1800


def _http_get(url, timeout=8, headers=None, decode=True):
    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15A372')
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        if not decode:
            return data
        for enc in ('utf-8', 'gbk', 'gb18030', 'latin-1'):
            try:
                return data.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue
        return data.decode('utf-8', errors='ignore')
    except Exception:
        return None


def _ensure_search_cache():
    global _search_cache, _search_cache_time
    now = time.time()
    if _search_cache and (now - _search_cache_time) < _search_cache_ttl:
        return True
    text = _http_get('http://fund.eastmoney.com/js/fundcode_search.js', timeout=10)
    if not text:
        return False
    try:
        start = text.find('[')
        end = text.rfind(']')
        if start < 0 or end < 0 or end <= start:
            return False
        arr = json.loads(text[start:end + 1])
        with _lock:
            _search_cache = arr
            _search_cache_time = now
        return True
    except Exception:
        return False


def search_funds_online(keyword, limit=30):
    keyword = (keyword or '').strip()
    if not keyword:
        return None
    if not _ensure_search_cache():
        local = [{'code': f['code'], 'name': f['name']} for f in SIM_DATA if keyword in f.get('name', '') or keyword in f.get('code', '')]
        return local[:limit] if local else None
    q = keyword.lower()
    with _lock:
        cache = _search_cache[:] if _search_cache else []
    matches = []
    seen = set()
    for item in cache:
        if len(item) < 3:
            continue
        code = str(item[0])
        name = str(item[2])
        pinyin = str(item[1]) if len(item) > 1 else ''
        if code in seen:
            continue
        if q in code or q in name or q in pinyin.lower():
            matches.append({'code': code, 'name': name})
            seen.add(code)
            if len(matches) >= limit:
                break
    return matches


def fetch_fund_nav(code):
    nav = None
    pct_nav = 0.0
    nav_prev = None
    name = ''
    nav_date = ''
    text = _http_get('http://fundgz.1234567.com.cn/js/%s.js' % code, timeout=5)
    gsz_found = False
    if text:
        try:
            start = text.find('{')
            end = text.rfind('}')
            if start >= 0 and end > start:
                d = json.loads(text[start:end + 1])
                gsz = d.get('gsz')
                gszzl = d.get('gszzl')
                dwjz = d.get('dwjz')
                name = d.get('name', '')
                gztime = d.get('gztime', '')
                if gsz and gsz not in ('', 'null', 'None'):
                    try:
                        nav = round(float(gsz), 4)
                        nav_date = gztime
                        gsz_found = True
                    except (ValueError, TypeError):
                        nav = None
                if gszzl and gszzl not in ('', 'null', 'None'):
                    try:
                        pct_nav = round(float(gszzl), 2)
                    except (ValueError, TypeError):
                        pct_nav = 0.0
                if dwjz and dwjz not in ('', 'null', 'None'):
                    try:
                        nav_prev = round(float(dwjz), 4)
                    except (ValueError, TypeError):
                        nav_prev = None
        except Exception:
            pass
    if nav is not None:
        return {'nav': nav, 'nav_prev': nav_prev or nav, 'pct_nav': pct_nav, 'name': name, 'nav_date': nav_date, 'is_estimated': gsz_found}
    text = _http_get('http://fund.eastmoney.com/pingzhongdata/%s.js?v=%d' % (code, int(time.time())), timeout=6)
    if not text:
        return None
    try:
        m = re.search(r'Data_netWorthTrend\s*=\s*(\[.*?\]);', text, re.DOTALL)
        if m:
            arr = json.loads(m.group(1))
            if arr and len(arr) > 0:
                last = arr[-1]
                nav = float(last.get('y', 0))
                pct_nav = float(last.get('equityReturn', 0)) or 0.0
                prev = arr[-2] if len(arr) > 1 else None
                nav_prev = float(prev.get('y')) if prev else nav
                ts = last.get('x', int(time.time() * 1000))
                nav_date = time.strftime('%Y-%m-%d', time.localtime(ts / 1000))
                nm = re.search(r'fS_name\s*=\s*"([^"]+)"', text)
                name = nm.group(1) if nm else ''
                return {'nav': round(nav, 4), 'nav_prev': round(nav_prev, 4), 'pct_nav': round(pct_nav, 2), 'name': name, 'nav_date': nav_date, 'is_estimated': False}
    except Exception:
        pass
    return None


def fetch_fund_price(code):
    headers = {'Referer': 'http://finance.sina.com.cn'}
    if code.startswith('5'):
        symbols = ['sh' + code, 'sz' + code, 'of' + code]
    else:
        symbols = ['sz' + code, 'sh' + code, 'of' + code]
    for symbol in symbols:
        raw = _http_get('http://hq.sinajs.cn/list=' + symbol, timeout=5, headers=headers, decode=False)
        if not raw:
            continue
        try:
            text = raw.decode('gbk', errors='ignore')
        except Exception:
            text = raw.decode('utf-8', errors='ignore')
        m = re.search(r'="([^"]+)"', text)
        if not m:
            continue
        parts = m.group(1).split(',')
        if len(parts) < 4:
            continue
        price_str = parts[3]
        prev_str = parts[2]
        if not price_str or price_str in ('0', '0.0', '0.00', '0.000', '0.0000'):
            continue
        try:
            price = float(price_str)
            prev_close = float(prev_str) if prev_str else price
        except (ValueError, TypeError):
            continue
        if price <= 0:
            continue
        pct = 0.0
        if prev_close > 0:
            pct = round((price - prev_close) / prev_close * 100, 2)
        return {'price': price, 'prev_close': prev_close, 'pct_price': pct}
    return None


def fetch_fund_status(code):
    status = '正常申购'
    try:
        text = _http_get('http://fundf10.eastmoney.com/jbxx_%s.html' % code, timeout=6)
        if text:
            text_norm = re.sub(r'\s+', ' ', text)
            m = re.search(r'申购状态</td>\s*<td[^>]*>([^<]+)</td>', text_norm)
            sg = m.group(1).strip() if m else ''
            limit_text = ''
            m3 = re.search(r'(?:单日限额|单用户限额|单户限额|限大额)[^<]{0,20}</td>\s*<td[^>]*>([^<]+)</td>', text_norm)
            if m3:
                limit_text = m3.group(1).strip()
            if '暂停' in sg or '停止' in sg or '封闭' in sg:
                status = '暂停申购'
            elif '限大额' in sg or '限大额' in (limit_text or ''):
                status = '限大额'
                if limit_text and limit_text not in ('--', '元', ''):
                    num = re.search(r'(\d+)', limit_text)
                    if num:
                        n = int(num.group(1))
                        if n >= 100000000:
                            status = '限%d亿' % (n // 100000000)
                        elif n >= 10000:
                            status = '限%d万' % (n // 10000)
                        else:
                            status = '限%d元' % n
            elif '开放' in sg or sg == '':
                status = '正常申购'
            else:
                status = sg if sg else '正常申购'
    except Exception:
        pass
    return status


def enrich_fund(basic):
    code = basic.get('code', '')
    name = basic.get('name', '') or code
    result = {
        'code': code, 'name': name,
        'price': 0.0, 'prev_close': 0.0, 'nav': 0.0, 'nav_prev': 0.0,
        'status': '正常申购', 'pct_price': 0.0, 'pct_nav': 0.0, 'premium': 0.0,
        'nav_date': '', 'is_estimated': False
    }
    got_nav = fetch_fund_nav(code)
    if got_nav:
        result['nav'] = got_nav['nav']
        result['nav_prev'] = got_nav['nav_prev'] or got_nav['nav']
        result['pct_nav'] = got_nav.get('pct_nav', 0.0) or 0.0
        result['nav_date'] = got_nav.get('nav_date', '') or ''
        result['is_estimated'] = got_nav.get('is_estimated', False)
        if got_nav.get('name'):
            result['name'] = got_nav['name']
    got_price = fetch_fund_price(code)
    if got_price:
        result['price'] = got_price['price']
        result['prev_close'] = got_price['prev_close']
        result['pct_price'] = got_price['pct_price']
    if result['nav'] > 0 and result['price'] > 0:
        result['premium'] = round((result['price'] - result['nav']) / result['nav'] * 100, 2)
    try:
        result['status'] = fetch_fund_status(code)
    except Exception:
        result['status'] = '正常申购'
    return result


def fetch_fund_history(code):
    result = []
    text = _http_get('http://fund.eastmoney.com/pingzhongdata/%s.js?v=%d' % (code, int(time.time())), timeout=10)
    if not text:
        return result
    try:
        m = re.search(r'Data_netWorthTrend\s*=\s*(\[.*?\]);', text, re.DOTALL)
        if m:
            arr = json.loads(m.group(1))
            for item in arr[-60:]:
                ts = item.get('x', 0)
                y = float(item.get('y', 0))
                pct = float(item.get('equityReturn', 0)) or 0.0
                dt = time.strftime('%Y-%m-%d', time.localtime(ts / 1000))
                result.append({'date': dt, 'nav': y, 'pct': pct})
    except Exception:
        pass
    return result


def fetch_fund_kline(code, days=90):
    result = []
    headers = {'Referer': 'http://finance.sina.com.cn', 'User-Agent': 'Mozilla/5.0'}
    if code.startswith('5'):
        symbol = 'sh' + code
    else:
        symbol = 'sz' + code
    try:
        url = 'http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=%s&scale=240&ma=no&datalen=%d' % (symbol, days)
        text = _http_get(url, timeout=8, headers=headers)
        if not text:
            return result
        arr = json.loads(text)
        for item in arr:
            try:
                result.append({
                    'date': item.get('day', ''),
                    'open': float(item.get('open', 0)) or 0.0,
                    'high': float(item.get('high', 0)) or 0.0,
                    'low': float(item.get('low', 0)) or 0.0,
                    'close': float(item.get('close', 0)) or 0.0,
                    'volume': float(item.get('volume', 0)) or 0.0
                })
            except (ValueError, TypeError):
                continue
    except Exception:
        pass
    return result


def fetch_full_history(code, days=90):
    nav_hist = fetch_fund_history(code)
    kline = fetch_fund_kline(code, days)
    status = '正常申购'
    try:
        status = fetch_fund_status(code)
    except Exception:
        pass

    kline_map = {}
    for k in kline:
        kline_map[k['date']] = k['close']

    nav_map = {}
    for n in nav_hist:
        nav_map[n['date']] = n

    merged = []
    all_dates = set(nav_map.keys()) | set(kline_map.keys())
    for d in sorted(all_dates, reverse=True):
        nav_item = nav_map.get(d)
        nav = nav_item['nav'] if nav_item else 0
        pct = nav_item.get('pct', 0) if nav_item else 0
        close = kline_map.get(d, 0) or 0
        premium = 0.0
        if nav > 0 and close > 0:
            premium = round((close - nav) / nav * 100, 2)
        merged.append({
            'date': d,
            'nav': round(nav, 4) if nav > 0 else 0,
            'close': round(close, 4) if close > 0 else 0,
            'premium': premium,
            'pct': round(pct, 2) if pct else 0
        })

    nav_date = ''
    if nav_hist:
        nav_date = nav_hist[-1].get('date', '')

    return {
        'code': code,
        'nav_history': nav_hist,
        'kline': kline,
        'merged': merged,
        'status': status,
        'nav_date': nav_date
    }


def handler_from_list(items):
    return list(items)


HTML_CONTENT = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>LOF基金监控</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent;}
html,body{height:100%;font-family:-apple-system,Helvetica,"PingFang SC","Microsoft YaHei",sans-serif;background:#f0f2f5;}
#app{display:flex;flex-direction:column;height:100%;}
.header{background:linear-gradient(135deg,#1a237e,#303f9f);padding:10px 10px 12px;flex-shrink:0;box-shadow:0 2px 8px rgba(0,0,0,.12);}
.title-bar{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;}
.title{color:#fff;font-size:15px;font-weight:700;letter-spacing:1px;}
.list-name{color:#ffd54f;font-size:11px;font-weight:600;background:rgba(255,213,79,.18);padding:3px 10px;border-radius:12px;}
.search-bar{display:flex;align-items:center;gap:6px;}
.search-input{flex:1;height:32px;padding:0 12px;border-radius:16px;border:none;font-size:13px;background:rgba(255,255,255,.96);color:#222;outline:none;}
.btn{height:32px;padding:0 12px;border-radius:16px;border:none;font-size:12px;font-weight:600;cursor:pointer;flex-shrink:0;transition:transform .1s;}
.btn:active{transform:scale(.94);}
.btn-search{background:#ffd54f;color:#1a237e;}
.btn-refresh{background:rgba(255,255,255,.22);color:#fff;padding:0 10px;}
.btn-auto{background:#4caf50;color:#fff;padding:0 10px;font-size:11px;}
.btn-auto.on{background:#ff9800;}
.search-mode{font-size:10px;color:#fff;padding:2px 8px;border-radius:10px;background:rgba(255,255,255,.15);cursor:pointer;margin-left:4px;}
.search-mode.active{background:rgba(255,213,79,.3);}
.tabs{display:flex;gap:5px;padding:6px 8px;background:#fff;border-bottom:1px solid #e8e8e8;flex-shrink:0;overflow-x:auto;white-space:nowrap;}
.tab{padding:4px 10px;border-radius:12px;background:#f0f2f5;color:#555;font-size:11px;cursor:pointer;flex-shrink:0;}
.tab.active{background:#1a237e;color:#fff;font-weight:600;}
.summary{display:flex;justify-content:space-around;padding:5px 8px;background:#fff;font-size:10px;color:#666;border-bottom:1px solid #eee;flex-shrink:0;}
.summary span{color:#222;font-weight:600;}
.summary .hi{color:#e53935;}
.summary .lo{color:#43a047;}
.summary .auto{color:#4caf50;}
.col-header{position:sticky;top:0;z-index:10;display:flex;align-items:center;gap:6px;padding:8px 8px;background:#1976d2;color:#fff;font-size:11px;font-weight:600;border-bottom:1px solid #0d47a1;flex-shrink:0;}
.col-header .col-fav{width:22px;text-align:center;flex-shrink:0;}
.col-header .col-info{flex:1;min-width:0;cursor:pointer;user-select:none;padding:2px 4px;border-radius:4px;}
.col-header .col-info:active{background:rgba(255,255,255,.2);}
.col-header .col-data{display:flex;gap:8px;align-items:center;}
.col-header .col-data .sort-h{min-width:62px;text-align:right;cursor:pointer;user-select:none;padding:2px 4px;border-radius:4px;}
.col-header .col-data .sort-h.prem{min-width:54px;text-align:center;}
.col-header .col-data .sort-h:active{background:rgba(255,255,255,.2);}
.col-header .arrow{display:inline-block;margin-left:2px;font-size:10px;opacity:.75;}
.col-header .arrow.active{opacity:1;color:#ffd54f;font-weight:700;}
.content{flex:1;overflow-y:auto;padding:4px;}
.item{background:#fff;border-radius:8px;padding:10px 8px;margin-bottom:4px;display:flex;align-items:center;gap:6px;box-shadow:0 1px 2px rgba(0,0,0,.04);cursor:pointer;transition:background .15s;position:relative;overflow:hidden;}
.item:active{background:#f5f5f5;}
.item.fav-item{background:linear-gradient(90deg,#fff5f5 0%,#fff 8px,#fff 100%);}
.item.fav-item::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:#e53935;}
.item.search-result{background:linear-gradient(90deg,#e3f2fd 0%,#fff 8px,#fff 100%);}
.item.search-result::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:#2196f3;}
.fav-btn{width:26px;height:26px;border-radius:50%;border:none;background:#f5f5f5;color:#999;font-size:13px;cursor:pointer;flex-shrink:0;display:flex;align-items:center;justify-content:center;transition:all .15s;}
.fav-btn.active{background:#ffebee;color:#e53935;}
.info{flex:1;min-width:0;}
.name{font-size:13px;font-weight:600;color:#212121;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.info-row{display:flex;align-items:center;gap:8px;margin-top:3px;flex-wrap:wrap;}
.code{font-size:11px;color:#757575;font-family:"SF Mono","Menlo",monospace;}
.tag{font-size:10px;padding:1px 6px;border-radius:3px;font-weight:500;}
.tag.stop{background:#ffebee;color:#e53935;}
.tag.limit{background:#fff8e1;color:#f57c00;}
.tag.ok{background:#e8f5e9;color:#43a047;}
.tag.est{background:#90caf9;color:#1565c0;font-size:9px;}
.tag.search{background:#2196f3;color:#fff;font-size:9px;margin-left:4px;}
.data{display:flex;align-items:center;gap:8px;}
.price-box{text-align:right;min-width:62px;}
.price{font-size:13px;font-weight:700;color:#212121;}
.price.miss{color:#bbb;font-weight:500;}
.price.nav{color:#1976d2;}
.price.close{color:#f57c00;}
.pct{font-size:10px;font-weight:600;margin-top:1px;}
.pct.up{color:#e53935;}
.pct.down{color:#43a047;}
.pct.flat{color:#999;}
.prem-box{min-width:52px;text-align:center;padding:4px 3px;border-radius:5px;color:#fff;font-weight:700;}
.prem-box.hi{background:#e53935;}
.prem-box.mid{background:#fb8c00;}
.prem-box.lo{background:#43a047;}
.prem-box.neg{background:#1e88e5;}
.prem-box.na{background:#9e9e9e;}
.prem-box .p1{font-size:12px;}
.prem-box .p2{font-size:9px;opacity:.9;margin-top:1px;}
.empty{text-align:center;padding:40px 20px;color:#999;font-size:13px;}
.toast{position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:rgba(0,0,0,.8);color:#fff;padding:8px 16px;border-radius:6px;font-size:12px;opacity:0;pointer-events:none;z-index:300;transition:opacity .2s;}
.toast.show{opacity:1;}
.modal-mask{position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:200;display:none;align-items:stretch;justify-content:center;}
.modal-mask.show{display:flex;animation:fadein .2s;}
@keyframes fadein{from{opacity:0;}to{opacity:1;}}
.modal{position:relative;width:100%;max-width:520px;margin:0;background:#fff;overflow-y:auto;animation:slideup .25s;display:flex;flex-direction:column;}
@keyframes slideup{from{transform:translateY(30px);opacity:.5;}to{transform:translateY(0);opacity:1;}}
.modal-header{background:linear-gradient(135deg,#1a237e,#303f9f);color:#fff;padding:14px 14px 12px;position:sticky;top:0;z-index:5;}
.modal-header .m-title{font-size:16px;font-weight:700;margin-bottom:4px;}
.modal-header .m-sub{font-size:11px;color:rgba(255,255,255,.85);margin-bottom:10px;}
.modal-header .m-row{display:flex;gap:14px;font-size:12px;}
.modal-header .m-row .cell{flex:1;}
.modal-header .m-row .lbl{color:rgba(255,255,255,.7);font-size:10px;margin-bottom:3px;}
.modal-header .m-row .val{font-size:15px;font-weight:700;}
.modal-header .m-row .up{color:#ff8a80;}
.modal-header .m-row .down{color:#b9f6ca;}
.modal-header .close-btn{position:absolute;top:10px;right:10px;width:28px;height:28px;border-radius:50%;border:none;background:rgba(255,255,255,.2);color:#fff;font-size:16px;line-height:1;cursor:pointer;}
.modal-actions{display:flex;gap:8px;padding:10px 12px;background:#fafafa;border-bottom:1px solid #eee;}
.modal-actions .mbtn{flex:1;height:34px;border-radius:17px;border:none;font-size:12px;font-weight:600;cursor:pointer;}
.modal-actions .mbtn.fav{background:#e53935;color:#fff;}
.modal-actions .mbtn.unfav{background:#ffcdd2;color:#c62828;}
.modal-actions .mbtn.del{background:#ef5350;color:#fff;}
.modal-actions .mbtn.refresh{background:#1976d2;color:#fff;}
.modal-actions .mbtn.add{background:#4caf50;color:#fff;}
.chart-wrap{padding:10px 8px;background:#fff;border-bottom:1px solid #eee;}
.chart-title{font-size:12px;font-weight:600;color:#444;margin:0 4px 6px;}
.chart-subtitle{font-size:10px;color:#999;margin:0 4px 6px;}
.chart-canvas{width:100%;height:180px;display:block;}
.history-section{padding:10px 8px;background:#fff;flex:1;}
.history-table{width:100%;border-collapse:collapse;font-size:11px;}
.history-table th{background:#f5f5f5;padding:6px 4px;text-align:right;color:#555;font-weight:600;border-bottom:1px solid #ddd;position:sticky;top:0;}
.history-table th:first-child{text-align:left;}
.history-table td{padding:7px 4px;text-align:right;border-bottom:1px solid #f0f0f0;color:#333;}
.history-table td:first-child{text-align:left;color:#555;font-family:"SF Mono",Menlo,monospace;}
.history-table tr:last-child td{border-bottom:none;}
.history-table .up{color:#e53935;font-weight:600;}
.history-table .down{color:#43a047;font-weight:600;}
.history-table .na{color:#bbb;}
.history-table .nav-cell{color:#1976d2;font-weight:600;}
.history-table .price-cell{color:#f57c00;font-weight:600;}
.h-scroll{max-height:360px;overflow-y:auto;}
.h-hint{font-size:10px;color:#999;padding:6px 4px 2px;text-align:center;}
.auto-refresh-bar{display:flex;align-items:center;justify-content:center;gap:10px;padding:8px;background:#fff;border-bottom:1px solid #eee;font-size:11px;color:#666;}
.auto-refresh-bar select{height:26px;padding:0 8px;border:1px solid #ddd;border-radius:6px;font-size:11px;background:#fff;}
.auto-refresh-bar .toggle{width:40px;height:22px;border-radius:11px;background:#ddd;position:relative;cursor:pointer;transition:background .2s;}
.auto-refresh-bar .toggle.on{background:#4caf50;}
.auto-refresh-bar .toggle::after{content:"";position:absolute;top:2px;left:2px;width:18px;height:18px;border-radius:50%;background:#fff;transition:left .2s;}
.auto-refresh-bar .toggle.on::after{left:20px;}
.history-toggle{display:flex;align-items:center;justify-content:center;gap:8px;padding:8px;background:#fff;border-top:1px solid #eee;font-size:11px;color:#666;border-bottom:1px solid #eee;}
.history-toggle .ht-btn{padding:4px 12px;border-radius:12px;background:#f0f2f5;cursor:pointer;}
.history-toggle .ht-btn.active{background:#1a237e;color:#fff;}
.search-results-header{display:flex;align-items:center;justify-content:space-between;padding:6px 10px;background:#e3f2fd;border-bottom:1px solid #bbdefb;font-size:11px;color:#1976d2;font-weight:600;}
.search-results-header .clear-search{color:#2196f3;text-decoration:underline;font-size:10px;cursor:pointer;}
@media (max-width:380px){.price-box{min-width:54px;}.prem-box{min-width:48px;}.col-header .col-data .sort-h{min-width:54px;}.col-header .col-data .sort-h.prem{min-width:48px;}}
</style>
</head>
<body>
<div id="app">
  <div class="header">
    <div class="title-bar"><div class="title">LOF基金监控</div><div class="list-name">__LIST_NAME__</div></div>
    <div class="search-bar">
      <input class="search-input" id="q" placeholder="输入基金代码或名称搜索" />
      <button class="btn btn-search" id="btn-search">搜索</button>
      <div id="search-mode">
        <span class="search-mode active" data-mode="replace">替换</span>
        <span class="search-mode" data-mode="append">追加</span>
      </div>
      <button class="btn btn-refresh" id="btn-refresh">刷新</button>
    </div>
  </div>
  <div class="auto-refresh-bar">
    <span>自动刷新:</span>
    <div class="toggle" id="auto-toggle"></div>
    <select id="refresh-interval">
      <option value="30">30秒</option>
      <option value="60" selected>1分钟</option>
      <option value="120">2分钟</option>
      <option value="300">5分钟</option>
      <option value="600">10分钟</option>
    </select>
    <span id="refresh-status" style="color:#4caf50;display:none;">刷新中...</span>
  </div>
  <div class="tabs" id="tabs">
    <div class="tab active" data-t="all">全部</div>
    <div class="tab" data-t="lof">LOF</div>
    <div class="tab" data-t="etf">ETF</div>
    <div class="tab" data-t="fav">自选</div>
    <div class="tab" data-t="high">高溢价</div>
    <div class="tab" data-t="low">高折价</div>
  </div>
  <div class="summary">
    <div>共 <span id="cnt">0</span> 只</div>
    <div>最高 <span class="hi" id="hi">--</span></div>
    <div>最低 <span class="lo" id="lo">--</span></div>
    <div class="auto" id="auto-indicator" style="display:none;">● 自动刷新中</div>
  </div>
  <div id="search-results-header" class="search-results-header" style="display:none;">
    <span>搜索结果</span>
    <span class="clear-search" id="clear-search">清除搜索</span>
  </div>
  <div class="col-header">
    <div class="col-fav">★</div>
    <div class="col-info" data-sort="name">基金名称<span class="arrow" data-arrow="name">↕</span></div>
    <div class="col-data">
      <div class="sort-h" data-sort="nav">净值<span class="arrow" data-arrow="nav">↕</span></div>
      <div class="sort-h" data-sort="price">场内现价<span class="arrow" data-arrow="price">↕</span></div>
      <div class="sort-h prem" data-sort="premium">溢价率<span class="arrow" data-arrow="premium">↕</span></div>
    </div>
  </div>
  <div class="content" id="list"></div>
</div>
<div id="toast" class="toast"></div>

<div class="modal-mask" id="modal">
  <div class="modal">
    <div class="modal-header">
      <button class="close-btn" id="modal-close">×</button>
      <div class="m-title" id="m-title">--</div>
      <div class="m-sub" id="m-sub">--</div>
      <div class="m-row">
        <div class="cell"><div class="lbl">单位净值</div><div class="val" id="m-nav">--</div></div>
        <div class="cell"><div class="lbl">场内现价</div><div class="val" id="m-price">--</div></div>
        <div class="cell"><div class="lbl">溢价率</div><div class="val" id="m-prem">--</div></div>
      </div>
    </div>
    <div class="modal-actions">
      <button class="mbtn fav" id="m-fav">加入自选</button>
      <button class="mbtn add" id="m-add">添加到列表</button>
      <button class="mbtn del" id="m-del">删除基金</button>
      <button class="mbtn refresh" id="m-refresh">刷新数据</button>
    </div>
    <div class="chart-wrap">
      <div class="chart-title">净值 vs 场内收盘价（近30日）</div>
      <div class="chart-subtitle" id="m-chart-sub">蓝线: 基金净值 | 橙线: 场内收盘价</div>
      <canvas class="chart-canvas" id="chart-nav"></canvas>
    </div>
    <div class="history-toggle">
      <span class="ht-btn active" data-ht="all">全部日期</span>
      <span class="ht-btn" data-ht="valid">仅完整数据</span>
    </div>
    <div class="chart-wrap">
      <div class="chart-title">历史净值 / 场内收盘价 / 溢价率</div>
      <div class="h-hint" id="m-hint">按日期降序排列 · 溢价率=(收盘价-净值)/净值×100%</div>
      <div class="h-scroll">
        <table class="history-table">
          <thead><tr><th>日期</th><th>净值</th><th>场内收盘</th><th>溢价率</th><th>净值涨跌</th></tr></thead>
          <tbody id="history-body"></tbody>
        </table>
      </div>
    </div>
  </div>
</div>

<script>
var DATA=[], CUR_TAB='all', FAV=[], SORT_KEY='premium', SORT_DIR='desc', CUR_CODE=null;
var SEARCH_MODE='replace', SEARCH_RESULTS=[], IS_SEARCHING=false;
var AUTO_REFRESH=false, REFRESH_INTERVAL=60, REFRESH_TIMER=null;
var HISTORY_VIEW_MODE='all';

try{ var favStr=localStorage.getItem('fav'); FAV=favStr?JSON.parse(favStr):[]; }catch(e){ FAV=[]; }
try{ var autoStr=localStorage.getItem('autoRefresh'); AUTO_REFRESH=autoStr==='true'; }catch(e){}
try{ var intervalStr=localStorage.getItem('refreshInterval'); REFRESH_INTERVAL=parseInt(intervalStr)||60; }catch(e){}
var saveFav=function(){ localStorage.setItem('fav', JSON.stringify(FAV)); };
var saveAutoRefresh=function(){ localStorage.setItem('autoRefresh', AUTO_REFRESH?'true':'false'); };
var saveRefreshInterval=function(){ localStorage.setItem('refreshInterval', REFRESH_INTERVAL.toString()); };
var isFav=function(c){ return FAV.indexOf(c)>-1; };

function toast(msg){
  var t=document.getElementById('toast'); t.textContent=msg; t.classList.add('show');
  clearTimeout(window.__toastT); window.__toastT=setTimeout(function(){ t.classList.remove('show'); }, 1500);
}
function premClass(p, hasVal){ if(!hasVal) return 'na'; if(p>=2) return 'hi'; if(p>0) return 'mid'; if(p>-1) return 'lo'; return 'neg'; }
function numClass(v){ if(v>0) return 'up'; if(v<0) return 'down'; return 'flat'; }

function render(){
  var d=DATA.slice();
  if(CUR_TAB==='fav') d=d.filter(function(f){ return isFav(f.code); });
  if(CUR_TAB==='high') d=d.filter(function(f){ return f.premium>0; });
  if(CUR_TAB==='low') d=d.filter(function(f){ return f.premium<0; });
  if(CUR_TAB==='lof') d=d.filter(function(f){ var c=f.code; return c.startsWith('16')||c.startsWith('501'); });
  if(CUR_TAB==='etf') d=d.filter(function(f){ var c=f.code; return c.startsWith('51')||c.startsWith('159')||c.startsWith('56')||c.startsWith('58'); });
  d.sort(function(a,b){
    var va, vb;
    if(SORT_KEY==='name') return a.name.localeCompare(b.name,'zh-CN')*(SORT_DIR==='asc'?1:-1);
    if(SORT_KEY==='code') return a.code.localeCompare(b.code)*(SORT_DIR==='asc'?1:-1);
    if(SORT_KEY==='nav'){ va=a.nav; vb=b.nav; }
    else if(SORT_KEY==='price'){ va=a.price; vb=b.price; }
    else if(SORT_KEY==='premium'){ va=a.premium; vb=b.premium; }
    else{ va=0; vb=0; }
    var am=(va===undefined||va===null||va===0);
    var bm=(vb===undefined||vb===null||vb===0);
    if(am && !bm) return 1;
    if(!am && bm) return -1;
    if(am && bm) return 0;
    return SORT_DIR==='asc'?va-vb:vb-va;
  });
  document.querySelectorAll('.arrow').forEach(function(el){ el.classList.remove('active'); el.textContent='↕'; });
  var aa=document.querySelector('.arrow[data-arrow="'+SORT_KEY+'"]');
  if(aa){ aa.classList.add('active'); aa.textContent=SORT_DIR==='asc'?'↑':'↓'; }
  var list=document.getElementById('list');
  list.innerHTML='';
  if(!d.length){ list.innerHTML='<div class="empty">暂无数据<br><span style="font-size:11px;color:#bbb;">请搜索添加基金到列表</span></div>'; }
  else{
    for(var i=0;i<d.length;i++){
      var f=d[i];
      var favOn=isFav(f.code);
      var isSearchResult=IS_SEARCHING && SEARCH_RESULTS.indexOf(f.code)>-1;
      var hasPrice=f.price>0;
      var hasNav=f.nav>0;
      var hasBoth=hasPrice&&hasNav;
      var row=document.createElement('div');
      row.className='item'+(favOn?' fav-item':'')+(isSearchResult?' search-result':'');
      row.setAttribute('data-code', f.code);
      var stTag=(f.status.indexOf('暂停')>-1?'stop':(f.status.indexOf('限')>-1?'limit':'ok'));
      var estTag=f.is_estimated?'<span class="tag est">估值</span>':'';
      var searchTag=isSearchResult?'<span class="tag search">搜索</span>':'';
      row.innerHTML =
        '<button class="fav-btn '+(favOn?'active':'')+'" data-code="'+f.code+'" data-act="fav">'+(favOn?'★':'☆')+'</button>'+
        '<div class="info"><div class="name">'+f.name+'</div><div class="info-row"><span class="code">'+f.code+'</span><span class="tag '+stTag+'">'+f.status+'</span>'+estTag+searchTag+'</div></div>'+
        '<div class="data">'+
          '<div class="price-box"><div class="price nav '+(hasNav?'':'miss')+'">'+(hasNav?f.nav.toFixed(4):'--')+'</div><div class="pct '+numClass(f.pct_nav)+'">'+(hasNav?(f.pct_nav>0?'+':'')+f.pct_nav.toFixed(2)+'%':'--')+'</div></div>'+
          '<div class="price-box"><div class="price close '+(hasPrice?'':'miss')+'">'+(hasPrice?f.price.toFixed(4):'--')+'</div><div class="pct '+numClass(f.pct_price)+'">'+(hasPrice?(f.pct_price>0?'+':'')+f.pct_price.toFixed(2)+'%':'--')+'</div></div>'+
          '<div class="prem-box '+premClass(f.premium, hasBoth)+'"><div class="p1">'+(hasBoth?(f.premium>0?'+':'')+f.premium.toFixed(2)+'%':'--')+'</div><div class="p2">'+(hasBoth?(f.premium>0?'溢价':'折价'):'无数据')+'</div></div>'+
        '</div>';
      list.appendChild(row);
    }
  }
  document.getElementById('cnt').textContent=d.length;
  var valids=d.filter(function(f){ return f.nav>0 && f.price>0; });
  if(valids.length){
    var mx=Math.max.apply(null, valids.map(function(f){ return f.premium; }));
    var mn=Math.min.apply(null, valids.map(function(f){ return f.premium; }));
    document.getElementById('hi').textContent=(mx>0?'+':'')+mx.toFixed(2)+'%';
    document.getElementById('lo').textContent=(mn>0?'+':'')+mn.toFixed(2)+'%';
  } else {
    document.getElementById('hi').textContent='--';
    document.getElementById('lo').textContent='--';
  }
  document.getElementById('search-results-header').style.display=IS_SEARCHING?'flex':'none';
}

document.getElementById('list').addEventListener('click', function(e){
  var btn=e.target.closest && e.target.closest('[data-act="fav"]');
  if(btn){
    e.stopPropagation();
    var c=btn.getAttribute('data-code');
    if(isFav(c)){ FAV.splice(FAV.indexOf(c),1); toast('已取消自选'); }
    else{ FAV.push(c); toast('已加入自选'); }
    saveFav(); render();
    return;
  }
  var item=e.target.closest && e.target.closest('.item');
  if(item){ openDetail(item.getAttribute('data-code')); }
});

document.getElementById('clear-search').onclick=function(){
  IS_SEARCHING=false;
  SEARCH_RESULTS=[];
  document.getElementById('q').value='';
  toast('已清除搜索结果');
  render();
};

document.querySelectorAll('#search-mode .search-mode').forEach(function(el){
  el.onclick=function(){
    document.querySelectorAll('#search-mode .search-mode').forEach(function(x){ x.classList.remove('active'); });
    el.classList.add('active');
    SEARCH_MODE=el.getAttribute('data-mode');
    toast('搜索模式: '+ (SEARCH_MODE==='replace'?'替换显示':'追加到列表'));
  };
});

document.getElementById('btn-search').onclick=function(){
  var q=document.getElementById('q').value.trim();
  load(q, true);
};
document.getElementById('q').addEventListener('keydown', function(e){ if(e.key==='Enter') load(e.target.value.trim(), true); });
document.getElementById('btn-refresh').onclick=function(){ load(null, false); };
document.querySelectorAll('#tabs .tab').forEach(function(t){
  t.onclick=function(){
    document.querySelectorAll('#tabs .tab').forEach(function(x){ x.classList.remove('active'); });
    t.classList.add('active'); CUR_TAB=t.getAttribute('data-t'); render();
  };
});
document.querySelectorAll('.col-header [data-sort]').forEach(function(el){
  el.onclick=function(){
    var key=el.getAttribute('data-sort');
    if(SORT_KEY===key) SORT_DIR=SORT_DIR==='asc'?'desc':'asc';
    else{ SORT_KEY=key; SORT_DIR='desc'; }
    render();
  };
});

var modal=document.getElementById('modal');
function openDetail(code){
  var fund=DATA.find(function(f){ return f.code===code; }) || {code:code, name:'--', status:'正常申购', nav:0, price:0, premium:0, pct_nav:0, pct_price:0, nav_date:'', is_estimated:false};
  CUR_CODE=code;
  document.getElementById('m-title').textContent=fund.name;
  var subInfo='代码: '+fund.code+' | 申购: '+fund.status;
  if(fund.nav_date) subInfo+=' | 净值日期: '+fund.nav_date;
  if(fund.is_estimated) subInfo+=' (估值)';
  document.getElementById('m-sub').textContent=subInfo;
  document.getElementById('m-nav').textContent=fund.nav>0?fund.nav.toFixed(4):'--';
  document.getElementById('m-price').textContent=fund.price>0?fund.price.toFixed(4):'--';
  var mp=document.getElementById('m-prem');
  if(fund.nav>0 && fund.price>0){
    var sign=fund.premium>0?'+':'';
    mp.textContent=sign+fund.premium.toFixed(2)+'%';
    mp.className='val '+(fund.premium>0?'up':(fund.premium<0?'down':''));
  } else { mp.textContent='--'; mp.className='val'; }
  var mFav=document.getElementById('m-fav');
  if(isFav(code)){ mFav.textContent='取消自选'; mFav.className='mbtn unfav'; }
  else{ mFav.textContent='加入自选'; mFav.className='mbtn fav'; }
  var mAdd=document.getElementById('m-add');
  var exists=DATA.some(function(f){ return f.code===code; });
  mAdd.style.display=exists?'none':'block';
  modal.classList.add('show');
  document.getElementById('history-body').innerHTML='<tr><td colspan="5" style="text-align:center;color:#999;padding:20px;">加载中...</td></tr>';
  var cnv=document.getElementById('chart-nav');
  var ctx=cnv.getContext('2d');
  ctx.clearRect(0,0,cnv.width,cnv.height);
  ctx.fillStyle='#bbb'; ctx.font='12px sans-serif'; ctx.textAlign='center';
  ctx.fillText('加载中...', cnv.width/2||100, cnv.height/2||90);
  loadDetail(code);
}
function closeModal(){ modal.classList.remove('show'); }
document.getElementById('modal-close').onclick=closeModal;
modal.addEventListener('click', function(e){ if(e.target===modal) closeModal(); });
document.getElementById('m-fav').onclick=function(){
  if(!CUR_CODE) return;
  if(isFav(CUR_CODE)){ FAV.splice(FAV.indexOf(CUR_CODE),1); toast('已取消自选'); }
  else{ FAV.push(CUR_CODE); toast('已加入自选'); }
  saveFav(); render(); openDetail(CUR_CODE);
};
document.getElementById('m-add').onclick=function(){
  if(!CUR_CODE) return;
  fetch('/api/detail?code='+CUR_CODE).then(function(r){ return r.json(); }).then(function(d){
    var exists=DATA.find(function(f){ return f.code===CUR_CODE; });
    if(exists){ toast('该基金已在列表中'); return; }
    var newFund={
      code: CUR_CODE,
      name: d.name || CUR_CODE,
      price: d.kline && d.kline.length ? d.kline[d.kline.length-1].close : 0,
      prev_close: 0,
      nav: d.nav_history && d.nav_history.length ? d.nav_history[d.nav_history.length-1].nav : 0,
      nav_prev: 0,
      status: d.status || '正常申购',
      pct_price: 0,
      pct_nav: 0,
      premium: 0,
      nav_date: d.nav_date || '',
      is_estimated: false
    };
    if(newFund.nav>0 && newFund.price>0){
      newFund.premium = ((newFund.price - newFund.nav) / newFund.nav * 100).toFixed(2);
    }
    DATA.push(newFund);
    toast('已添加到列表');
    render();
    closeModal();
  }).catch(function(){ toast('添加失败'); });
};
document.getElementById('m-del').onclick=function(){
  if(!CUR_CODE) return;
  DATA=DATA.filter(function(f){ return f.code!==CUR_CODE; });
  if(isFav(CUR_CODE)){ FAV.splice(FAV.indexOf(CUR_CODE),1); saveFav(); }
  toast('已删除该基金');
  closeModal(); render();
};
document.getElementById('m-refresh').onclick=function(){
  if(!CUR_CODE) return;
  load(null, false, CUR_CODE);
};

document.querySelectorAll('.history-toggle .ht-btn').forEach(function(el){
  el.onclick=function(){
    document.querySelectorAll('.history-toggle .ht-btn').forEach(function(x){ x.classList.remove('active'); });
    el.classList.add('active');
    HISTORY_VIEW_MODE=el.getAttribute('ht');
    if(CUR_CODE){ loadDetail(CUR_CODE); }
  };
});

function drawDualChart(el, merged){
  var cnv=el;
  var dpr=window.devicePixelRatio||1;
  var rect=cnv.getBoundingClientRect();
  cnv.width=rect.width*dpr; cnv.height=rect.height*dpr;
  var ctx=cnv.getContext('2d');
  ctx.scale(dpr, dpr);
  var w=rect.width, h=rect.height;
  ctx.clearRect(0,0,w,h);
  if(!merged || !merged.length){
    ctx.fillStyle='#bbb'; ctx.font='12px sans-serif'; ctx.textAlign='center';
    ctx.fillText('无历史数据', w/2, h/2); return;
  }
  var validData = merged.filter(function(p){ return p.nav>0 && p.close>0; });
  var displayData = validData.length? validData.slice(0,30) : merged.slice(0,30);
  if(!displayData.length){
    ctx.fillStyle='#bbb'; ctx.font='12px sans-serif'; ctx.textAlign='center';
    ctx.fillText('无完整数据', w/2, h/2); return;
  }
  var series = displayData.slice().reverse();
  var navPoints=[], pricePoints=[];
  series.forEach(function(p){
    if(p.nav>0) navPoints.push({date:p.date, val:p.nav});
    if(p.close>0) pricePoints.push({date:p.date, val:p.close});
  });
  var allVals=[];
  navPoints.forEach(function(p){ allVals.push(p.val); });
  pricePoints.forEach(function(p){ allVals.push(p.val); });
  if(!allVals.length){
    ctx.fillStyle='#bbb'; ctx.font='12px sans-serif'; ctx.textAlign='center';
    ctx.fillText('暂无数据', w/2, h/2); return;
  }
  var mn=Math.min.apply(null, allVals), mx=Math.max.apply(null, allVals);
  var pad=22;
  var innerW=w-pad*2, innerH=h-pad*2;
  var range=mx-mn || 1;
  ctx.strokeStyle='#eee'; ctx.lineWidth=1;
  for(var i=0;i<=4;i++){
    var y=pad+(innerH*i/4);
    ctx.beginPath(); ctx.moveTo(pad, y); ctx.lineTo(w-pad, y); ctx.stroke();
    ctx.fillStyle='#bbb'; ctx.font='10px sans-serif'; ctx.textAlign='left';
    ctx.fillText((mx - (range*i/4)).toFixed(3), 2, y+3);
  }
  var totalPoints = Math.max(navPoints.length, pricePoints.length);
  var step = totalPoints>1? innerW/(totalPoints-1) : innerW;
  if(navPoints.length){
    ctx.strokeStyle='#1976d2'; ctx.lineWidth=1.8; ctx.beginPath();
    navPoints.forEach(function(p, idx){
      var x=pad+idx*step;
      var y=pad+innerH-((p.val-mn)/range*innerH);
      if(idx===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
    });
    ctx.stroke();
  }
  if(pricePoints.length){
    ctx.strokeStyle='#f57c00'; ctx.lineWidth=1.5; ctx.beginPath();
    pricePoints.forEach(function(p, idx){
      var x=pad+idx*step;
      var y=pad+innerH-((p.val-mn)/range*innerH);
      if(idx===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
    });
    ctx.stroke();
    var lp = pricePoints[pricePoints.length-1];
    var lx=pad+(pricePoints.length-1)*step;
    var ly=pad+innerH-((lp.val-mn)/range*innerH);
    ctx.fillStyle='#f57c00'; ctx.beginPath(); ctx.arc(lx, ly, 3, 0, Math.PI*2); ctx.fill();
  }
  ctx.fillStyle='#1976d2'; ctx.fillRect(w-100, 4, 10, 10);
  ctx.fillStyle='#333'; ctx.font='10px sans-serif'; ctx.textAlign='left';
  ctx.fillText('净值', w-86, 13);
  ctx.fillStyle='#f57c00'; ctx.fillRect(w-56, 4, 10, 10);
  ctx.fillStyle='#333'; ctx.fillText('场内收盘', w-42, 13);
}

async function load(q, isSearch, refreshCode){
  document.getElementById('refresh-status').style.display='inline';
  try{
    var url=q?'/api/search?q='+encodeURIComponent(q):'/api/list';
    var r=await fetch(url);
    var data=await r.json();
    if(isSearch && q){
      IS_SEARCHING=true;
      SEARCH_RESULTS=data.map(function(f){ return f.code; });
      if(SEARCH_MODE==='replace'){
        DATA=data;
        toast('搜索到 '+data.length+' 只基金');
      } else {
        var existingCodes={};
        for(var i=0;i<DATA.length;i++){ existingCodes[DATA[i].code]=true; }
        var addedCount=0;
        for(var j=0;j<data.length;j++){
          var f=data[j];
          if(!existingCodes[f.code]){
            DATA.push(f);
            existingCodes[f.code]=true;
            addedCount++;
          }
        }
        toast('搜索到 '+data.length+' 只，新增 '+addedCount+' 只');
      }
    } else if(!q && data){
      IS_SEARCHING=false;
      SEARCH_RESULTS=[];
      var existingCodes={};
      for(var k=0;k<DATA.length;k++){ existingCodes[DATA[k].code]=true; }
      for(var m=0;m<data.length;m++){
        var f=data[m];
        if(!existingCodes[f.code]){ DATA.push(f); }
      }
      toast('刷新完成，共 '+DATA.length+' 只');
    }
    render();
    if(refreshCode){ openDetail(refreshCode); }
  } catch(e){ toast('加载失败'); }
  document.getElementById('refresh-status').style.display='none';
}

async function loadDetail(code){
  try{
    var r=await fetch('/api/detail?code='+code);
    var d=await r.json();
    var tb=document.getElementById('history-body');
    tb.innerHTML='';
    var merged = d.merged || [];
    var displayRows;
    if(HISTORY_VIEW_MODE==='valid'){
      displayRows = merged.filter(function(row){ return row.nav>0 && row.close>0; });
    } else {
      displayRows = merged.slice(0, 40);
    }
    if(!displayRows.length){
      var nh = d.nav_history || [];
      for(var i=nh.length-1;i>=0;i--){
        var it=nh[i];
        var tr=document.createElement('tr');
        var itHas=(it.pct!==undefined&&it.pct!==null&&it.pct!==0);
        var pctTxt = itHas ? ((it.pct>0?'+':'')+it.pct.toFixed(2)+'%') : '--';
        var pctCls = itHas ? (it.pct>0?'up':'down') : 'na';
        tr.innerHTML='<td>'+it.date+'</td><td class="nav-cell">'+(it.nav>0?it.nav.toFixed(4):'--')+'</td><td class="na">--</td><td class="na">--</td><td class="'+pctCls+'">'+pctTxt+'</td>';
        tb.appendChild(tr);
      }
    } else {
      for(var j=0;j<displayRows.length;j++){
        var row=displayRows[j];
        var tr2=document.createElement('tr');
        var hasPct = (row.pct!==undefined&&row.pct!==null&&row.pct!==0);
        var pctTxt2 = hasPct ? ((row.pct>0?'+':'')+row.pct.toFixed(2)+'%') : '--';
        var pctCls2 = hasPct ? (row.pct>0?'up':'down') : 'na';
        var hasBoth = row.nav>0 && row.close>0;
        var premTxt = hasBoth ? ((row.premium>0?'+':'')+row.premium.toFixed(2)+'%') : '--';
        var premCls = hasBoth ? (row.premium>0?'up':(row.premium<0?'down':'na')) : 'na';
        tr2.innerHTML =
          '<td>'+row.date+'</td>'+
          '<td class="nav-cell">'+(row.nav>0?row.nav.toFixed(4):'--')+'</td>'+
          '<td class="price-cell">'+(row.close>0?row.close.toFixed(4):'--')+'</td>'+
          '<td class="'+premCls+'">'+premTxt+'</td>'+
          '<td class="'+pctCls2+'">'+pctTxt2+'</td>';
        tb.appendChild(tr2);
      }
    }
    drawDualChart(document.getElementById('chart-nav'), displayRows);
  } catch(e){ toast('详情加载失败'); }
}

function toggleAutoRefresh(){
  AUTO_REFRESH = !AUTO_REFRESH;
  saveAutoRefresh();
  var toggle=document.getElementById('auto-toggle');
  var indicator=document.getElementById('auto-indicator');
  if(AUTO_REFRESH){
    toggle.classList.add('on');
    indicator.style.display='inline';
    toast('自动刷新已开启 ('+REFRESH_INTERVAL+'秒)');
    scheduleRefresh();
  } else {
    toggle.classList.remove('on');
    indicator.style.display='none';
    if(REFRESH_TIMER){ clearTimeout(REFRESH_TIMER); REFRESH_TIMER=null; }
    toast('自动刷新已关闭');
  }
}

function scheduleRefresh(){
  if(!AUTO_REFRESH) return;
  REFRESH_TIMER = setTimeout(function(){
    load(null, false);
    scheduleRefresh();
  }, REFRESH_INTERVAL * 1000);
}

document.getElementById('auto-toggle').onclick=toggleAutoRefresh;

document.getElementById('refresh-interval').onchange=function(){
  REFRESH_INTERVAL = parseInt(this.value);
  saveRefreshInterval();
  if(AUTO_REFRESH){
    if(REFRESH_TIMER){ clearTimeout(REFRESH_TIMER); }
    scheduleRefresh();
    toast('刷新间隔已设为 '+REFRESH_INTERVAL+'秒');
  }
};

document.getElementById('refresh-interval').value=REFRESH_INTERVAL;
if(AUTO_REFRESH){
  document.getElementById('auto-toggle').classList.add('on');
  document.getElementById('auto-indicator').style.display='inline';
  scheduleRefresh();
}

load(null, false);
</script>
</body>
</html>
'''

HTML = HTML_CONTENT.replace('__LIST_NAME__', LIST_NAME)


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send_json(self, obj):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/' or self.path.startswith('/index'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML.encode('utf-8'))
            return

        if self.path.startswith('/api/list'):
            self._send_json(SIM_DATA)
            return

        if self.path.startswith('/api/search'):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            query = params.get('q', [''])[0]
            query = urllib.parse.unquote(query).strip()
            if not query:
                self._send_json(SIM_DATA)
                return
            basics = search_funds_online(query, limit=20)
            results = []
            if basics:
                for b in basics:
                    results.append(enrich_fund(b))
            self._send_json(results)
            return

        if self.path.startswith('/api/detail'):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            code = params.get('code', [''])[0]
            if not code:
                self._send_json({'history': []})
                return
            data = fetch_full_history(code, days=90)
            self._send_json(data)
            return

        self.send_error(404)


def main():
    print('LOF基金监控 v1.7.1 启动, 端口 8888')
    try:
        http.server.HTTPServer(('0.0.0.0', 8888), Handler).serve_forever()
    except OSError:
        print('端口8888被占用, 尝试 8080...')
        try:
            http.server.HTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
        except OSError:
            print('尝试 8000...')
            http.server.HTTPServer(('0.0.0.0', 8000), Handler).serve_forever()


if __name__ == '__main__':
    main()
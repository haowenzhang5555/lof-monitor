#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# LOF基金监控 v1.8.1

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


def _strip_html_tags(text):
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&[a-zA-Z]+;', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def fetch_fund_status(code):
    status = '正常申购'
    try:
        text = _http_get('http://fundf10.eastmoney.com/jbxx_%s.html' % code, timeout=6)
        if not text:
            return status

        plain = _strip_html_tags(text)

        sg_value = ''
        sg_match = re.search(r'申购状态[\s:：]*([^\s\u3000]{1,20})', plain)
        if not sg_match:
            sg_match = re.search(r'(?:申购|开放申购|开放)[\s:：]*([^\s\u3000]{1,20}?)(?:申购|状态|赎回|$)', plain)
        if sg_match:
            sg_value = sg_match.group(1).strip()
            sg_value = re.sub(r'[。，、；：].*$', '', sg_value)

        limit_value = ''
        limit_num = None
        limit_keywords = ['限大额', '单日限额', '单用户限额', '单户限额', '大额申购', '限额', '限购']
        for kw in limit_keywords:
            pat = kw + r'[\s:：]*([^\s\u3000]{1,30})'
            lm = re.search(pat, plain)
            if lm:
                limit_value = lm.group(1).strip()
                limit_value = re.sub(r'[。，、；：].*$', '', limit_value)
                num_match = re.search(r'(\d+(?:\.\d+)?)\s*(万|亿|元|千|百)?', limit_value)
                if num_match:
                    num = float(num_match.group(1))
                    unit = num_match.group(2) or ''
                    if unit == '万':
                        limit_num = int(num * 10000)
                    elif unit == '亿':
                        limit_num = int(num * 100000000)
                    elif unit == '千':
                        limit_num = int(num * 1000)
                    else:
                        try:
                            limit_num = int(num)
                        except Exception:
                            limit_num = None
                break

        if '暂停' in sg_value or '停止' in sg_value or '封闭' in sg_value or sg_value == '暂停':
            status = '暂停申购'
        elif limit_num is not None:
            if limit_num >= 100000000:
                yi = limit_num // 100000000
                if limit_num % 100000000 == 0:
                    status = '限%d亿' % yi
                else:
                    wan = (limit_num % 100000000) // 10000
                    if wan > 0:
                        status = '限%d亿%d万' % (yi, wan)
                    else:
                        status = '限%d亿' % yi
            elif limit_num >= 10000:
                status = '限%d万' % (limit_num // 10000)
            elif limit_num >= 1000:
                status = '限%d元' % limit_num
            else:
                status = '限大额'
        elif '限大额' in plain or '大额限购' in plain or '暂停大额' in plain:
            status = '限大额'
        elif '开放' in sg_value or '正常' in sg_value or sg_value == '' or '开放申购' in plain:
            status = '正常申购'
        elif sg_value:
            status = sg_value[:10]
        else:
            status = '正常申购'
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

    merged_all = []
    all_dates = set(nav_map.keys()) | set(kline_map.keys())
    for d in sorted(all_dates, reverse=True):
        nav_item = nav_map.get(d)
        nav = nav_item['nav'] if nav_item else 0
        pct = nav_item.get('pct', 0) if nav_item else 0
        close = kline_map.get(d, 0) or 0
        premium = 0.0
        if nav > 0 and close > 0:
            premium = round((close - nav) / nav * 100, 2)
        merged_all.append({
            'date': d,
            'nav': round(nav, 4) if nav > 0 else 0,
            'close': round(close, 4) if close > 0 else 0,
            'premium': premium,
            'pct': round(pct, 2) if pct else 0
        })

    merged = merged_all[:30]

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
html,body{height:100%;font-family:-apple-system,Helvetica,"PingFang SC",Microsoft YaHei,sans-serif;background:#f0f2f5;}
#app{display:flex;flex-direction:column;height:100%;}
.header{background:linear-gradient(135deg,#1a237e,#303f9f);padding:10px 10px 12px;flex-shrink:0;box-shadow:0 2px 8px rgba(0,0,0,.12);}
.title-bar{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;gap:10px;}
.title{color:#fff;font-size:15px;font-weight:700;letter-spacing:1px;}
.title-bar .left-group{display:flex;align-items:center;gap:8px;}
.version{color:#ffd54f;font-size:10px;font-weight:500;opacity:.85;}
.list-name{color:#ffd54f;font-size:11px;font-weight:600;background:rgba(255,213,79,.18);padding:3px 10px;border-radius:12px;}
.search-bar{display:flex;align-items:center;gap:4px;flex-wrap:nowrap;min-width:0;}
.search-input{flex:1;max-width:120px;height:28px;padding:0 10px;border-radius:14px;border:none;font-size:12px;background:rgba(255,255,255,.96);color:#222;outline:none;}
.btn{height:28px;padding:0 10px;border-radius:14px;border:none;font-size:11px;font-weight:600;cursor:pointer;flex-shrink:0;transition:transform .1s;}
.btn:active{transform:scale(.94);}
.btn-search{background:#ffd54f;color:#1a237e;}
.btn-refresh{background:rgba(255,255,255,.22);color:#fff;padding:0 8px;}
.btn-auto{background:#4caf50;color:#fff;padding:0 8px;font-size:10px;border-radius:14px;min-width:56px;}
.btn-auto.on{background:#ff9800;}
.refresh-select{height:28px;padding:0 6px;border:none;border-radius:10px;font-size:10px;background:rgba(255,255,255,.9);color:#333;outline:none;min-width:58px;}
.search-results-wrap{background:#fff;border-bottom:2px solid #1976d2;padding:6px;box-shadow:0 2px 8px rgba(25,118,210,.15);}
.search-results-header{display:flex;justify-content:space-between;align-items:center;padding:8px 12px;background:linear-gradient(135deg,#1976d2,#42a5f5);border-radius:8px;margin-bottom:8px;}
.search-results-header span:first-child{color:#fff;font-size:13px;font-weight:600;}
.search-results-header .clear-search{color:rgba(255,255,255,.9);font-size:11px;text-decoration:underline;cursor:pointer;padding:2px 6px;border-radius:4px;}
.search-results-header .clear-search:active{background:rgba(255,255,255,.2);}
.search-results-content{display:flex;flex-wrap:wrap;gap:6px;}
.search-result-item{display:flex;align-items:center;gap:8px;padding:8px 12px;background:linear-gradient(135deg,#f5f9ff,#e3f2fd);border:1px solid #90caf9;border-radius:10px;cursor:pointer;transition:all .2s;min-width:200px;}
.search-result-item:active{background:#bbdefb;transform:scale(0.98);}
.search-result-item .s-code{font-size:12px;color:#1565c0;font-weight:700;font-family:monospace;}
.search-result-item .s-name{font-size:13px;color:#222;flex:1;}
.search-result-item .s-add{font-size:11px;color:#fff;padding:3px 10px;background:#4caf50;border-radius:12px;margin-left:auto;}
.search-result-item .s-add.exist{background:#9e9e9e;color:#fff;}
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
.fav-btn{width:26px;height:26px;border-radius:50%;border:none;background:#f5f5f5;color:#999;font-size:13px;cursor:pointer;flex-shrink:0;display:flex;align-items:center;justify-content:center;transition:all .15s;}
.fav-btn.active{background:#ffebee;color:#e53935;}
.info{flex:1;min-width:0;}
.name{font-size:13px;font-weight:600;color:#212121;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.info-row{display:flex;align-items:center;gap:8px;margin-top:3px;flex-wrap:wrap;}
.code{font-size:11px;color:#757575;font-family:"SF Mono","Menlo",monospace;}
.tag{font-size:10px;padding:1px 6px;border-radius:3px;font-weight:500;}
.tag.stop{background:#e53935;color:#fff;}
.tag.limit{background:#f57c00;color:#fff;}
.tag.ok{background:#43a047;color:#fff;}
.tag.est{background:#1976d2;color:#fff;font-size:9px;}
.tag.srch{background:#ffd600;color:#6d4c00;font-size:9px;}
.item.search-item{background:linear-gradient(90deg,#fff9e6 0%,#fff 8px,#fff 100%);}
.item.search-item::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:#ffd600;}
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
.chart-canvas{width:100%;height:180px;display:block;cursor:crosshair;}
.chart-tooltip{position:absolute;background:rgba(33,33,33,.92);color:#fff;padding:6px 10px;border-radius:4px;font-size:11px;line-height:1.5;pointer-events:none;z-index:10;white-space:nowrap;}
.chart-tooltip .t-date{color:#ffd54f;font-weight:600;margin-bottom:3px;}
.chart-tooltip .t-row{display:flex;justify-content:space-between;gap:14px;}
.chart-tooltip .t-lbl{color:rgba(255,255,255,.7);}
.chart-tooltip .t-nav{color:#64b5f6;font-weight:600;}
.chart-tooltip .t-price{color:#ffb74d;font-weight:600;}
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
@media (max-width:380px){.price-box{min-width:54px;}.prem-box{min-width:48px;}.col-header .col-data .sort-h{min-width:54px;}.col-header .col-data .sort-h.prem{min-width:48px;}}
</style>
</head>
<body>
<div id="app">
  <div class="header">
    <div class="title-bar"><div class="left-group"><div class="title">LOF基金监控</div><span class="version">v1.8.2</span></div><div class="list-name">__LIST_NAME__</div></div>
    <div class="search-bar">
      <input class="search-input" id="q" placeholder="输入基金代码或名称搜索" />
      <button class="btn btn-search" id="btn-search">搜索</button>
      <button class="btn btn-refresh" id="btn-refresh">刷新</button>
      <button class="btn btn-auto" id="btn-auto">自动刷新</button>
      <select id="refresh-interval" class="refresh-select">
        <option value="10">10秒</option>
        <option value="20">20秒</option>
        <option value="30" selected>30秒</option>
        <option value="60">1分钟</option>
        <option value="300">5分钟</option>
      </select>
      <span id="refresh-status" style="color:#4caf50;display:none;font-size:10px;">刷新中...</span>
    </div>
  </div>
  <div class="search-results-wrap" id="search-results-wrap" style="display:none;">
    <div class="search-results-header">
      <span>搜索结果</span>
      <span class="clear-search" id="clear-search">清除</span>
    </div>
    <div class="search-results-content" id="search-results-content"></div>
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
var DATA=[], CUR_TAB='all', FAV=[], SORT_KEY='premium', SORT_DIR='desc', CUR_CODE=null, SEARCH_CODES=[];
var AUTO_REFRESH=false, REFRESH_INTERVAL=30, REFRESH_TIMER=null;

try{ var favStr=localStorage.getItem('fav'); FAV=favStr?JSON.parse(favStr):[]; }catch(e){ FAV=[]; }
try{ var autoStr=localStorage.getItem('autoRefresh'); AUTO_REFRESH=autoStr==='true'; }catch(e){}
try{ var intervalStr=localStorage.getItem('refreshInterval'); REFRESH_INTERVAL=parseInt(intervalStr)||30; }catch(e){}
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
    var aInSearch = SEARCH_CODES.indexOf(a.code)>-1;
    var bInSearch = SEARCH_CODES.indexOf(b.code)>-1;
    if(aInSearch && !bInSearch) return -1;
    if(!aInSearch && bInSearch) return 1;
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
      var hasPrice=f.price>0;
      var hasNav=f.nav>0;
      var hasBoth=hasPrice&&hasNav;
      var isSearch=SEARCH_CODES.indexOf(f.code)>-1;
      var row=document.createElement('div');
      row.className='item'+(favOn?' fav-item':'')+(isSearch?' search-item':'');
      row.setAttribute('data-code', f.code);
      var stTag=(f.status.indexOf('暂停')>-1?'stop':(f.status.indexOf('限')>-1?'limit':'ok'));
      var estTag=f.is_estimated?'<span class="tag est">估值</span>':'';
      var searchTag=isSearch?'<span class="tag srch">搜索</span>':'';
      row.innerHTML =
        '<button class="fav-btn '+(favOn?'active':'')+'" data-code="'+f.code+'" data-act="fav">'+(favOn?'★':'☆')+'</button>'+
        '<div class="info"><div class="name">'+f.name+'</div><div class="info-row"><span class="code">'+f.code+'</span>'+searchTag+'<span class="tag '+stTag+'">'+f.status+'</span>'+estTag+'</div></div>'+
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

document.getElementById('btn-search').onclick=function(){
  var q=document.getElementById('q').value.trim();
  if(!q){ clearSearch(); return; }
  fetch('/api/search?q='+encodeURIComponent(q)).then(function(r){ return r.json(); }).then(function(results){
    if(!results || !results.length){
      toast('未找到匹配的基金');
      return;
    }
    SEARCH_CODES=[];
    var existingMap={};
    for(var xi=0;xi<DATA.length;xi++){ existingMap[DATA[xi].code]=xi; }
    for(var yj=0;yj<results.length;yj++){
      var ff=results[yj];
      SEARCH_CODES.push(ff.code);
      var eidx=existingMap[ff.code];
      if(eidx!==undefined){ DATA[eidx]=ff; }
      else{ DATA.push(ff); }
    }
    render();
    toast('搜索到 '+results.length+' 只基金，已在列表中置顶');
  }).catch(function(){ toast('搜索失败'); });
};
function clearSearch(){
  document.getElementById('q').value='';
  SEARCH_CODES=[];
  render();
}
document.getElementById('clear-search').onclick=clearSearch;
document.getElementById('q').addEventListener('keydown', function(e){
  if(e.key==='Enter'){
    var q=e.target.value.trim();
    if(!q) clearSearch();
    else document.getElementById('btn-search').click();
  }
});
document.getElementById('search-results-content').addEventListener('click', function(e){
  var item=e.target.closest && e.target.closest('.search-result-item');
  if(item){
    var code=item.getAttribute('data-code');
    fetch('/api/detail?code='+code).then(function(r){ return r.json(); }).then(function(d){
      var existsIdx=DATA.findIndex(function(f){ return f.code===code; });
      var newFund={
        code: code,
        name: d.name || code,
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
        newFund.premium = ((newFund.price - newFund.nav) / newFund.nav * 100);
      }
      if(existsIdx>=0){
        DATA[existsIdx]=newFund;
        toast('已更新基金 '+code);
      } else {
        DATA.push(newFund);
        toast('已添加基金 '+code);
      }
      render();
      clearSearch();
    });
  }
});
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

function drawDualChart(el, merged){
  var cnv=el;
  var dpr=window.devicePixelRatio||1;
  var rect=cnv.getBoundingClientRect();
  cnv.width=rect.width*dpr; cnv.height=rect.height*dpr;
  var ctx=cnv.getContext('2d');
  ctx.scale(dpr, dpr);
  var w=rect.width, h=rect.height;
  ctx.clearRect(0,0,w,h);

  // 设置数据和计算参数
  var validData = merged && merged.length ? merged.filter(function(p){ return p.nav>0 || p.close>0; }) : [];
  var displayData = validData.slice(0,30);
  var hasData = displayData.length>0;

  var seriesData = [];
  var navPoints=[], pricePoints=[];
  var mn=0, mx=1, pad=22, innerW=w-pad*2, innerH=h-pad*2, range=1, step=innerW, totalPoints=0;

  if(hasData){
    seriesData = displayData.slice().reverse();
    seriesData.forEach(function(p){
      if(p.nav>0) navPoints.push({date:p.date, val:p.nav});
      if(p.close>0) pricePoints.push({date:p.date, val:p.close});
    });
    var allVals=[];
    navPoints.forEach(function(p){ allVals.push(p.val); });
    pricePoints.forEach(function(p){ allVals.push(p.val); });
    if(allVals.length){
      mn=Math.min.apply(null, allVals);
      mx=Math.max.apply(null, allVals);
      range=mx-mn || 1;
      totalPoints = Math.max(navPoints.length, pricePoints.length, 1);
      step = totalPoints>1? innerW/(totalPoints-1) : innerW;
    } else {
      hasData=false;
    }
  }

  // 基础绘制函数
  function drawBase(){
    ctx.clearRect(0,0,w,h);
    if(!hasData){
      ctx.fillStyle='#bbb'; ctx.font='12px sans-serif'; ctx.textAlign='center';
      ctx.fillText('无历史数据', w/2, h/2);
      return;
    }
    // 网格线和刻度
    ctx.strokeStyle='#eee'; ctx.lineWidth=1;
    for(var i=0;i<=4;i++){
      var y=pad+(innerH*i/4);
      ctx.beginPath(); ctx.moveTo(pad, y); ctx.lineTo(w-pad, y); ctx.stroke();
      ctx.fillStyle='#bbb'; ctx.font='10px sans-serif'; ctx.textAlign='left';
      ctx.fillText((mx - (range*i/4)).toFixed(3), 2, y+3);
    }
    // 净值线
    if(navPoints.length){
      ctx.strokeStyle='#1976d2'; ctx.lineWidth=1.8; ctx.beginPath();
      navPoints.forEach(function(p, idx){
        var x=pad+idx*step;
        var y=pad+innerH-((p.val-mn)/range*innerH);
        if(idx===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
      });
      ctx.stroke();
    }
    // 价格线
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
    // 图例
    ctx.fillStyle='#1976d2'; ctx.fillRect(w-100, 4, 10, 10);
    ctx.fillStyle='#333'; ctx.font='10px sans-serif'; ctx.textAlign='left';
    ctx.fillText('净值', w-86, 13);
    ctx.fillStyle='#f57c00'; ctx.fillRect(w-56, 4, 10, 10);
    ctx.fillStyle='#333'; ctx.fillText('场内收盘', w-42, 13);
  }

  // 创建/获取悬浮提示框
  var tooltip = cnv.parentNode.querySelector('.chart-tooltip');
  if(!tooltip){
    tooltip = document.createElement('div');
    tooltip.className='chart-tooltip';
    tooltip.style.display='none';
    cnv.parentNode.style.position='relative';
    cnv.parentNode.appendChild(tooltip);
  }

  function hideTooltip(){
    tooltip.style.display='none';
  }

  function showTooltip(mouseX, mouseY){
    if(!hasData) return;
    var relX = mouseX - rect.left;
    var relY = mouseY - rect.top;
    if(relX<pad || relX>w-pad || relY<pad || relY>h-pad){
      hideTooltip();
      drawBase();
      return;
    }
    // 找到最近的点索引
    var idxFloat = (relX-pad)/step;
    var idx = Math.round(idxFloat);
    idx = Math.max(0, Math.min(totalPoints-1, idx));
    var targetDate = seriesData[idx] ? seriesData[idx].date : '';
    var navVal = null, priceVal = null;
    for(var ni=0;ni<navPoints.length;ni++){
      if(navPoints[ni].date===targetDate){ navVal=navPoints[ni].val; break; }
    }
    for(var pi=0;pi<pricePoints.length;pi++){
      if(pricePoints[pi].date===targetDate){ priceVal=pricePoints[pi].val; break; }
    }
    if(navVal===null && priceVal===null){
      hideTooltip();
      drawBase();
      return;
    }
    // 重绘基础图
    drawBase();
    // 绘制十字线
    var crossX = pad+idx*step;
    var crossY = relY;
    ctx.strokeStyle='rgba(120,120,120,.55)';
    ctx.lineWidth=1;
    ctx.setLineDash([3,3]);
    ctx.beginPath(); ctx.moveTo(crossX, pad); ctx.lineTo(crossX, h-pad); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(pad, crossY); ctx.lineTo(w-pad, crossY); ctx.stroke();
    ctx.setLineDash([]);
    // 在交点画小圆点
    if(navVal!==null){
      var ny=pad+innerH-((navVal-mn)/range*innerH);
      ctx.fillStyle='#1976d2'; ctx.beginPath(); ctx.arc(crossX, ny, 4, 0, Math.PI*2); ctx.fill();
    }
    if(priceVal!==null){
      var py=pad+innerH-((priceVal-mn)/range*innerH);
      ctx.fillStyle='#f57c00'; ctx.beginPath(); ctx.arc(crossX, py, 4, 0, Math.PI*2); ctx.fill();
    }
    // 显示悬浮框
    var premHtml='';
    if(navVal!==null && priceVal!==null){
      var prem = ((priceVal - navVal) / navVal * 100);
      var premSign = prem>0?'+':'';
      var premColor = prem>0?'#ff5252':(prem<0?'#4caf50':'#bbb');
      premHtml = '<div class="t-row" style="border-top:1px solid rgba(255,255,255,.15);padding-top:3px;margin-top:2px;"><span class="t-lbl" style="color:rgba(255,255,255,.75);">溢价率</span><span style="color:'+premColor+';font-weight:700;">'+premSign+prem.toFixed(2)+'%</span></div>';
    }
    tooltip.innerHTML =
      '<div class="t-date">'+targetDate+'</div>'+
      (navVal!==null?'<div class="t-row"><span class="t-lbl">净值</span><span class="t-nav">'+navVal.toFixed(4)+'</span></div>':'')+
      (priceVal!==null?'<div class="t-row"><span class="t-lbl">场内收盘</span><span class="t-price">'+priceVal.toFixed(4)+'</span></div>':'')+
      premHtml;
    tooltip.style.display='block';
    var tipRect = tooltip.getBoundingClientRect();
    var tipW = tipRect.width, tipH = tipRect.height;
    var tx = crossX + 10;
    var ty = crossY - tipH/2;
    if(tx+tipW > w-4) tx = crossX - tipW - 10;
    if(ty<0) ty=2;
    if(ty+tipH > h) ty=h-tipH-2;
    tooltip.style.left=tx+'px';
    tooltip.style.top=ty+'px';
  }

  // 绑定事件
  cnv.onmousemove = function(e){
    showTooltip(e.clientX, e.clientY);
  };
  cnv.onmouseleave = function(){
    hideTooltip();
    drawBase();
  };

  // 初始绘制
  drawBase();
}

async function load(q, isSearch, refreshCode){
  document.getElementById('refresh-status').style.display='inline';
  try{
    var url=q?'/api/search?q='+encodeURIComponent(q):'/api/list';
    var r=await fetch(url);
    var data=await r.json();
    if(data && data.length){
      var existingMap={};
      for(var i=0;i<DATA.length;i++){ existingMap[DATA[i].code]=i; }
      var updated=0, added=0;
      for(var j=0;j<data.length;j++){
        var f=data[j];
        var idx=existingMap[f.code];
        if(idx!==undefined){
          DATA[idx]=f;
          updated++;
        } else {
          DATA.push(f);
          existingMap[f.code]=DATA.length-1;
          added++;
        }
      }
      toast(isSearch&&q?('搜索到 '+data.length+' 只，新增 '+added+' 只，更新 '+updated+' 只'):('刷新完成，共 '+DATA.length+' 只'));
    } else {
      toast(isSearch&&q?'未找到匹配基金':'暂无数据');
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
    var displayRows = merged.slice(0, 30);
    if(!displayRows.length){
      tb.innerHTML='<tr><td colspan="5" style="text-align:center;color:#999;padding:20px;">暂无历史数据</td></tr>';
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
  var btn=document.getElementById('btn-auto');
  var indicator=document.getElementById('auto-indicator');
  if(AUTO_REFRESH){
    btn.classList.add('on');
    btn.textContent='自动刷新中';
    indicator.style.display='inline';
    toast('自动刷新已开启 ('+REFRESH_INTERVAL+'秒)');
    scheduleRefresh();
  } else {
    btn.classList.remove('on');
    btn.textContent='自动刷新';
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

document.getElementById('btn-auto').onclick=toggleAutoRefresh;

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
  document.getElementById('btn-auto').classList.add('on');
  document.getElementById('btn-auto').textContent='自动刷新中';
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
    print('LOF基金监控 v1.8.0 启动, 端口 8888')
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
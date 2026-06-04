# ============================================================
# LOF基金溢价实时监控系统 - 后端
# Version: 1.2.0
# ============================================================

import os
import re
import ssl
import json
import urllib.request
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

# 缓存
_cache = {}
_cache_purchase = {}
_cache_trend = {}

def cache_get(cache_dict, key, ttl=20):
    entry = cache_dict.get(key)
    if entry and entry['expires_at'] > datetime.now():
        return entry['data']
    return None

def cache_set(cache_dict, key, data, ttl=20):
    cache_dict[key] = {'data': data, 'expires_at': datetime.now() + timedelta(seconds=ttl)}

def http_get(url, referer='', timeout=8):
    headers = {'User-Agent': UA}
    if referer:
        headers['Referer'] = referer
    req = urllib.request.Request(url, headers=headers)
    return urllib.request.urlopen(req, timeout=timeout, context=ssl_ctx)

def get_market(code):
    return 'sh' if code.startswith('5') else 'sz'

# ============================================================
# 数据源1：新浪实时行情
# ============================================================

def fetch_price_from_sina(code):
    """从新浪获取ETF实时价格"""
    market = get_market(code)
    try:
        url = f'https://hq.sinajs.cn/list={market}{code}'
        resp = http_get(url, referer='https://finance.sina.com.cn/', timeout=3)
        text = resp.read().decode('gbk')
        m = re.search(r'"(.+)"', text)
        if not m:
            return None
        parts = m.group(1).split(',')
        if len(parts) < 9:
            return None
        return {
            'name': parts[0],
            'price': float(parts[3]) if parts[3] else 0,
            'prev_close': float(parts[2]) if parts[2] else 0,
            'high': float(parts[4]) if parts[4] else 0,
            'low': float(parts[5]) if parts[5] else 0,
            'open': float(parts[1]) if parts[1] else 0,
            'volume': int(float(parts[8])) if parts[8] else 0,
            'date': parts[30] if len(parts) > 30 else '',
            'time': parts[31] if len(parts) > 31 else '',
        }
    except Exception as e:
        print(f'sina({code}) error: {e}')
        return None

# ============================================================
# 数据源2：天天基金估值（NAV + 实时估值）
# ============================================================

def fetch_nav_from_fundgz(code):
    """从天天基金获取基金估值"""
    try:
        url = f'https://fundgz.1234567.com.cn/js/{code}.js'
        resp = http_get(url, referer='https://fund.eastmoney.com/', timeout=3)
        text = resp.read().decode()
        m = re.search(r'jsonpgz\((.+)\)', text)
        if not m:
            return None
        data = json.loads(m.group(1))
        nav = float(data.get('dwjz', 0))
        estimate = float(data.get('gsz', 0))
        return {
            'name': data.get('name', ''),
            'nav': nav,
            'nav_date': data.get('jzrq', ''),
            'estimate_value': estimate,
            'estimate_change': float(data.get('gszzl', 0)),
            'estimate_time': data.get('gztime', ''),
        }
    except Exception as e:
        print(f'fundgz({code}) error: {e}')
        return None

# ============================================================
# 数据源3：LSJZList API（NAV + 申购状态）
# ============================================================

def fetch_fund_info_lsjz(code):
    """从东方财富LSJZList接口获取净值和申购状态"""
    try:
        url = f'https://api.fund.eastmoney.com/f10/lsjz?callback=jQuery&fundCode={code}&pageIndex=1&pageSize=1'
        resp = http_get(url, referer='https://fundf10.eastmoney.com/', timeout=5)
        text = resp.read().decode()
        m = re.search(r'\((.+)\)', text)
        if not m:
            return None
        data = json.loads(m.group(1))
        lsjz = data.get('Data', {}).get('LSJZList', [])
        if not lsjz:
            return None
        item = lsjz[0]
        return {
            'nav': float(item.get('DWJZ', 0)),
            'nav_date': item.get('FSRQ', ''),
            'sgzt': item.get('SGZT', ''),
        }
    except Exception as e:
        print(f'lsjz({code}) error: {e}')
        return None

# ============================================================
# 申购限额抓取
# ============================================================

def fetch_purchase_limit(code, purchase_status):
    """从天天基金详情页抓取申购限额"""
    try:
        url = f'https://fund.eastmoney.com/{code}.html'
        resp = http_get(url, referer='https://fund.eastmoney.com/', timeout=6)
        html = resp.read(80000).decode(errors='ignore')

        # 查找所有含"限"字的区块
        purchase_section = ''
        idx = html.find('限')
        if idx > 0:
            purchase_section = html[max(0,idx-300):idx+600]

        if not purchase_section:
            purchase_section = html

        # 查找限额数字，优先匹配显式标注的单位
        # 如：单日累计购买上限50.00万元 → 50万
        # 如：限大额(单日累计购买上限50.00万元) → 50万
        # 如：单日申购限额10万元
        patterns = [
            (r'上限[^\d]*?([\d,，.]+)\s*万', 10000),
            (r'限[^\d]*?([\d,，.]+)\s*万', 10000),
            (r'限[^\d]*?([\d,，.]+)\s*元', 1),
            (r'上限[^\d]*?([\d,，.]+)\s*元', 1),
            (r'([\d,，.]+)\s*万.*?(?:限|上)', 10000),
            (r'单日[^\d]*?([\d,，.]+)\s*万', 10000),
            (r'单日[^\d]*?([\d,，.]+)\s*元', 1),
        ]

        limit = 0
        for pat, unit in patterns:
            matches = re.findall(pat, purchase_section)
            for m in matches:
                try:
                    val = float(m.replace(',', '').replace('，', ''))
                    total = int(val * unit)
                    if total > limit:
                        limit = total
                except:
                    pass

        return limit
    except Exception as e:
        print(f'purchase_limit({code}) error: {e}')
        return 0

# ============================================================
# 申购状态映射
# ============================================================

def map_purchase_status(sgzt):
    if not sgzt:
        return '开放申购'
    sgzt = sgzt.strip()
    if '暂停' in sgzt or '停止' in sgzt:
        return '暂停申购'
    if '限' in sgzt or '额' in sgzt:
        return '限额申购'
    if '场内' in sgzt or '买入' in sgzt:
        return '开放申购'
    return '开放申购'

# ============================================================
# 分时数据
# ============================================================

def fetch_intraday_trend(code):
    """从新浪获取5分钟K线"""
    cache_key = f'trend_{code}'
    cached = cache_get(_cache_trend, cache_key, 60)
    if cached:
        return cached

    market = get_market(code)
    try:
        url = f'https://quotes.sina.cn/cn/api/jsonp_v2.php/data/CN_MarketDataService.getKLineData?symbol={market}{code}&scale=5&datalen=60'
        resp = http_get(url, referer='https://finance.sina.com.cn/', timeout=5)
        text = resp.read().decode()
        m = re.search(r'data\((\[.*\])\)', text, re.DOTALL)
        if not m:
            return None
        bars = json.loads(m.group(1))
        today = datetime.now().strftime('%Y-%m-%d')
        result = []
        for bar in bars:
            if bar['day'].startswith(today):
                result.append({
                    'time': bar['day'].split(' ')[-1][:5],
                    'price': float(bar['close']),
                })
        result = result if result else None
        cache_set(_cache_trend, cache_key, result, 120)
        return result
    except Exception as e:
        print(f'trend({code}) error: {e}')
        return None

# ============================================================
# 基金代码范围判断
# ============================================================

def is_fund_code(code):
    """判断代码是否为已知的基金代码格式（非股票）"""
    if not code or len(code) < 6:
        return False
    code = code.zfill(6)
    # LOF: 16xxxx, 501xxx, 164xxx, 161xxx, 162xxx
    # ETF: 159xxx, 51xxxx, 588xxx
    fund_prefixes = ['16', '501', '164', '161', '162', '159', '51', '588']
    return any(code.startswith(p) for p in fund_prefixes)


def looks_like_stock(name, premium, code):
    """通过名称和溢价率判断是否为股票"""
    if not name:
        return True
    # 名称中包含基金关键词的视为基金
    fund_kw = ['基金', 'ETF', 'LOF', '指数', '货币', '债券', '债', '成长', '优选',
               '红利', '价值', '量化', '沪港', '港股', '联接', '增强', '纯债']
    for kw in fund_kw:
        if kw in name:
            return False
    # 溢价率极端（超过50%）可能是股票误识别
    if abs(premium) > 50:
        return True
    return False


# ============================================================
# 基金列表
# ============================================================

PRESET_FUNDS = [
    "513100", "513500", "513520", "159941", "513050", "159605",
    "510300", "510050", "510500", "159915", "159949", "512880",
    "512760", "513030", "159920", "510880", "518880", "512480",
    "159995", "513090", "512660", "159601", "159845",
    "160416", "162411", "159992", "513130", "513010", "513300",
    "515030", "515790", "515050", "512010", "512800", "512690",
    "159996", "513150", "513220", "513880", "513980", "159632",
    "159607", "515880", "512100",
    # LOF套利品种
    "501225", "501312", "501018", "501021", "501078",
    "164906", "164205",
    "161129", "161027", "161725", "160632", "162703", "160706",
    "166009", "166023",
]

fund_database = PRESET_FUNDS.copy()

# ============================================================
# API 路由
# ============================================================

@app.route('/')
def index():
    return send_file('index.html')


@app.route('/api/funds', methods=['GET'])
def get_funds():
    fund_type = request.args.get('type', 'lof')
    codes_to_show = fund_database
    
    if fund_type == 'lof':
        # LOF基金：代码以16/161/162/164/501开头
        codes_to_show = [c for c in fund_database if (
            c.startswith('16') or c.startswith('501') or 
            c.startswith('164') or c.startswith('161') or c.startswith('162')
        )]
        if not codes_to_show:
            codes_to_show = fund_database
    
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(build_fund_data, code): code for code in codes_to_show}
        for future in as_completed(futures):
            fund = future.result()
            if fund:
                results.append(fund)
    # LOF视图按溢价率降序（可套利优先）
    results.sort(key=lambda x: x['premium'], reverse=True)
    return jsonify(results)


@app.route('/api/funds/search', methods=['GET'])
def search_funds():
    keyword = request.args.get('q', '').lower().strip()
    if not keyword:
        return get_funds()

    cache_set(_cache, '__keyword', keyword, 30)

    if keyword.isdigit() and len(keyword) >= 5:
        code = keyword.zfill(6)
        fund = build_fund_data(code)
        if fund and fund.get('nav', 0) > 0 and is_fund_code(code):
            if code not in fund_database:
                fund_database.append(code)
            return jsonify([fund])
        # 不是基金（如股票）则返回空，且不加入数据库
        return jsonify([])

    matched = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(build_fund_data, code): code for code in fund_database}
        for future in as_completed(futures):
            fund = future.result()
            if fund and keyword in fund['name'].lower():
                matched.append(fund)
    matched.sort(key=lambda x: x['premium'], reverse=True)
    return jsonify(matched)


@app.route('/api/funds/<code>', methods=['GET'])
def get_fund_detail(code):
    fund = build_fund_data(code)
    if not fund:
        return jsonify({'error': '基金不存在'}), 404
    trend = fetch_intraday_trend(code)
    fund['trend'] = trend if trend else []
    return jsonify(fund)


@app.route('/api/funds/add', methods=['POST'])
def add_fund():
    data = request.get_json()
    code = data.get('code', '').strip()
    if not code or len(code) < 5:
        return jsonify({"error": "请输入有效的基金代码"}), 400
    code = code.zfill(6)
    if code in fund_database:
        fund = build_fund_data(code)
        return jsonify(fund) if fund else (jsonify({"error": "无法获取基金数据"}), 500)
    fund = build_fund_data(code)
    if fund:
        fund_database.append(code)
        return jsonify(fund)
    return jsonify({"error": "无法获取该基金数据，请检查代码是否正确"}), 400


@app.route('/api/funds/refresh', methods=['POST'])
def refresh_funds():
    _cache.clear()
    _cache_purchase.clear()
    _cache_trend.clear()
    return jsonify({'status': 'success', 'message': '数据已刷新', 'update_time': datetime.now().isoformat()})


@app.route('/api/funds/<code>', methods=['DELETE'])
def delete_fund(code):
    """从 fund_database 中删除指定基金"""
    if code in fund_database:
        fund_database.remove(code)
    _cache.pop(code, None)
    return jsonify({'status': 'success'})

# ============================================================
# 核心：组装基金数据
# ============================================================

def build_fund_data(code):
    cached = cache_get(_cache, code, 20)
    if cached:
        return cached

    # 并行获取三大数据源
    price_data = None
    nav_data_fundgz = None
    lsjz_data = None

    with ThreadPoolExecutor(max_workers=3) as executor:
        f_price = executor.submit(fetch_price_from_sina, code)
        f_fundgz = executor.submit(fetch_nav_from_fundgz, code)
        f_lsjz = executor.submit(fetch_fund_info_lsjz, code)

        for f in as_completed([f_price, f_fundgz, f_lsjz], timeout=8):
            try:
                r = f.result(timeout=3)
                if f == f_price:
                    price_data = r
                elif f == f_fundgz:
                    nav_data_fundgz = r
                elif f == f_lsjz:
                    lsjz_data = r
            except Exception:
                pass

    if not price_data and not nav_data_fundgz and not lsjz_data:
        return None

    # 名称
    name = (price_data or {}).get('name', '') or (nav_data_fundgz or {}).get('name', '')

    # 价格：优先新浪实时价，其次天天基金估值
    price = 0
    if price_data and price_data.get('price', 0) > 0:
        price = price_data['price']
    elif nav_data_fundgz and nav_data_fundgz.get('estimate_value', 0) > 0:
        price = nav_data_fundgz['estimate_value']

    # 净值：优先LSJZList，其次天天基金
    nav = 0
    nav_date = ''
    if lsjz_data and lsjz_data.get('nav', 0) > 0:
        nav = lsjz_data['nav']
        nav_date = lsjz_data['nav_date']
    elif nav_data_fundgz and nav_data_fundgz.get('nav', 0) > 0:
        nav = nav_data_fundgz['nav']
        nav_date = nav_data_fundgz['nav_date']

    premium = round(((price - nav) / nav) * 100, 2) if nav > 0 else 0

    # 申购状态
    sgzt = lsjz_data.get('sgzt', '') if lsjz_data else ''
    purchase_status = map_purchase_status(sgzt)
    if purchase_status == '开放申购' and nav_data_fundgz:
        est = nav_data_fundgz.get('estimate_value', 0)
        if est > 0:
            purchase_status = '开放申购'

    # 申购限额
    purchase_limit = fetch_purchase_limit(code, purchase_status)
    if purchase_limit == -1:
        purchase_limit = 0  # 显示为0表示无限额但标题提示

    result = {
        'code': code,
        'name': name if name else f'基金{code}',
        'price': price,
        'nav': nav,
        'premium': premium,
        'purchase_status': purchase_status,
        'purchase_limit': purchase_limit,
        'nav_date': nav_date,
        'update_time': datetime.now().isoformat()
    }

    # 检测是否为股票：如果代码不在基金范围且名称不像基金且溢价极端，标记nav=0
    if not is_fund_code(code) and looks_like_stock(name, premium, code):
        result['nav'] = 0
        result['premium'] = 0
        result['purchase_status'] = '开放申购'
        result['purchase_limit'] = 0

    cache_set(_cache, code, result, 20)
    return result


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LOF基金监控 v1.9.2-QPython"""

import os, re, ssl, json, http.server, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

def _cst_date(ts_ms):
    try:
        cst = timezone(timedelta(hours=8))
        dt = datetime.fromtimestamp(int(ts_ms) / 1000, tz=cst)
        return dt.strftime('%Y-%m-%d')
    except Exception:
        return ''

JS_SCRIPT = """var API = "/api";
var fundData = [];
var allFunds = [];
var lofFunds = [];
var favFunds = [];
var currentTab = "lof";

function loadFavorites() {
  try { favFunds = JSON.parse(localStorage.getItem("favFunds") || "[]"); }
  catch(e) { favFunds = []; }
}

function saveFavorites() {
  localStorage.setItem("favFunds", JSON.stringify(favFunds));
}

function isFavorite(code) {
  return favFunds.indexOf(code) > -1;
}

function toggleFavorite(code, element) {
  var idx = favFunds.indexOf(code);
  if(idx > -1) {
    favFunds.splice(idx, 1);
    element.classList.remove("active");
    showToast("已取消自选");
  } else {
    favFunds.push(code);
    element.classList.add("active");
    showToast("已加入自选");
  }
  saveFavorites();
  updateFavCount();
}

function updateFavCount() {
  document.getElementById("fav-count").textContent = favFunds.length;
}

function showToast(msg) {
  var t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.add("show");
  setTimeout(function(){ t.classList.remove("show"); }, 1500);
}

function render() {
  var data = [];
  if(currentTab === "fav") {
    data = fundData.filter(function(f){ return isFavorite(f.code); });
  } else if(currentTab === "all") {
    data = allFunds;
  } else {
    data = lofFunds;
  }

  var list = document.getElementById("fund-list");
  list.innerHTML = "";

  if(!data.length) {
    list.innerHTML = '<div style="text-align:center;color:#667;padding:30px;font-size:13px">暂无数据，请检查网络后刷新</div>';
    document.getElementById("fund-count").textContent = "0";
    return;
  }

  for(var i=0; i<data.length; i++) {
    var f = data[i];
    var hasNav = f.nav > 0;
    var isFav = isFavorite(f.code);

    var priceChange = 0;
    if(hasNav && f.prev_close && f.prev_close > 0) {
      priceChange = ((f.price - f.prev_close) / f.prev_close) * 100;
    }

    var navChange = f.nav_change || 0;

    var statusHtml = "";
    if(hasNav) {
      if(f.purchase_status === "Stopped") {
        statusHtml = '<span class="status-tag stopped">暂停</span>';
      } else if(f.purchase_status === "Limited") {
        statusHtml = '<span class="status-tag limited">限额</span>';
      }
    }

    var priceSign = priceChange >= 0 ? "+" : "";
    var navSign = navChange >= 0 ? "+" : "";
    var premSign = f.premium >= 0 ? "-" : "";

    var item = document.createElement("div");
    item.className = "fund-item" + (isFav ? " fav" : "");

    var btn = document.createElement("button");
    btn.className = "fav-btn" + (isFav ? " active" : "");
    btn.innerHTML = isFav ? "&#10084;" : "&#9825;";
    btn.onclick = function(code, el) { return function() { toggleFavorite(code, el); }; }(f.code, btn);

    var info = document.createElement("div");
    info.className = "fund-info";
    info.innerHTML = '<div class="fund-name">' + f.name + '</div><div class="fund-meta">' + f.code + statusHtml + '</div>';

    var col1 = document.createElement("div");
    col1.className = "col";
    col1.innerHTML = '<div class="col-value">' + (f.price > 0 ? f.price.toFixed(4) : "-") + '</div>' +
                     '<div class="col-change ' + (priceChange >= 0 ? "up" : "dn") + '">' +
                     (hasNav ? priceSign + priceChange.toFixed(2) + "%" : "-") + '</div>';

    var col2 = document.createElement("div");
    col2.className = "col";
    col2.innerHTML = '<div class="col-value">' + (hasNav ? f.nav.toFixed(4) : "-") + '</div>' +
                     '<div class="col-change ' + (navChange >= 0 ? "up" : "dn") + '">' +
                     (hasNav ? navSign + navChange.toFixed(2) + "%" : "-") + '</div>';

    var prem = document.createElement("div");
    prem.className = "premium " + (f.premium >= 0 ? "high-premium" : "low-premium");
    prem.innerHTML = hasNav ? premSign + f.premium.toFixed(2) + "%" : "-";

    item.appendChild(btn);
    item.appendChild(info);
    item.appendChild(col1);
    item.appendChild(col2);
    item.appendChild(prem);

    list.appendChild(item);
  }

  document.getElementById("fund-count").textContent = data.length;

  var validData = data.filter(function(f){ return f.nav > 0; });
  if(validData.length) {
    var sorted = validData.sort(function(a,b){ return b.premium - a.premium; });
    document.getElementById("high-premium").textContent = "-" + sorted[0].premium.toFixed(2);
    document.getElementById("low-premium").textContent = sorted[sorted.length-1].premium.toFixed(2);
  }
}

async function fetchData(type, keyword) {
  try {
    var url = keyword
      ? API + "/funds/search?q=" + encodeURIComponent(keyword)
      : API + "/funds?type=" + type;

    var resp = await fetch(url, {cache: "no-cache"});
    var data = await resp.json();

    fundData = data.filter(function(f){ return f.nav > 0; });
    lofFunds = fundData.filter(function(f){ return isLofCode(f.code); });
    allFunds = fundData;

    render();
    showToast("加载完成，共 " + fundData.length + " 只");
  } catch(e) {
    showToast("加载失败，请检查网络");
    console.error(e);
  }
}

function isLofCode(code) {
  if(!code) return false;
  code = code.toString().padStart(6, '0');
  return code.startsWith('16') || code.startsWith('501');
}

function switchTab(tab) {
  currentTab = tab;
  document.querySelectorAll(".tab-btn").forEach(function(btn){ btn.classList.remove("active"); });
  event.target.classList.add("active");
  render();
}

function refreshData() {
  showToast("刷新中...");
  fetchData(currentTab === "lof" ? "lof" : "all", "");
}

function init() {
  loadFavorites();
  updateFavCount();
  fetchData("lof", "");
  setInterval(refreshData, 30000);
}

window.onload = init;
"""

CSS_STYLE = """* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background:#f5f5f5; }
.header { background:linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); color:#fff; padding:12px 15px; position:sticky; top:0; z-index:100; }
.header-top { display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; }
.title { font-size:18px; font-weight:600; }
.version { font-size:10px; opacity:0.7; }
.refresh-btn { background:rgba(255,255,255,0.2); border:none; color:#fff; padding:6px 12px; border-radius:15px; font-size:12px; cursor:pointer; }
.tabs { display:flex; gap:8px; }
.tab-btn { flex:1; padding:8px 0; border:none; background:none; color:rgba(255,255,255,0.7); font-size:13px; border-radius:8px; transition:all 0.2s; }
.tab-btn.active { background:rgba(255,255,255,0.2); color:#fff; }
.search-bar { display:flex; gap:8px; padding:10px 15px; background:#fff; border-bottom:1px solid #eee; }
.search-input { flex:1; padding:8px 12px; border:1px solid #ddd; border-radius:20px; font-size:13px; outline:none; }
.search-btn { background:#1e3c72; color:#fff; border:none; padding:8px 16px; border-radius:20px; font-size:13px; cursor:pointer; }
.fund-list { padding:10px; }
.fund-item { display:flex; align-items:center; background:#fff; padding:12px; margin-bottom:8px; border-radius:12px; box-shadow:0 1px 3px rgba(0,0,0,0.05); transition:transform 0.1s; }
.fund-item:active { transform:scale(0.98); }
.fav-btn { width:36px; height:36px; border:none; background:#f5f5f5; border-radius:50%; font-size:18px; cursor:pointer; display:flex; align-items:center; justify-content:center; margin-right:10px; transition:all 0.2s; }
.fav-btn.active { background:#ff6b6b; color:#fff; }
.fund-info { flex:1; min-width:0; }
.fund-name { font-size:14px; font-weight:500; color:#333; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.fund-meta { font-size:11px; color:#999; margin-top:2px; }
.status-tag { display:inline-block; margin-left:6px; padding:1px 6px; border-radius:4px; font-size:10px; }
.status-tag.stopped { background:#ff4757; color:#fff; }
.status-tag.limited { background:#ffa502; color:#fff; }
.col { text-align:right; min-width:80px; margin-left:10px; }
.col-value { font-size:14px; font-weight:600; color:#333; }
.col-change { font-size:11px; margin-top:2px; }
.col-change.up { color:#ff4757; }
.col-change.dn { color:#2ed573; }
.premium { min-width:60px; text-align:right; font-size:14px; font-weight:600; }
.premium.high-premium { color:#ff4757; }
.premium.low-premium { color:#2ed573; }
.footer { text-align:center; padding:20px; color:#999; font-size:12px; }
.toast { position:fixed; bottom:60px; left:50%; transform:translateX(-50%); background:rgba(0,0,0,0.8); color:#fff; padding:12px 24px; border-radius:25px; font-size:13px; opacity:0; transition:opacity 0.3s; pointer-events:none; z-index:1000; }
.toast.show { opacity:1; }
"""

HTML_CONTENT = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>LOF基金监控</title>
<style>""" + CSS_STYLE + """</style>
</head>
<body>
<div class="header">
  <div class="header-top">
    <div>
      <div class="title">LOF基金监控</div>
      <div class="version">v1.9.2-QPython</div>
    </div>
    <button class="refresh-btn" onclick="refreshData()">刷新</button>
  </div>
  <div class="tabs">
    <button class="tab-btn active" onclick="switchTab('lof')">LOF</button>
    <button class="tab-btn" onclick="switchTab('all')">全部</button>
    <button class="tab-btn" onclick="switchTab('fav')">自选 <span id="fav-count">0</span></button>
  </div>
</div>
<div class="search-bar">
  <input type="text" class="search-input" placeholder="搜索基金代码或名称" id="search-input" onkeyup="if(event.keyCode==13) doSearch()">
  <button class="search-btn" onclick="doSearch()">搜索</button>
</div>
<div class="fund-list" id="fund-list">
  <div style="text-align:center;color:#999;padding:40px;font-size:14px">加载中...</div>
</div>
<div class="footer">
  <div>溢价率 = (场内价格 - 净值) / 净值 × 100%</div>
  <div style="margin-top:5px;color:#ccc">数据仅供参考</div>
</div>
<div id="toast" class="toast"></div>
<script>
function doSearch() {
  var q = document.getElementById("search-input").value.trim();
  fetchData("lof", q);
}
""" + JS_SCRIPT + """
</script>
</body>
</html>"""

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
_cache = {}

PF = [
    '513100','513500','513520','159941','513050','159605','510300','510050','510500',
    '159915','159949','512880','512760','513030','159920','510880','518880','512480',
    '159995','513090','512660','159601','159845','160416','162411','159992','513130',
    '513010','513300','515030','515790','515050','512010','512800','512690','159996',
    '513150','513220','513880','513980','159632','159607','515880','512100','501225',
    '501312','501018','501021','501078','164906','164205','161129','161027','161725',
    '160632','162703','160706','166009','166623','161226','160213','161128','163208',
    '160717','164205'
]
FD = PF.copy()

def get_cache(d, k, t=20):
    entry = d.get(k)
    if entry and entry['expires_at'] > datetime.now():
        return entry['data']
    return None

def set_cache(d, k, v, t=20):
    d[k] = {'data': v, 'expires_at': datetime.now() + timedelta(seconds=t)}

def http_get(url, timeout=8):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    return urllib.request.urlopen(req, timeout=timeout, context=ssl_ctx)

def get_market(c):
    return 'sh' if c.startswith('5') else 'sz'

def fetch_price(c):
    try:
        url = 'https://hq.sinajs.cn/list=' + get_market(c) + c
        txt = http_get(url, 3).read().decode('gbk', errors='ignore')
        m = re.search(r'"(.+)"', txt)
        if not m: return None
        p = m.group(1).split(',')
        if len(p) < 9: return None
        return {
            'name': p[0],
            'price': float(p[3]) if p[3] else 0,
            'prev_close': float(p[2]) if p[2] else 0
        }
    except: return None

def fetch_nav_gz(c):
    try:
        url = 'https://fundgz.1234567.com.cn/js/' + c + '.js'
        txt = http_get(url, 3).read().decode()
        m = re.search(r'jsonpgz\((.+)\)', txt)
        if not m: return None
        d = json.loads(m.group(1))
        return {
            'name': d.get('name', ''),
            'nav': float(d.get('dwjz', 0)),
            'nav_date': d.get('jzrq', ''),
            'estimate_value': float(d.get('gsz', 0)),
            'nav_change': float(d.get('gszzl', 0))
        }
    except: return None

def fetch_nav_list(c):
    try:
        url = 'https://api.fund.eastmoney.com/f10/lsjz?callback=jQuery&fundCode=' + c + '&pageIndex=1&pageSize=1'
        txt = http_get(url, 5).read().decode()
        m = re.search(r'\((.+)\)', txt)
        if not m: return None
        d = json.loads(m.group(1))
        l = d.get('Data', {}).get('LSJZList', [])
        if not l: return None
        return {
            'nav': float(l[0].get('DWJZ', 0)),
            'nav_date': l[0].get('FSRQ', ''),
            'sgzt': l[0].get('SGZT', '')
        }
    except: return None

def fetch_fund_status(c):
    try:
        url = 'http://fund.eastmoney.com/' + c + '.html'
        txt = http_get(url, 5).read().decode('utf-8', errors='ignore')
        plain = re.sub(r'<script[^>]*>.*?</script>', '', txt, flags=re.DOTALL | re.IGNORECASE)
        plain = re.sub(r'<style[^>]*>.*?</style>', '', plain, flags=re.DOTALL | re.IGNORECASE)
        plain = re.sub(r'<[^>]+>', ' ', plain)
        plain = re.sub(r'\s+', '', plain)
        ts_m = re.search(r'交易状态[:：]?(.{0,150}?)购买手续费', plain)
        status_frag = ts_m.group(1) if ts_m else ''
        if len(status_frag) < 2:
            ts_m2 = re.search(r'交易状态[:：]?(.{0,80})', plain)
            status_frag = ts_m2.group(1) if ts_m2 else ''
        is_suspended = '暂停申购' in status_frag or '停止申购' in status_frag
        is_limit = '限大额' in status_frag or '暂停大额申购' in status_frag or '大额限购' in status_frag
        if is_suspended:
            return 'Stopped'
        elif is_limit:
            return 'Limited'
        return 'Open'
    except:
        return 'Open'

def map_status(s):
    if not s: return 'Open'
    s = s.strip()
    if '暂停' in s or '停止' in s: return 'Stopped'
    if '限' in s: return 'Limited'
    return 'Open'

def is_lof(c):
    if not c or len(c) < 6: return False
    c = c.zfill(6)
    prefixes = ['16', '501', '164', '161', '162']
    return any(c.startswith(p) for p in prefixes)

def build_fund(c):
    cached = get_cache(_cache, c, 20)
    if cached: return cached

    price_data = None
    nav_gz_data = None
    nav_list_data = None

    with ThreadPoolExecutor(max_workers=3) as ex:
        futures = [ex.submit(fetch_price, c), ex.submit(fetch_nav_gz, c), ex.submit(fetch_nav_list, c)]
        for f in as_completed(futures, timeout=8):
            try:
                r = f.result(timeout=3)
                if f == futures[0]:
                    price_data = r
                elif f == futures[1]:
                    nav_gz_data = r
                else:
                    nav_list_data = r
            except:
                pass

    if not price_data and not nav_gz_data and not nav_list_data:
        return None

    name = (price_data or {}).get('name', '') or (nav_gz_data or {}).get('name', '')
    price = prev_close = 0

    if price_data and price_data.get('price', 0) > 0:
        price = price_data['price']
        prev_close = price_data.get('prev_close', 0)
    elif nav_gz_data and nav_gz_data.get('estimate_value', 0) > 0:
        price = nav_gz_data['estimate_value']

    nav = nav_date = nav_change = 0

    if nav_list_data and nav_list_data.get('nav', 0) > 0:
        nav = nav_list_data['nav']
        nav_date = nav_list_data['nav_date']
    elif nav_gz_data and nav_gz_data.get('nav', 0) > 0:
        nav = nav_gz_data['nav']
        nav_date = nav_gz_data['nav_date']
        nav_change = nav_gz_data.get('nav_change', 0)

    premium = round(((price - nav) / nav) * 100, 2) if nav > 0 else 0
    
    sgzt = (nav_list_data or {}).get('sgzt', '')
    purchase_status = map_status(sgzt)
    
    if purchase_status == 'Open' and is_lof(c):
        purchase_status = fetch_fund_status(c)

    result = {
        'code': c,
        'name': name or 'Fund-' + c,
        'price': price,
        'prev_close': prev_close,
        'nav': nav,
        'nav_change': nav_change,
        'premium': premium,
        'purchase_status': purchase_status,
        'purchase_limit': 0,
        'nav_date': nav_date,
        'update_time': datetime.now().isoformat()
    }

    if not is_lof(c) and abs(premium) > 50:
        result['nav'] = 0
        result['premium'] = 0
        result['purchase_status'] = 'Open'

    set_cache(_cache, c, result, 20)
    return result

def handle_get_all(fp):
    fund_type = fp.get('type', ['lof'])[0] if isinstance(fp.get('type'), list) else fp.get('type', 'lof')

    if fund_type == 'lof':
        codes = [x for x in FD if x.startswith('16') or x.startswith('501')]
    else:
        codes = FD.copy()

    if not codes:
        codes = FD.copy()

    results = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(build_fund, c): c for c in codes}
        for f in as_completed(futures):
            r = f.result()
            if r:
                results.append(r)

    results.sort(key=lambda x: x['premium'], reverse=True)
    return results

def handle_search(fp):
    keyword = urllib.parse.unquote(fp.get('q', [''])[0] if isinstance(fp.get('q'), list) else fp.get('q', '')).lower().strip()

    if not keyword:
        return handle_get_all({'type': ['lof']})

    if keyword.isdigit() and len(keyword) >= 5:
        code = keyword.zfill(6)
        f = build_fund(code)
        if f and f.get('nav', 0) > 0 and is_lof(code):
            if code not in FD:
                FD.append(code)
            return [f]
        return []

    matched = []
    for c in FD:
        f = build_fund(c)
        if f and keyword in f['name'].lower():
            matched.append(f)

    matched.sort(key=lambda x: x['premium'], reverse=True)
    return matched

def handle_refresh():
    _cache.clear()
    return {'status': 'success', 'update_time': datetime.now().isoformat()}

class RequestHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(self.client_address[0] + ' - - [' + self.log_date_time_string() + '] ' + fmt % args)

    def do_GET(self):
        if self.path in ['/', '', '/index.html']:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_CONTENT.encode('utf-8'))
            return

        if self.path.startswith('/api/'):
            self.handle_api()
            return

        self.send_error(404)

    def handle_api(self):
        path = self.path[4:]
        query_params = {}

        if '?' in path:
            parts = path.split('?', 1)
            path = parts[0]
            for pair in parts[1].split('&'):
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    query_params[k] = [v]

        try:
            if path == '/funds':
                self.send_json(handle_get_all(query_params))
            elif path.startswith('/funds/search'):
                self.send_json(handle_search(query_params))
            elif path.startswith('/funds/refresh'):
                self.send_json(handle_refresh())
            else:
                self.send_error(404)
        except Exception as e:
            print('API Error:', e)
            self.send_error(500)

    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def do_POST(self):
        if self.path.startswith('/api/'):
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = {}
            if content_length > 0:
                body = self.rfile.read(content_length).decode()
                for pair in body.split('&'):
                    if '=' in pair:
                        k, v = pair.split('=', 1)
                        post_data[urllib.parse.unquote(k)] = urllib.parse.unquote(v)
            self.handle_api_post(post_data)
        else:
            self.send_error(404)

    def handle_api_post(self, post_data):
        path = self.path[4:]
        if path.startswith('/funds/refresh'):
            self.send_json(handle_refresh())
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

def run(port=8000):
    ports_to_try = [port, 8080, 8888, 5000]
    for p in ports_to_try:
        try:
            server = http.server.HTTPServer(('0.0.0.0', p), RequestHandler)
            print('=' * 50)
            print('LOF基金监控 v1.9.2-QPython 启动成功!')
            print('访问: http://localhost:' + str(p))
            print('=' * 50)
            server.serve_forever()
        except OSError:
            print('端口', p, '已被占用, 尝试下一个...')
            continue

if __name__ == '__main__':
    run(8000)

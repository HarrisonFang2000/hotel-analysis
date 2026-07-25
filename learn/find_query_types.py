"""找出每个Tab对应的queryType参数"""
import sqlite3, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from playwright.sync_api import sync_playwright

conn = sqlite3.connect('data/hotel_data.db')
c = conn.cursor()
c.execute("SELECT config_value FROM sys_config WHERE config_key='collect_cookie'")
row = c.fetchone()
cookies = json.loads(row[0]) if row else []

pw = sync_playwright().start()
browser = pw.chromium.launch(headless=True, args=['--no-sandbox'])
ctx = browser.new_context(viewport={'width': 1920, 'height': 1080})
ctx.add_cookies(cookies)
page = ctx.new_page()

# 只监听导出API
export_calls = []
def on_request(req):
    if 'export/hotelIncomeStatus.do' in req.url:
        export_calls.append(req.url)

page.on('request', on_request)

page.goto('http://kz.quhuhu.com/v2/report/guestRoom.htm', timeout=30000)
page.wait_for_load_state('networkidle', timeout=15000)

# 定义每个tab
tabs = {
    "income_check": "营业收入",
    "daily_room": "日租房概况",
    "hourly_room": "钟点房概况",
    "other_consume": "其他消费概况",
}

from urllib.parse import urlparse, parse_qs

for rtype, tab_name in tabs.items():
    export_calls.clear()
    
    # 切换tab
    page.locator(f".ivu-tabs-tab:has-text('{tab_name}')").first.click()
    page.wait_for_timeout(1500)
    
    # 点导出
    try:
        for sel in ["button:has-text('导出')", "span:has-text('导出')"]:
            el = page.locator(sel).last
            if el.count() > 0:
                with page.expect_download(timeout=30000) as dl:
                    el.click()
                download = dl.value
                # 解析URL参数
                url = download.url if hasattr(download, 'url') else ''
                if not url and export_calls:
                    url = export_calls[0]
                if url:
                    params = parse_qs(urlparse(url).query)
                    qt = params.get('queryType', ['?'])[0]
                    print(f"  {rtype:15s} ({tab_name:8s}) → queryType={qt}")
                break
    except Exception as e:
        # 从拦截的请求中获取
        if export_calls:
            for u in export_calls:
                params = parse_qs(urlparse(u).query)
                qt = params.get('queryType', ['?'])[0]
                print(f"  {rtype:15s} ({tab_name:8s}) → queryType={qt} (intercepted)")
        else:
            print(f"  {rtype:15s} ({tab_name:8s}) → FAILED: {e}")

browser.close()
pw.stop()

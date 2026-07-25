"""抓取去呼呼导出API"""
import sqlite3, json, os, time, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from playwright.sync_api import sync_playwright

conn = sqlite3.connect('data/hotel_data.db')
c = conn.cursor()
c.execute("SELECT config_value FROM sys_config WHERE config_key='collect_cookie'")
row = c.fetchone()
cookies = json.loads(row[0]) if row else []
print(f"加载 {len(cookies)} 个Cookie")

pw = sync_playwright().start()
browser = pw.chromium.launch(headless=True, args=['--no-sandbox'])
ctx = browser.new_context(viewport={'width': 1920, 'height': 1080})
ctx.add_cookies(cookies)
page = ctx.new_page()

# 监听网络请求
api_urls = []
def on_request(req):
    url = req.url
    if any(kw in url.lower() for kw in ['export', 'download', 'excel', 'guestroom']):
        api_urls.append(f"[{req.method}] {url}")
def on_response(resp):
    if any(kw in resp.url.lower() for kw in ['export', 'download', 'excel']):
        ct = resp.headers.get('content-type', '')
        print(f"  RESP {resp.status} {ct[:60]} -> {resp.url}")

page.on('request', on_request)
page.on('response', on_response)

print("导航到报表页...")
page.goto('http://kz.quhuhu.com/v2/report/guestRoom.htm', timeout=30000)
page.wait_for_load_state('networkidle', timeout=15000)
print(f"已到达: {page.title()}")

# 点导出
print("尝试导出...")
try:
    for sel in ["button:has-text('导出')", "span:has-text('导出')"]:
        el = page.locator(sel).last
        if el.count() > 0 and el.is_visible(timeout=3000):
            with page.expect_download(timeout=30000) as dl:
                el.click()
            download = dl.value
            print(f"下载成功!")
            print(f"  URL: {download.url}")
            print(f"  文件名: {download.suggested_filename}")
            download.save_as(f"learn/test_export.xlsx")
            print(f"  已保存: learn/test_export.xlsx")
            break
except Exception as e:
    print(f"导出失败: {e}")

print(f"\n捕获的相关API ({len(set(api_urls))}个):")
for u in sorted(set(api_urls)):
    print(f"  {u}")

browser.close()
pw.stop()

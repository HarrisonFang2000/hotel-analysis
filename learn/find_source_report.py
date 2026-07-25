"""探索客源统计报表的导出API"""
import sys, os, time, json, sqlite3
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse, parse_qs

conn = sqlite3.connect('data/hotel_data.db')
c = conn.cursor()
c.execute("SELECT config_value FROM sys_config WHERE config_key='collect_cookie'")
cookies = json.loads(c.fetchone()[0])

pw = sync_playwright().start()
browser = pw.chromium.launch(headless=True, args=['--no-sandbox'])
ctx = browser.new_context(viewport={'width': 1920, 'height': 1080})
ctx.add_cookies(cookies)
page = ctx.new_page()

# 监听所有API请求
api_hits = []
def on_request(req):
    url = req.url
    if 'api' in url or 'export' in url or 'source' in url.lower() or 'guest' in url.lower():
        api_hits.append(f"[{req.method}] {url[:200]}")

page.on('request', on_request)

# 尝试可能的客源统计URL
urls_to_try = [
    'http://kz.quhuhu.com/v2/report/guestSource.htm',
    'http://kz.quhuhu.com/v2/report/customerSource.htm',
    'http://kz.quhuhu.com/v2/report/sourceStats.htm',
    'http://kz.quhuhu.com/v2/report/guestRoom.htm',  # 已知的客房销售报表
]

for url in urls_to_try:
    api_hits.clear()
    print(f'\n尝试: {url}')
    try:
        page.goto(url, wait_until='domcontentloaded', timeout=15000)
        page.wait_for_timeout(3000)
        try:
            page.wait_for_load_state('networkidle', timeout=10000)
        except:
            pass
        title = page.title()
        print(f'  标题: {title}')
        print(f'  实际URL: {page.url[:120]}')
        
        # 找导出按钮
        for sel in ["button:has-text('导出')", "span:has-text('导出')"]:
            try:
                el = page.locator(sel).last
                if el.count() > 0 and el.is_visible(timeout=2000):
                    with page.expect_download(timeout=15000) as dl:
                        el.click()
                    download = dl.value
                    print(f'  导出URL: {download.url[:200]}')
                    print(f'  文件名: {download.suggested_filename}')
                    break
            except:
                pass
        
        if api_hits:
            print(f'  API请求 ({len(api_hits)}):')
            for h in api_hits[-10:]:
                print(f'    {h[:150]}')
    except Exception as e:
        print(f'  失败: {e}')

browser.close()
pw.stop()

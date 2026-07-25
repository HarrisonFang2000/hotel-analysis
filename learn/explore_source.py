"""探索客源统计页面，找到订单来源明细的导出API"""
import sys, os, json, sqlite3, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from playwright.sync_api import sync_playwright

conn = sqlite3.connect('data/hotel_data.db')
c = conn.cursor()
c.execute("SELECT config_value FROM sys_config WHERE config_key='collect_cookie'")
cookies = json.loads(c.fetchone()[0])

pw = sync_playwright().start()
browser = pw.chromium.launch(headless=True, args=['--no-sandbox'])
ctx = browser.new_context(viewport={'width': 1920, 'height': 1080})
ctx.add_cookies(cookies)
page = ctx.new_page()

# 监听导出API
export_hits = []
def on_request(req):
    if 'export' in req.url:
        export_hits.append(req.url)
page.on('request', on_request)

# 尝试客源统计URL
page.goto('https://kz.quhuhu.com/v2/report/guestSource.htm', timeout=20000)
page.wait_for_timeout(5000)
try:
    page.wait_for_load_state('networkidle', timeout=15000)
except:
    pass

print(f'URL: {page.url}')
print(f'Title: {page.title()}')
page.screenshot(path='learn/guestSource.png')

# 分析页面内容
body = page.evaluate("() => document.body.innerText.substring(0, 1000)")
print(f'页面文本:\n{body}')

# 尝试找导出按钮
print('\n尝试导出...')
for sel in ["button:has-text('导出')", "span:has-text('导出')", "a:has-text('导出')"]:
    try:
        el = page.locator(sel).last
        if el.count() > 0:
            print(f'  找到: {sel}')
            try:
                with page.expect_download(timeout=15000) as dl:
                    el.click()
                download = dl.value
                print(f'  导出URL: {download.url}')
                print(f'  文件名: {download.suggested_filename}')
                download.save_as('learn/source_export.xls')
                print(f'  已保存!')
                break
            except Exception as e:
                print(f'  下载失败: {e}')
    except Exception as e:
        print(f'  选择器失败: {e}')

print(f'\n捕获的导出API ({len(export_hits)}):')
for h in export_hits:
    print(f'  {h}')

browser.close()
pw.stop()

"""
彻底攻克客源统计报表
步骤：
1. Cookie免登 → PMS首页
2. 菜单导航: 报表 → 运营报表 → 客源统计
3. 分析页面：日期选择、查询、导出
4. 截获导出API
"""
import sys, os, json, sqlite3, time, re
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

# 监听所有网络请求
all_api = []
def on_request(req):
    url = req.url
    if '/api/' in url or 'export' in url:
        all_api.append(f"[{req.method}] {url[:200]}")
page.on('request', on_request)

def snap(name):
    page.screenshot(path=f'learn/source_{name}.png')
    print(f'  截图: {name}')

# ============ Step 1: 进入PMS首页 ============
print('Step 1: 进入PMS首页')
page.goto('http://kz.quhuhu.com/rooms/table.htm', timeout=20000)
page.wait_for_timeout(3000)
try:
    page.wait_for_load_state('networkidle', timeout=10000)
except:
    pass
print(f'URL: {page.url}')
print(f'标题: {page.title()}')
snap('01_home')

# ============ Step 2: 点击顶部导航"报表" ============
print('\nStep 2: 点击"报表"')
all_api.clear()

# 在顶部导航栏找"报表"
found_report = False
for sel in [
    "a:has-text('报表')", "span:has-text('报表')", "li:has-text('报表')",
    "div:has-text('报表')", ".nav-item:has-text('报表')", "[class*='nav']:has-text('报表')",
]:
    try:
        el = page.locator(sel).first
        if el.count() > 0:
            el.click()
            print(f'  点击: {sel}')
            found_report = True
            break
    except:
        continue

if not found_report:
    # JS兜底
    page.evaluate("""() => {
        for (const el of document.querySelectorAll('a,span,li,div')) {
            if (el.textContent.trim() === '报表' && el.offsetParent) {
                el.click(); return;
            }
        }
    }""")
    print('  JS点击"报表"')

page.wait_for_timeout(2000)
snap('02_after_report')

# ============ Step 3: 找"运营报表" ============
print('\nStep 3: 找"运营报表"')
found_oper = False
for sel in [
    "a:has-text('运营报表')", "span:has-text('运营报表')", "li:has-text('运营报表')",
    "div:has-text('运营报表')", ".menu-item:has-text('运营报表')",
]:
    try:
        el = page.locator(sel).first
        if el.count() > 0:
            el.click()
            print(f'  点击: {sel}')
            found_oper = True
            break
    except:
        continue

if not found_oper:
    page.evaluate("""() => {
        for (const el of document.querySelectorAll('a,span,li,div')) {
            if (el.textContent.includes('运营报表') && el.offsetParent) {
                el.click(); return;
            }
        }
    }""")
    print('  JS点击"运营报表"')

page.wait_for_timeout(2000)
snap('03_after_oper')

# ============ Step 4: 找"客源统计" ============
print('\nStep 4: 找"客源统计"')
found_source = False
for sel in [
    "a:has-text('客源统计')", "span:has-text('客源统计')", "li:has-text('客源统计')",
    "div:has-text('客源统计')", ".menu-item:has-text('客源统计')",
]:
    try:
        el = page.locator(sel).first
        if el.count() > 0:
            el.click()
            print(f'  点击: {sel}')
            found_source = True
            break
    except:
        continue

if not found_source:
    page.evaluate("""() => {
        for (const el of document.querySelectorAll('a,span,li,div')) {
            if (el.textContent.includes('客源统计') && el.offsetParent) {
                el.click(); return;
            }
        }
    }""")
    print('  JS点击"客源统计"')

page.wait_for_timeout(4000)
try:
    page.wait_for_load_state('networkidle', timeout=15000)
except:
    pass
page.wait_for_timeout(2000)

print(f'URL: {page.url}')
print(f'标题: {page.title}')
snap('04_source_page')

# ============ Step 5: 分析页面 ============
print('\nStep 5: 分析客源统计页面')
body = page.evaluate("() => (document.body || document.documentElement).innerText || ''")
print(f'页面文本(前800字):\n{body[:800]}')

# 找Tab/子报表
print('\n查找页面Tab/子报表:')
tabs = page.evaluate("""() => {
    const tabs = [];
    for (const el of document.querySelectorAll('.ivu-tabs-tab, [role=tab], .tab-item, .tab-title')) {
        if (el.offsetParent) tabs.push(el.textContent.trim());
    }
    return tabs;
}""")
print(f'  找到Tab: {tabs}')

# 找所有按钮
print('\n查找按钮:')
btns = page.evaluate("""() => {
    const btns = [];
    for (const el of document.querySelectorAll('button')) {
        if (el.offsetParent) btns.push(el.textContent.trim() || el.className);
    }
    return btns;
}""")
print(f'  按钮: {btns[:20]}')

# ============ Step 6: 尝试导出 ============
print('\nStep 6: 尝试导出')
all_api.clear()

# 如果有"订单来源明细"tab，先切换
for tab_name in ['订单来源明细', '来源明细', '客源明细']:
    for sel in [f".ivu-tabs-tab:has-text('{tab_name}')", f"div:has-text('{tab_name}')"]:
        try:
            el = page.locator(sel).first
            if el.count() > 0:
                el.click()
                print(f'  切换到Tab: {tab_name}')
                page.wait_for_timeout(2000)
                break
        except:
            continue

snap('05_before_export')

# 点导出
exported = False
for sel in ["button:has-text('导出')", "span:has-text('导出')", "a:has-text('导出')"]:
    try:
        el = page.locator(sel).last
        if el.count() > 0 and el.is_visible(timeout=3000):
            with page.expect_download(timeout=30000) as dl:
                el.click()
            download = dl.value
            print(f'\n✅ 导出成功!')
            print(f'  URL: {download.url}')
            print(f'  文件名: {download.suggested_filename}')
            download.save_as('learn/source_export_detail.xls')
            print(f'  已保存: learn/source_export_detail.xls')
            exported = True
            break
    except Exception as e:
        print(f'  导出失败({sel}): {e}')

# ============ Step 7: 分析API ============
print(f'\nStep 7: 捕获的API ({len(all_api)}个):')
export_apis = [u for u in all_api if 'export' in u.lower()]
other_apis = [u for u in all_api if 'export' not in u.lower()]
print('  导出相关:')
for u in export_apis:
    print(f'    {u[:200]}')
print('  其他API(最后10个):')
for u in other_apis[-10:]:
    print(f'    {u[:200]}')

browser.close()
pw.stop()

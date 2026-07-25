"""直接测试去呼呼API，诊断Cookie是否有效"""
import urllib.request, urllib.parse
import sqlite3, json, os

# 从数据库读取cookie
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'hotel_data.db')
conn = sqlite3.connect(db_path)
row = conn.execute("SELECT config_value FROM sys_config WHERE config_key='collect_cookie'").fetchone()
conn.close()

if not row:
    print('NO COOKIE FOUND!')
    exit()

cookies_list = json.loads(row[0])
cookie_str = '; '.join([f"{c['name']}={c['value']}" for c in cookies_list])
print(f'Cookie loaded: {len(cookies_list)} cookies, {len(cookie_str)} chars')

# Build API URL
HOTEL_NO = "hotel17873063584414"
EXPORT_API = "https://kz.quhuhu.com/v2/c/api/export/hotelIncomeStatus.do"

params = {
    'hotelNo': HOTEL_NO,
    'queryType': 'business',
    'queryChannel': 'false',
    'startDate': '2026-07-03 00:00:00',
    'endDate': '2026-07-03 23:59:00',
    'payType': '',
    'orderStatus': '',  # Try empty instead of "全部"
    'queryPaymentReceived': 'false',
}
url = EXPORT_API + '?' + urllib.parse.urlencode(params)
print(f'\nURL params: orderStatus="" (empty)')

req = urllib.request.Request(url, headers={
    'Cookie': cookie_str,
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
})
try:
    resp = urllib.request.urlopen(req, timeout=30)
    data = resp.read()
    print(f'Response: {len(data)} bytes, first 4 bytes: {data[:4].hex()}')
    if len(data) > 500 and data[:2] == b'\xd0\xcf':
        print('✅ Valid Excel file!')
    elif len(data) < 100:
        print(f'Content: {data[:200]}')
    else:
        print(f'Unexpected content, first 200: {data[:200]}')
except Exception as e:
    print(f'Error: {e}')
    if hasattr(e, 'read'):
        print(f'Error body: {e.read()[:500]}')

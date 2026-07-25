"""直接用urllib测试导出API的queryType参数"""
import sqlite3, json, urllib.request, urllib.parse, os, sys

conn = sqlite3.connect('data/hotel_data.db')
c = conn.cursor()
c.execute("SELECT config_value FROM sys_config WHERE config_key='collect_cookie'")
row = c.fetchone()
cookies_list = json.loads(row[0])

# 构建Cookie header
cookie_str = '; '.join([f"{c['name']}={c['value']}" for c in cookies_list])

base = 'https://kz.quhuhu.com/v2/c/api/export/hotelIncomeStatus.do'

# 测试不同queryType
for qt in ['business', 'daily', 'dailyRoom', 'night', 'hourly', 'hourlyRoom', 'hour', 'other', 'otherConsume', 'consume', 'income']:
    params = {
        'hotelNo': 'hotel17873063584414',
        'queryType': qt,
        'queryChannel': 'false',
        'startDate': '2026-07-19 00:00:00',
        'endDate': '2026-07-19 23:59:00',
        'payType': '',
        'orderStatus': '',
        'queryPaymentReceived': 'false',
    }
    url = base + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'Cookie': cookie_str})
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        data = resp.read()
        ct = resp.headers.get('Content-Type', '')
        size = len(data)
        is_excel = 'octet' in ct or (size > 500 and data[:2] == b'\xd0\xcf')
        print(f'  {qt:15s}  size={size:6d}  excel={is_excel}')
    except Exception as e:
        print(f'  {qt:15s}  ERROR: {e}')

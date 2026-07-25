"""检查月度导出的Excel结构"""
import sys, os, json, sqlite3, urllib.request, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd

conn = sqlite3.connect('data/hotel_data.db')
c = conn.cursor()
c.execute("SELECT config_value FROM sys_config WHERE config_key='collect_cookie'")
cookies = json.loads(c.fetchone()[0])
ck = '; '.join([f"{c['name']}={c['value']}" for c in cookies])

base = 'https://kz.quhuhu.com/v2/c/api/export/hotelIncomeStatus.do'
p = {
    'hotelNo': 'hotel17873063584414',
    'queryType': 'business',
    'queryChannel': 'false',
    'startDate': '2026-07-01 00:00:00',
    'endDate': '2026-07-20 23:59:00',
    'payType': '',
    'orderStatus': '',
    'queryPaymentReceived': 'false',
}
url = base + '?' + urllib.parse.urlencode(p)
req = urllib.request.Request(url, headers={'Cookie': ck})
r = urllib.request.urlopen(req, timeout=30)
data = r.read()
path = 'learn/month_export.xls'
with open(path, 'wb') as f:
    f.write(data)

df = pd.read_excel(path, header=None)
print(f'Shape: {df.shape}')
print(f'行0: {[str(df.iloc[0,i])[:60] for i in range(min(8,df.shape[1]))]}')
print(f'行1: {[str(df.iloc[1,i])[:30] for i in range(min(8,df.shape[1]))]}')

# 看前20行了解结构
print('\n前20行数据:')
for i in range(min(20, len(df))):
    row = [str(v)[:30] if pd.notna(v) else 'NaN' for v in df.iloc[i]]
    print(f'  [{i}] {row}')

# 统计日期出现的行
print('\n查找日期行...')
for i in range(len(df)):
    for j in range(df.shape[1]):
        v = str(df.iloc[i, j])
        if '2026-07-' in v:
            print(f'  [{i},{j}] = {v[:80]}')
            break

# 最后20行
print(f'\n最后20行 (总{len(df)}行):')
for i in range(max(0, len(df)-20), len(df)):
    row = [str(v)[:30] if pd.notna(v) else 'NaN' for v in df.iloc[i]]
    print(f'  [{i}] {row}')

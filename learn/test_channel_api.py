"""
测试客源统计API：
1. 单日 vs 日期范围
2. 订单来源明细 tab（可能有每单价格详情）
3. 各channelCode/payTypeCode参数
"""
import sys, os, json, sqlite3, urllib.request, urllib.parse
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

conn = sqlite3.connect('data/hotel_data.db')
c = conn.cursor()
c.execute("SELECT config_value FROM sys_config WHERE config_key='collect_cookie'")
cookies = json.loads(c.fetchone()[0])
ck = '; '.join([f"{c['name']}={c['value']}" for c in cookies])

base = 'https://kz.quhuhu.com/v2/c/api/export/channelOrderSummary.do'

# 测试1: 不同日期范围
print("=== 测试1: 日期范围 ===")
for start, end, label in [
    ('2026-07-19', '2026-07-19', '今天'),
    ('2026-07-18', '2026-07-18', '昨天'),
    ('2026-07-01', '2026-07-19', '本月至今'),
]:
    p = {
        'hotelNo': 'hotel17873063584414',
        'beginTime': f'{start} 00:00:00',
        'endTime': f'{end} 23:59:59',
        'channelCode': '',
        'payTypeCode': '',
    }
    url = base + '?' + urllib.parse.urlencode(p)
    req = urllib.request.Request(url, headers={'Cookie': ck})
    r = urllib.request.urlopen(req, timeout=15)
    data = r.read()
    path = f'learn/channel_{label}.xls'
    with open(path, 'wb') as f:
        f.write(data)
    df = pd.read_excel(path, header=None)
    print(f'\n{label} ({start}~{end}): {len(data)} bytes, {len(df)} rows')
    for i in range(len(df)):
        row = [str(v) for v in df.iloc[i] if str(v) != 'nan']
        if row:
            print(f'  {row}')

# 测试2: payTypeCode筛选
print("\n=== 测试2: payTypeCode筛选 ===")
for ptc, label in [('', '全部'), ('tyf', '全额预付'), ('xf', '到店现付')]:
    p = {
        'hotelNo': 'hotel17873063584414',
        'beginTime': '2026-07-19 00:00:00',
        'endTime': '2026-07-19 23:59:59',
        'channelCode': '',
        'payTypeCode': ptc,
    }
    url = base + '?' + urllib.parse.urlencode(p)
    req = urllib.request.Request(url, headers={'Cookie': ck})
    r = urllib.request.urlopen(req, timeout=15)
    path = f'learn/channel_pt_{ptc or "all"}.xls'
    with open(path, 'wb') as f:
        f.write(r.read())
    df = pd.read_excel(path, header=None)
    rows = []
    for i in range(len(df)):
        row = [str(v) for v in df.iloc[i] if str(v) != 'nan']
        if row:
            rows.append(row)
    print(f'{label}(payTypeCode={ptc or "空"}): {rows}')

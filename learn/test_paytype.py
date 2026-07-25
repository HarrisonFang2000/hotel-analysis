"""测试不同的payType参数"""
import sys, os, urllib.request, urllib.parse, sqlite3, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.data_cleaner import DataCleaner

conn = sqlite3.connect('data/hotel_data.db')
c = conn.cursor()
c.execute("SELECT config_value FROM sys_config WHERE config_key='collect_cookie'")
cookies = json.loads(c.fetchone()[0])
ck = '; '.join([f"{c['name']}={c['value']}" for c in cookies])

base = 'https://kz.quhuhu.com/v2/c/api/export/hotelIncomeStatus.do'
dc = DataCleaner()

# 测试不同的payType
pay_types = ['', 'online', 'offline', '线上', '线下', '美团', '携程', '微信', '支付宝', '预付', '现付', 'OTA', 'walkin', '1', '2', '3', 'direct', 'agent']

for pt in pay_types:
    p = {
        'hotelNo': 'hotel17873063584414',
        'queryType': 'business',
        'queryChannel': 'false',
        'startDate': '2026-07-19 00:00:00',
        'endDate': '2026-07-19 23:59:00',
        'payType': pt,
        'orderStatus': '',
        'queryPaymentReceived': 'false',
    }
    url = base + '?' + urllib.parse.urlencode(p)
    try:
        req = urllib.request.Request(url, headers={'Cookie': ck})
        r = urllib.request.urlopen(req, timeout=15)
        data = r.read()
        path = f'learn/paytype_{pt or "all"}.xls'
        with open(path, 'wb') as f:
            f.write(data)
        d, result, errors = dc.parse_excel(path)
        print(f"payType={pt or '(空=全部)':12s}  size={len(data):6d}  rooms={result['room_count']:4d}  fee={result['total_fee']:10.2f}  min={result['min_price']:8.2f}")
    except Exception as e:
        print(f"payType={pt or '(空=全部)':12s}  ERROR: {e}")

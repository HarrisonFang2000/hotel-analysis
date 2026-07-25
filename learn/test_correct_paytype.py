import sys, os, json, sqlite3, urllib.request, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.data_cleaner import DataCleaner

conn = sqlite3.connect('data/hotel_data.db')
c = conn.cursor()
c.execute("SELECT config_value FROM sys_config WHERE config_key='collect_cookie'")
cookies = json.loads(c.fetchone()[0])
ck = '; '.join([f"{c['name']}={c['value']}" for c in cookies])

base = 'https://kz.quhuhu.com/v2/c/api/export/hotelIncomeStatus.do'
dc = DataCleaner()

for pt, label in [('', '全部'), ('tyf', '全额预付-线上'), ('xf', '到店现付-线下')]:
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
    req = urllib.request.Request(url, headers={'Cookie': ck})
    r = urllib.request.urlopen(req, timeout=15)
    path = f"learn/paytype_{pt or 'all'}.xls"
    with open(path, 'wb') as f:
        f.write(r.read())
    d, result, errors = dc.parse_excel(path)
    print(f"{label}(payType={pt or '空'}): rooms={result['room_count']}, fee={result['total_fee']:.2f}, min={result['min_price']:.2f}")

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.collector import QuhuhuCollector
from app.core.data_cleaner import DataCleaner
import time

c = QuhuhuCollector()
c._preload_config()
print('Cookie:', bool(c._load_cookie_string()))

t0 = time.time()
path = c._api_collect_by_range('2026-07-01', '2026-07-20', '')
t1 = time.time()
print(f'Export: {path} ({t1-t0:.1f}s)')

if path:
    data = DataCleaner().parse_monthly_excel(path)
    t2 = time.time()
    print(f'Parsed {len(data)} days ({t2-t1:.1f}s)')
    for d in data[:5]:
        print(f'  {d["date"]}: rooms={d["room_count"]}, fee={d["total_fee"]}, min={d["min_price"]}')
    if len(data) > 5:
        print('  ...')
        for d in data[-3:]:
            print(f'  {d["date"]}: rooms={d["room_count"]}, fee={d["total_fee"]}, min={d["min_price"]}')

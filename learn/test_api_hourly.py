import urllib.request, json
r = urllib.request.urlopen('http://127.0.0.1:8080/api/hourly/list?date=2026-07-19')
d = json.loads(r.read())
print(f"code: {d['code']}")
items_with_data = [i for i in d['data'] if i.get('id')]
print(f"有数据的条目: {len(items_with_data)}")
for i in items_with_data:
    print(f"  hour={i['data_hour']}, rooms={i['sold_rooms']}, fee={i['total_revenue']}, min={i['min_price']}")
# 也看看23点的
h23 = [i for i in d['data'] if i['data_hour'] == 23][0]
print(f"\n23点: {h23}")

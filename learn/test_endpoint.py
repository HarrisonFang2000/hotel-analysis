import urllib.request,json,time

url = 'http://127.0.0.1:8080/api/io/import/auto-collect-history?start_date=2026-07-01&end_date=2026-07-03'
req = urllib.request.Request(url, method='POST')
t0 = time.time()
try:
    r = urllib.request.urlopen(req, timeout=120)
    d = json.loads(r.read())
    print(f"OK ({time.time()-t0:.1f}s): code={d['code']}, {d['message']}")
    data = d.get('data', {})
    print(f"  Total days: {data.get('total_days')}")
    print(f"  Success: {data.get('success_count')}")
    print(f"  Fail: {data.get('fail_count')}")
    if data.get('results'):
        for r in data['results'][-5:]:
            print(f"    {r['date']}: {r['rooms']} rooms, {r['revenue']} fee")
except Exception as e:
    print(f"Error: {e}")

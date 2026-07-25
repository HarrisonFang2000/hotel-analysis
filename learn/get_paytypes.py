import sys, os, json, sqlite3, urllib.request

conn = sqlite3.connect('data/hotel_data.db')
c = conn.cursor()
c.execute("SELECT config_value FROM sys_config WHERE config_key='collect_cookie'")
cookies = json.loads(c.fetchone()[0])
ck = '; '.join([f"{c['name']}={c['value']}" for c in cookies])

# 获取支付类型列表
req = urllib.request.Request('https://kz.quhuhu.com/v2/c/api/common/payTypes',
    data=b'{}', headers={'Cookie': ck, 'Content-Type': 'application/json'})
r = urllib.request.urlopen(req, timeout=10)
data = json.loads(r.read())
print("=== payTypes API ===")
print(json.dumps(data, indent=2, ensure_ascii=False))

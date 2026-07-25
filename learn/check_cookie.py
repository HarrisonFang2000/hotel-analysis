import sqlite3
db = sqlite3.connect('data/hotel_data.db')
rows = db.execute("SELECT config_key, config_value FROM sys_config WHERE config_key IN ('order_status', 'collect_cookie', 'quhuhu_username')").fetchall()
for k, v in rows:
    if k == 'collect_cookie':
        print(f'{k}: (长度={len(v)}, 前80字符={v[:80]})')
    else:
        print(f'{k}: {v}')
db.close()

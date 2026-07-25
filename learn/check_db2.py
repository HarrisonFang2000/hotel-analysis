import sqlite3
db = sqlite3.connect('data/hotel_data.db')
db.row_factory = sqlite3.Row

tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print('Tables:', [t[0] for t in tables])
for t in tables:
    cnt = db.execute(f'SELECT COUNT(*) FROM [{t[0]}]').fetchone()[0]
    print(f'  {t[0]}: {cnt} rows')

print()
# 最新日数据
try:
    rows = db.execute('SELECT * FROM daily_data ORDER BY date DESC LIMIT 5').fetchall()
    print('=== 日数据 (最新5条) ===')
    for r in rows:
        print(dict(r))
except Exception as e:
    print(f'daily_data error: {e}')

print()
# 最新小时数据
try:
    rows = db.execute('SELECT * FROM hourly_data ORDER BY date DESC, hour DESC LIMIT 5').fetchall()
    print('=== 小时数据 (最新5条) ===')
    for r in rows:
        print(dict(r))
except Exception as e:
    print(f'hourly_data error: {e}')

db.close()

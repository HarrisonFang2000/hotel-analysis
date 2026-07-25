import sqlite3
db = sqlite3.connect('data/hotel_data.db')
db.row_factory = sqlite3.Row

# 查表结构
for table in ['hourly_data', 'daily_data', 'monthly_data', 'quarterly_data', 'yearly_data']:
    info = db.execute(f'PRAGMA table_info({table})').fetchall()
    cols = [(c['name'], c['type']) for c in info]
    print(f'{table}: {cols}')
    print()

# 最新几条数据
print('=== hourly_data 最新2条 ===')
rows = db.execute('SELECT * FROM hourly_data ORDER BY rowid DESC LIMIT 2').fetchall()
for r in rows:
    print(dict(r))

print()
print('=== daily_data 最新2条 ===')
rows = db.execute('SELECT * FROM daily_data ORDER BY rowid DESC LIMIT 2').fetchall()
for r in rows:
    print(dict(r))

db.close()

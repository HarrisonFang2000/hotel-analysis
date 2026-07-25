import sqlite3
db = sqlite3.connect('data/hotel_data.db')
db.row_factory = sqlite3.Row

print('=== 日报数据 (全部) ===')
rows = db.execute('SELECT data_date, sold_rooms, total_revenue, occupancy_rate, revpar FROM daily_data ORDER BY data_date').fetchall()
for r in rows:
    print(dict(r))

print(f'\n=== 月报数据 ({db.execute("SELECT COUNT(*) FROM monthly_data").fetchone()[0]}条) ===')
rows = db.execute('SELECT * FROM monthly_data ORDER BY data_year, data_month').fetchall()
for r in rows:
    print(dict(r))

print(f'\n=== 季报数据 ({db.execute("SELECT COUNT(*) FROM quarterly_data").fetchone()[0]}条) ===')
rows = db.execute('SELECT * FROM quarterly_data ORDER BY data_year, data_quarter').fetchall()
for r in rows:
    print(dict(r))

print(f'\n=== 年报数据 ({db.execute("SELECT COUNT(*) FROM yearly_data").fetchone()[0]}条) ===')
rows = db.execute('SELECT * FROM yearly_data ORDER BY data_year').fetchall()
for r in rows:
    print(dict(r))

db.close()

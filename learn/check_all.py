import sqlite3
conn = sqlite3.connect('data/hotel_data.db')
c = conn.cursor()

tables = ['hourly_data', 'daily_data', 'monthly_data', 'quarterly_data', 'yearly_data']
for t in tables:
    c.execute(f"SELECT COUNT(*) FROM {t}")
    cnt = c.fetchone()[0]
    if cnt > 0:
        c.execute(f"SELECT * FROM {t} ORDER BY rowid DESC LIMIT 3")
        rows = c.fetchall()
        print(f"\n{t} ({cnt} rows), latest:")
        for r in rows:
            print(f"  {[x for x in r]}")
    else:
        print(f"\n{t}: EMPTY")

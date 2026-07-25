import sqlite3
db = sqlite3.connect('data/hotel.db')
tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print('Tables:', [t[0] for t in tables])
for t in tables:
    cnt = db.execute(f'SELECT COUNT(*) FROM [{t[0]}]').fetchone()[0]
    print(f'  {t[0]}: {cnt} rows')
db.close()

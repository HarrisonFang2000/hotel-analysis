import sqlite3
db = sqlite3.connect('data/hotel_data.db')
db.row_factory = sqlite3.Row
rows = db.execute("SELECT data_date, data_hour, sold_rooms, total_revenue, create_time FROM hourly_data WHERE data_date='2026-07-20' ORDER BY data_hour").fetchall()
print(f'=== 2026-07-20 小时数据 ({len(rows)}条) ===')
for r in rows:
    print(f'  hour={r["data_hour"]:2d}  rooms={r["sold_rooms"]:3d}  fee=¥{r["total_revenue"]:>10}  time={r["create_time"]}')
db.close()

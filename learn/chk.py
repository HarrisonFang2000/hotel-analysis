import sqlite3
conn = sqlite3.connect('data/hotel_data.db')
c = conn.cursor()
c.execute("SELECT data_date, data_hour, sold_rooms, total_revenue, min_price FROM hourly_data WHERE data_date='2026-07-19' ORDER BY data_hour")
rows = c.fetchall()
print("hourly_data for 2026-07-19:")
for r in rows:
    print(f"  hour={r[1]}, rooms={r[2]}, fee={r[3]}, min={r[4]}")
if not rows:
    print("  (empty)")

# Also check daily
c.execute("SELECT data_date, sold_rooms, total_revenue, min_price FROM daily_data WHERE data_date='2026-07-19'")
d = c.fetchone()
print(f"\ndaily_data for 2026-07-19: {d}")

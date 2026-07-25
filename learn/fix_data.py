import sqlite3, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.scheduler import quarterly_aggregate_for_quarter, yearly_aggregate_for_year

conn = sqlite3.connect('data/hotel_data.db')
c = conn.cursor()

# 清理零数据
c.execute("DELETE FROM hourly_data WHERE sold_rooms=0 AND total_revenue=0")
print(f"清理hourly零数据: {c.rowcount} 行")

c.execute("DELETE FROM daily_data WHERE sold_rooms=0 AND total_revenue=0")
print(f"清理daily零数据: {c.rowcount} 行")

conn.commit()

# 统计剩余
c.execute("SELECT COUNT(*), MIN(data_date), MAX(data_date) FROM daily_data")
r = c.fetchone()
print(f"\ndaily_data: {r[0]}行, {r[1]}~{r[2]}")

c.execute("SELECT COUNT(*), MIN(data_date), MAX(data_date) FROM hourly_data WHERE data_hour=24")
r = c.fetchone()
print(f"hourly(h24): {r[0]}行, {r[1]}~{r[2]}")

c.execute("SELECT * FROM monthly_data")
print(f"\nmonthly_data: {c.fetchall()}")

# 补算季度和年度
print("\n补算季度...")
for year in [2026, 2025]:
    for q in range(1, 5):
        try:
            quarterly_aggregate_for_quarter(year, q)
            print(f"  {year}Q{q} OK")
        except Exception as e:
            print(f"  {year}Q{q}: {e}")

print("\n补算年度...")
for year in [2026, 2025]:
    try:
        yearly_aggregate_for_year(year)
        print(f"  {year} OK")
    except Exception as e:
        print(f"  {year}: {e}")

c.execute("SELECT COUNT(*) FROM quarterly_data")
print(f"\nquarterly_data: {c.fetchone()[0]}行")
c.execute("SELECT COUNT(*) FROM yearly_data")
print(f"yearly_data: {c.fetchone()[0]}行")

conn.close()
print("\n完成!")

import sys, os, sqlite3
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.scheduler import daily_aggregate

conn = sqlite3.connect('data/hotel_data.db')
c = conn.cursor()

# 找出有小时数据但没日报的日期
c.execute("""
    SELECT DISTINCT h.data_date FROM hourly_data h 
    WHERE h.data_hour=24 AND h.sold_rooms>0
    AND h.data_date NOT IN (SELECT data_date FROM daily_data WHERE sold_rooms>0)
    ORDER BY h.data_date
""")
missing = [r[0] for r in c.fetchall()]
print(f"缺失日报的日期: {len(missing)} 天")
for d in missing:
    try:
        daily_aggregate(d)
        print(f"  {d} ✓")
    except Exception as e:
        print(f"  {d} ✗ {e}")
print("完成")

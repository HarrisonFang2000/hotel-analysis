"""全量重建月报、季报、年报"""
import sqlite3
import calendar
import os

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'hotel_data.db')
TOTAL_ROOMS = 113

def round2(v):
    return round(float(v), 2)

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

# 1. 获取所有日报数据，按月汇总
print('=== 重建月报 ===')
monthly_agg = {}
rows = db.execute('SELECT data_date, sold_rooms, total_revenue FROM daily_data ORDER BY data_date').fetchall()
for r in rows:
    ym = r['data_date'][:7]  # YYYY-MM
    if ym not in monthly_agg:
        monthly_agg[ym] = {'sold': 0, 'fee': 0.0}
    monthly_agg[ym]['sold'] += r['sold_rooms']
    monthly_agg[ym]['fee'] += r['total_revenue']

for ym in sorted(monthly_agg.keys()):
    year, month = int(ym[:4]), int(ym[5:7])
    total_sold = monthly_agg[ym]['sold']
    total_fee = monthly_agg[ym]['fee']
    days_in_month = calendar.monthrange(year, month)[1]
    
    occupancy = round2(total_sold / (TOTAL_ROOMS * days_in_month) * 100)
    revpar = round2(total_fee / (TOTAL_ROOMS * days_in_month))
    adr = round2(total_fee / total_sold) if total_sold > 0 else 0.0
    
    db.execute("""
        INSERT OR REPLACE INTO monthly_data (data_year, data_month, days, sold_rooms, occupancy_rate, revpar, total_revenue, adr)
        VALUES (?,?,?,?,?,?,?,?)
    """, (year, month, days_in_month, total_sold, occupancy, revpar, round2(total_fee), adr))
    print(f'  {ym}: {total_sold}间, ¥{total_fee}, 出租率{occupancy}%, RevPar¥{revpar}, ADR¥{adr}')

# 2. 重建季报（从月报汇总）
print('\n=== 重建季报 ===')
quarterly_agg = {}
for ym, data in monthly_agg.items():
    year, month = int(ym[:4]), int(ym[5:7])
    quarter = (month - 1) // 3 + 1
    key = (year, quarter)
    if key not in quarterly_agg:
        quarterly_agg[key] = {'sold': 0, 'fee': 0.0}
    quarterly_agg[key]['sold'] += data['sold']
    quarterly_agg[key]['fee'] += data['fee']

for (year, quarter) in sorted(quarterly_agg.keys()):
    total_sold = quarterly_agg[(year, quarter)]['sold']
    total_fee = quarterly_agg[(year, quarter)]['fee']
    
    # 计算季度天数
    months = [(quarter-1)*3+1, (quarter-1)*3+2, (quarter-1)*3+3]
    total_days = sum(calendar.monthrange(year, m)[1] for m in months)
    
    occupancy = round2(total_sold / (TOTAL_ROOMS * total_days) * 100)
    revpar = round2(total_fee / (TOTAL_ROOMS * total_days))
    adr = round2(total_fee / total_sold) if total_sold > 0 else 0.0
    
    db.execute("""
        INSERT OR REPLACE INTO quarterly_data (data_year, data_quarter, days, sold_rooms, occupancy_rate, revpar, total_revenue, adr)
        VALUES (?,?,?,?,?,?,?,?)
    """, (year, quarter, total_days, total_sold, occupancy, revpar, round2(total_fee), adr))
    print(f'  {year} Q{quarter}: {total_sold}间, ¥{total_fee}, {total_days}天')

# 3. 重建年报（从月报汇总）
print('\n=== 重建年报 ===')
yearly_agg = {}
for ym, data in monthly_agg.items():
    year = int(ym[:4])
    if year not in yearly_agg:
        yearly_agg[year] = {'sold': 0, 'fee': 0.0}
    yearly_agg[year]['sold'] += data['sold']
    yearly_agg[year]['fee'] += data['fee']

# 统计每年有效天数
year_days = {}
for r in rows:
    year = int(r['data_date'][:4])
    year_days[year] = year_days.get(year, 0) + 1

for year in sorted(yearly_agg.keys()):
    total_sold = yearly_agg[year]['sold']
    total_fee = yearly_agg[year]['fee']
    valid_days = year_days.get(year, 0)
    
    occupancy = round2(total_sold / (TOTAL_ROOMS * valid_days) * 100) if valid_days > 0 else 0
    revpar = round2(total_fee / (TOTAL_ROOMS * valid_days)) if valid_days > 0 else 0
    adr = round2(total_fee / total_sold) if total_sold > 0 else 0.0
    
    db.execute("""
        INSERT OR REPLACE INTO yearly_data (data_year, valid_days, sold_rooms, occupancy_rate, revpar, total_revenue, adr)
        VALUES (?,?,?,?,?,?,?)
    """, (year, valid_days, total_sold, occupancy, revpar, round2(total_fee), adr))
    print(f'  {year}: {total_sold}间, ¥{total_fee}, {valid_days}天')

db.commit()
db.close()
print('\n✅ 全量重建完成！')

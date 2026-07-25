"""
图表数据接口
给前端ECharts提供数据
"""
from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta

from app.db.database import db_transaction
from app.schemas.common import ApiResponse
from app.utils.validator import validate_date

router = APIRouter(prefix="/api/chart", tags=["图表接口"])


@router.get("/hourly/trend", summary="小时趋势数据")
def get_hourly_trend(date: str):
    """获取指定日期小时趋势，双Y轴：房费柱+单房收益线"""
    if not validate_date(date):
        raise HTTPException(status_code=400, detail="日期格式错误")
    
    with db_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT data_hour, total_revenue, revpar, occupancy_rate, adr
            FROM hourly_data
            WHERE data_date = ?
            ORDER BY data_hour
        """, (date,))
        data = [dict(row) for row in cursor.fetchall()]
        
        # 补全1-24点
        data_map = {d["data_hour"]: d for d in data}
        hours = list(range(1, 25))
        revenues = []
        revpars = []
        occupancy = []
        adrs = []
        
        for h in hours:
            if h in data_map:
                revenues.append(data_map[h]["total_revenue"])
                revpars.append(data_map[h]["revpar"])
                occupancy.append(data_map[h]["occupancy_rate"])
                adrs.append(data_map[h]["adr"])
            else:
                revenues.append(0)
                revpars.append(0)
                occupancy.append(0)
                adrs.append(0)
        
        return ApiResponse.success({
            "hours": [f"{h}:00" for h in hours],
            "total_revenue": revenues,
            "revpar": revpars,
            "occupancy_rate": occupancy,
            "adr": adrs
        })


@router.get("/daily/trend", summary="日趋势数据")
def get_daily_trend(days: int = 30):
    """获取最近N天日趋势"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    with db_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT data_date, total_revenue, revpar, occupancy_rate, sold_rooms, adr
            FROM daily_data
            WHERE data_date >= ? AND data_date <= ?
            ORDER BY data_date
        """, (start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")))
        data = [dict(row) for row in cursor.fetchall()]
        
        return ApiResponse.success({
            "dates": [d["data_date"] for d in data],
            "total_revenue": [d["total_revenue"] for d in data],
            "revpar": [d["revpar"] for d in data],
            "occupancy_rate": [d["occupancy_rate"] for d in data],
            "sold_rooms": [d["sold_rooms"] for d in data],
            "adr": [d["adr"] for d in data]
        })


@router.get("/heatmap", summary="入住率热力图数据")
def get_heatmap_data(year: int, month: int):
    """获取指定月份小时入住率热力图，X轴日期，Y轴小时"""
    with db_transaction() as conn:
        cursor = conn.cursor()
        # 获取当月所有数据
        month_str = f"{year}-{month:02d}"
        cursor.execute("""
            SELECT data_date, data_hour, occupancy_rate
            FROM hourly_data
            WHERE data_date LIKE ?
            ORDER BY data_date, data_hour
        """, (f"{month_str}%",))
        data = cursor.fetchall()
        
        # 转换为热力图格式：[x索引, y索引, 值]
        # 先获取当月天数
        import calendar
        days = calendar.monthrange(year, month)[1]
        
        heatmap_data = []
        for row in data:
            day = int(row["data_date"].split("-")[2]) - 1
            hour = row["data_hour"] - 1
            heatmap_data.append([day, hour, row["occupancy_rate"]])
        
        return ApiResponse.success({
            "days": days,
            "data": heatmap_data
        })


@router.get("/weekday", summary="星期规律数据")
def get_weekday_data():
    """按星期统计平均入住率和单房收益"""
    weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    result = {name: {"occupancy": 0, "revpar": 0, "count": 0} for name in weekday_names}
    
    with db_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT data_date, occupancy_rate, revpar FROM daily_data")
        for row in cursor.fetchall():
            date_obj = datetime.strptime(row["data_date"], "%Y-%m-%d")
            weekday = date_obj.weekday()
            name = weekday_names[weekday]
            result[name]["occupancy"] += row["occupancy_rate"]
            result[name]["revpar"] += row["revpar"]
            result[name]["count"] += 1
    
    # 计算平均值
    avg_occupancy = []
    avg_revpar = []
    for name in weekday_names:
        if result[name]["count"] > 0:
            avg_occupancy.append(round(result[name]["occupancy"] / result[name]["count"], 2))
            avg_revpar.append(round(result[name]["revpar"] / result[name]["count"], 2))
        else:
            avg_occupancy.append(0)
            avg_revpar.append(0)
    
    return ApiResponse.success({
        "weekdays": weekday_names,
        "avg_occupancy": avg_occupancy,
        "avg_revpar": avg_revpar
    })


@router.get("/price-scatter", summary="定价象限散点图")
def get_price_scatter_data(days: int = 90):
    """价格vs入住率散点图，用于定价分析"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    with db_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT min_price, occupancy_rate, data_date
            FROM daily_data
            WHERE data_date >= ? AND data_date <= ? AND min_price > 0
        """, (start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")))
        data = [dict(row) for row in cursor.fetchall()]
        
        return ApiResponse.success([
            [d["min_price"], d["occupancy_rate"], d["data_date"]]
            for d in data
        ])

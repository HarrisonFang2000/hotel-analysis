# -*- coding: utf-8 -*-
"""导入导出接口"""
import os
import uuid
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
import pandas as pd

from app.db.database import db_transaction
from app.schemas.common import ApiResponse
from app.core.data_cleaner import DataCleaner
from app.core.calculator import calc_hourly
from app.constants import IMPORT_DIR, EXPORT_DIR, DataSource, MAX_HOUR
from app.core.scheduler import daily_aggregate, monthly_aggregate_for_month, quarterly_aggregate_for_quarter, yearly_aggregate_for_year
from app.core.collector import auto_collect
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/io", tags=["导入导出"])
cleaner = DataCleaner()


def _trigger_recalc(date_str: str) -> None:
    """导入后触发日报月报重算"""
    from datetime import datetime as _dt
    dt = _dt.strptime(date_str, "%Y-%m-%d")
    daily_aggregate(date_str)
    monthly_aggregate_for_month(dt.year, dt.month)


@router.post("/import/excel", summary="导入Excel报表（支持单文件或双文件核对）")
async def import_excel(
    room_sale_file: UploadFile = File(None),
    source_detail_file: UploadFile = File(None),
):
    """
    手动导入报表：
    - room_sale_file: 客房销售报表 Excel
    - source_detail_file: 订单来源明细 Excel（可选，用于核对和提取OTA起售价）
    
    核对逻辑：
    1. 客房销售报表提供：房间数、总房费
    2. 订单来源明细提供：渠道分布、OTA起售价（排除线下客人）
    3. 交叉验证：两表总房费是否一致
    """
    try:
        os.makedirs(IMPORT_DIR, exist_ok=True)
        result = {
            "room_sale": None,
            "source_detail": None,
            "cross_check": None,
            "final": {},
            "warnings": [],
        }
        
        # ========== 1. 解析客房销售报表 ==========
        if room_sale_file is None:
            raise HTTPException(status_code=400, detail="请至少上传客房销售报表")
        
        room_path = os.path.join(IMPORT_DIR, f"manual_room_{uuid.uuid4().hex[:8]}.xls")
        with open(room_path, "wb") as f:
            f.write(await room_sale_file.read())
        
        report_date, room_data, room_errors = cleaner.parse_excel(room_path)
        if room_errors:
            raise HTTPException(status_code=400, detail="客房销售报表解析失败: " + ";".join(room_errors))
        
        result["room_sale"] = {
            "date": report_date,
            "room_count": room_data["room_count"],
            "total_fee": room_data["total_fee"],
            "min_price": room_data["min_price"],
        }
        logger.info(f"客房销售报表: {result['room_sale']}")
        
        # ========== 2. 解析订单来源明细（可选）==========
        ota_min_price = room_data["min_price"]  # 默认用全部最低价
        source_channels = []
        
        if source_detail_file is not None:
            source_path = os.path.join(IMPORT_DIR, f"manual_source_{uuid.uuid4().hex[:8]}.xls")
            with open(source_path, "wb") as f:
                f.write(await source_detail_file.read())
            
            source_data = cleaner.parse_source_excel(source_path)
            source_channels = source_data.get("channels", [])
            
            online_revenue = sum(
                ch["revenue"] for ch in source_channels
                if "线下" not in ch.get("channel", "") and "现付" not in ch.get("pay_type", "")
            )
            offline_revenue = sum(
                ch["revenue"] for ch in source_channels
                if "线下" in ch.get("channel", "") or "现付" in ch.get("pay_type", "")
            )
            total_source_revenue = online_revenue + offline_revenue
            
            # OTA起售价：从订单来源明细中推算（非线下渠道的最低房价）
            # 如果有渠道级别的均价数据，取线上渠道中最低的
            ota_prices = []
            for ch in source_channels:
                if "线下" not in ch.get("channel", "") and "现付" not in ch.get("pay_type", ""):
                    nights = ch.get("room_nights", 0)
                    rev = ch.get("revenue", 0)
                    if nights > 0:
                        ota_prices.append(rev / nights)
            if ota_prices:
                ota_min_price = round(min(ota_prices), 2)
            
            result["source_detail"] = {
                "channels": source_channels,
                "online_revenue": online_revenue,
                "offline_revenue": offline_revenue,
                "total_revenue": total_source_revenue,
                "ota_min_price": ota_min_price,
            }
            logger.info(f"订单来源明细: 线上¥{online_revenue}, 线下¥{offline_revenue}, OTA起售价¥{ota_min_price}")
            
            # ========== 3. 交叉核对 ==========
            room_total = room_data["total_fee"]
            diff = abs(room_total - total_source_revenue)
            diff_pct = (diff / room_total * 100) if room_total > 0 else 0
            
            result["cross_check"] = {
                "room_sale_total": room_total,
                "source_detail_total": total_source_revenue,
                "difference": round(diff, 2),
                "diff_percent": round(diff_pct, 2),
                "is_match": diff < 1.0 or diff_pct < 1.0,
            }
            
            if not result["cross_check"]["is_match"]:
                result["warnings"].append(
                    f"⚠️ 两表房费不一致: 客房销售¥{room_total} vs 订单来源¥{total_source_revenue}，差异¥{diff}"
                )
            else:
                result["warnings"].append(
                    f"✅ 核对通过: 两表房费一致 (差异¥{diff})"
                )
        
        # ========== 4. 数据入库 ==========
        from datetime import datetime as _dt
        try:
            from zoneinfo import ZoneInfo
            TZ = ZoneInfo("Asia/Shanghai")
        except ImportError:
            import pytz
            TZ = pytz.timezone("Asia/Shanghai")
        now = _dt.now(TZ)
        current_hour = now.hour if now.hour != 0 else MAX_HOUR
        
        final_rooms = room_data["room_count"]
        final_fee = room_data["total_fee"]
        final_min = ota_min_price  # 优先用OTA起售价
        
        hourly_data = calc_hourly(final_rooms, final_fee, final_min)
        
        with db_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO hourly_data "
                "(data_date, data_hour, sold_rooms, available_rooms, occupancy_rate, min_price, revpar, total_revenue, adr, data_source) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    report_date, current_hour,
                    hourly_data["sold_rooms"], hourly_data["available_rooms"],
                    hourly_data["occupancy_rate"], hourly_data["min_price"],
                    hourly_data["revpar"], hourly_data["total_revenue"],
                    hourly_data["adr"],
                    DataSource.MANUAL_INPUT
                )
            )
            cursor.execute(
                "INSERT INTO import_record (file_name, report_type, data_date, import_status) "
                "VALUES (?, ?, ?, 1)",
                (room_sale_file.filename or "手动导入", "manual_dual", report_date)
            )
        
        if current_hour == MAX_HOUR:
            _trigger_recalc(report_date)
        
        result["final"] = {
            "date": report_date,
            "hour": current_hour,
            "sold_rooms": final_rooms,
            "total_revenue": final_fee,
            "ota_min_price": final_min,
        }
        result["success"] = True
        
        return ApiResponse.success(result, message=f"导入成功: {report_date} {final_rooms}间 ¥{final_fee}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"导入失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import/auto-collect", summary="单日自动采集")
def auto_collect_single(date: str):
    """
    单日自动采集：从去呼呼API导出当天客房销售数据并入库。
    凌晨0点自动切换为采集昨天h24结算数据。
    """
    from app.core.collector import auto_collect
    from datetime import datetime as _dt
    
    # 确定正确的采集日期和小时
    try:
        from zoneinfo import ZoneInfo
        TZ = ZoneInfo("Asia/Shanghai")
    except ImportError:
        import pytz
        TZ = pytz.timezone("Asia/Shanghai")
    
    now = _dt.now(TZ)
    data_hour = None
    actual_date = date if date else now.strftime("%Y-%m-%d")
    
    if now.hour == 0:
        # 凌晨0点：如用户请求"今天"，实际采集昨天h24结算
        today_str = now.strftime("%Y-%m-%d")
        if actual_date == today_str:
            from datetime import timedelta
            actual_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        data_hour = 24
    
    result = auto_collect(actual_date, data_hour)
    errors = result.get("errors", [])
    # API导出失败（当天无数据）不算错误，返回空数据
    if not result.get("success"):
        if errors and any("API导出失败" in e for e in errors):
            return ApiResponse.success({
                "success": True,
                "date": result.get("date", actual_date),
                "total_sold": 0,
                "total_revenue": 0.0,
            }, message="当天暂无客房数据，请稍后再试或检查Cookie是否有效")
        raise HTTPException(status_code=500, detail="采集失败: " + ";".join(errors))
    return ApiResponse.success({
        "success": True,
        "date": result["date"],
        "total_sold": result["total_sold"],
        "total_revenue": result["total_revenue"],
    }, message=f"采集完成: {result['date']} {result['total_sold']}间, ¥{result['total_revenue']}")


@router.post("/import/auto-collect-history", summary="批量采集历史数据（按月导出，极速）")
def auto_collect_history(start_date: str, end_date: str = ""):
    """
    批量采集历史数据。按月导出Excel（一次一个月，每列一天），逐日核算入库。
    比逐日采集快30倍。
    """
    from datetime import datetime as _dt, timedelta as _td
    import calendar
    from app.core.collector import QuhuhuCollector
    
    if not end_date:
        end_date = _dt.now().strftime("%Y-%m-%d")
    
    d1 = _dt.strptime(start_date, "%Y-%m-%d")
    d2 = _dt.strptime(end_date, "%Y-%m-%d")
    if d1 > d2:
        raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")
    
    total_days = (d2 - d1).days + 1
    if total_days > 366:
        raise HTTPException(status_code=400, detail="日期范围不能超过366天")
    
    results = []
    success_count = 0
    errors = []
    collector = QuhuhuCollector()
    collector._preload_config()
    cookie_str = collector._load_cookie_string()
    if not cookie_str:
        raise HTTPException(status_code=400, detail="未找到登录Cookie，请先一键读取Cookie")
    
    # 按月批量导出
    current_month = _dt(d1.year, d1.month, 1)
    end_month = _dt(d2.year, d2.month, 1)
    
    while current_month <= end_month:
        # 计算当月范围
        month_start = max(d1, current_month)
        last_day = calendar.monthrange(current_month.year, current_month.month)[1]
        month_end = min(d2, _dt(current_month.year, current_month.month, last_day))
        
        if month_start > month_end:
            current_month = _dt(current_month.year + (current_month.month // 12), 
                               ((current_month.month % 12) + 1), 1)
            continue
        
        try:
            logger.info(f"导出月份: {current_month.strftime('%Y-%m')}")
            
            # 客房销售报表
            room_path = collector._api_collect_by_range(
                month_start.strftime("%Y-%m-%d"),
                month_end.strftime("%Y-%m-%d"),
                pay_type=""
            )
            
            # OTA起售价（全额预付）
            ota_path = collector._api_collect_by_range(
                month_start.strftime("%Y-%m-%d"),
                month_end.strftime("%Y-%m-%d"),
                pay_type="tyf"
            )
            
            if not room_path:
                errors.append(f"{current_month.strftime('%Y-%m')}: 导出失败")
                current_month = _dt(current_month.year + (current_month.month // 12),
                                   ((current_month.month % 12) + 1), 1)
                continue
            
            # 解析月度数据
            daily_data = cleaner.parse_monthly_excel(room_path)
            ota_daily = {}
            if ota_path:
                ota_data = cleaner.parse_monthly_excel(ota_path)
                ota_daily = {d["date"]: d["min_price"] for d in ota_data if d["min_price"] > 0}
            
            # 逐日入库（单事务批量写入 hourly + daily）
            with db_transaction() as conn:
                c = conn.cursor()
                for day in daily_data:
                    date_str = day["date"]
                    if date_str < start_date or date_str > end_date:
                        continue
                    
                    ota_min = ota_daily.get(date_str, day["min_price"])
                    
                    try:
                        hd = calc_hourly(day["room_count"], day["total_fee"], ota_min)
                        # 写小时数据
                        c.execute(
                            """INSERT OR REPLACE INTO hourly_data
                               (data_date, data_hour, sold_rooms, available_rooms,
                                occupancy_rate, min_price, revpar, total_revenue, adr, data_source)
                               VALUES (?,24,?,?,?,?,?,?,?,?)""",
                            (date_str, hd["sold_rooms"], hd["available_rooms"],
                             hd["occupancy_rate"], hd["min_price"], hd["revpar"],
                             hd["total_revenue"], hd["adr"], DataSource.AUTO_IMPORT)
                        )
                        # 同时写日报数据（省去daily_aggregate）
                        c.execute(
                            """INSERT OR REPLACE INTO daily_data
                               (data_date, min_price, sold_rooms, remain_rooms,
                                occupancy_rate, revpar, total_revenue, adr, data_source)
                               VALUES (?,?,?,?,?,?,?,?,?)""",
                            (date_str, hd["min_price"], hd["sold_rooms"],
                             hd["available_rooms"], hd["occupancy_rate"],
                             hd["revpar"], hd["total_revenue"], hd["adr"], DataSource.AUTO_IMPORT)
                        )
                        c.execute(
                            "INSERT OR REPLACE INTO import_record (file_name, report_type, data_date, import_status) VALUES (?,?,?,1)",
                            (f"历史采集_{date_str}", "history_auto", date_str)
                        )
                        
                        success_count += 1
                        results.append({
                            "date": date_str,
                            "rooms": day["room_count"],
                            "revenue": day["total_fee"],
                            "ota_min": ota_min,
                        })
                    except Exception as e:
                        errors.append(f"{date_str}: {str(e)}")
            
            logger.info(f"  月份完成: {len(daily_data)}天")
            
        except Exception as e:
            errors.append(f"{current_month.strftime('%Y-%m')}: {str(e)}")
            logger.error(f"月份导出异常: {e}")
        
        # 下一个月
        current_month = _dt(current_month.year + (current_month.month // 12),
                           ((current_month.month % 12) + 1), 1)
    
    # ===== 联动触发上层聚合（24点数据→日报→月报→季报→年报）=====
    if success_count > 0:
        # 收集涉及的年月
        from datetime import datetime as _dt
        months = set()
        years = set()
        for r in results:
            d = _dt.strptime(r["date"], "%Y-%m-%d")
            months.add((d.year, d.month))
            years.add(d.year)
        
        # 逐月重算
        for year, month in sorted(months):
            try:
                monthly_aggregate_for_month(year, month)
            except Exception:
                pass
        
        # 逐季重算（涉及月份所在的季度）
        quarters = set()
        for year, month in months:
            q = (month - 1) // 3 + 1
            quarters.add((year, q))
        for year, q in sorted(quarters):
            try:
                quarterly_aggregate_for_quarter(year, q)
            except Exception:
                pass
        
        # 逐年重算
        for year in sorted(years):
            try:
                yearly_aggregate_for_year(year)
            except Exception:
                pass
    
    return ApiResponse.success({
        "total_days": total_days,
        "success_count": success_count,
        "fail_count": len(errors),
        "results": results[-30:],
        "errors": errors[-10:],
    }, message=f"历史采集完成: {success_count}/{total_days} 天成功")


@router.get("/export/order-flow", summary="导出订单流速表")
def export_order_flow(start_date: str, end_date: str):
    """导出专业订单流速表Excel，含每日总览+小时流速+渠道分析"""
    from fastapi.responses import StreamingResponse
    from app.core.order_flow import generate_order_flow_report
    
    try:
        output = generate_order_flow_report(start_date, end_date)
        from urllib.parse import quote
        filename = f"订单流速表_{start_date}_{end_date}.xlsx"
        encoded_filename = quote(filename)
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")


@router.get("/export/excel", summary="导出指定日期范围数据")
def export_excel(start_date: str, end_date: str):
    """导出数据为Excel"""
    try:
        os.makedirs(EXPORT_DIR, exist_ok=True)
        with db_transaction() as conn:
            df_daily = pd.read_sql(
                "SELECT data_date as 日期, min_price as 起售价, sold_rooms as 售出房间, "
                "remain_rooms as 剩余房间, occupancy_rate as 出租率, revpar as 单房收益, "
                "total_revenue as 累计房费 FROM daily_data "
                "WHERE data_date >= ? AND data_date <= ? ORDER BY data_date",
                conn, params=(start_date, end_date)
            )
            df_hourly = pd.read_sql(
                "SELECT data_date as 日期, data_hour as 小时, sold_rooms as 已售房间, "
                "available_rooms as 可售房间, occupancy_rate as 出租率, min_price as 起售价, "
                "revpar as 单房收益, total_revenue as 累计房费 FROM hourly_data "
                "WHERE data_date >= ? AND data_date <= ? ORDER BY data_date, data_hour",
                conn, params=(start_date, end_date)
            )

        export_name = f"酒店数据_{start_date}_{end_date}.xlsx"
        export_path = os.path.join(EXPORT_DIR, export_name)

        with pd.ExcelWriter(export_path, engine="openpyxl") as writer:
            df_daily.to_excel(writer, sheet_name="日报数据", index=False)
            df_hourly.to_excel(writer, sheet_name="小时数据", index=False)

        return FileResponse(
            export_path,
            filename=export_name,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        logger.error(f"导出Excel失败：{str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"导出失败：{str(e)}")


@router.get("/export/report", summary="通用报表导出（支持6种类型）")
def export_report(type: str, start_date: str, end_date: str = ""):
    """
    通用导出：type=hourly|daily|weekly|monthly|quarterly|yearly
    """
    import pandas as pd
    
    type_labels = {
        'hourly': ('小时报', 'hourly_data', 'data_date,data_hour'),
        'daily': ('日报', 'daily_data', 'data_date'),
        'monthly': ('月报', 'monthly_data', 'data_year,data_month'),
        'quarterly': ('季报', 'quarterly_data', 'data_year,data_quarter'),
        'yearly': ('年报', 'yearly_data', 'data_year'),
    }
    
    if type not in type_labels:
        raise HTTPException(status_code=400, detail=f"不支持的报表类型: {type}，可选: {','.join(type_labels.keys())}")
    
    label, table, _ = type_labels[type]
    
    try:
        os.makedirs(EXPORT_DIR, exist_ok=True)
        
        with db_transaction() as conn:
            if type == 'hourly':
                df = pd.read_sql(
                    "SELECT data_date as 日期, data_hour as 小时, sold_rooms as 已售房间, "
                    "available_rooms as 可售房间, occupancy_rate as 出租率, min_price as 起售价格, "
                    "revpar as 单房收益, adr as 平均房价, total_revenue as 累计房费 "
                    "FROM hourly_data WHERE data_date >= ? AND data_date <= ? "
                    "ORDER BY data_date, data_hour",
                    conn, params=(start_date, end_date or start_date)
                )
            elif type == 'daily':
                df = pd.read_sql(
                    "SELECT data_date as 日期, min_price as 起售价格, sold_rooms as 售出房间, "
                    "remain_rooms as 剩余房间, occupancy_rate as 出租率, "
                    "revpar as 单房收益, adr as 平均房价, total_revenue as 累计房费 "
                    "FROM daily_data WHERE data_date >= ? AND data_date <= ? "
                    "ORDER BY data_date",
                    conn, params=(start_date, end_date or start_date)
                )
            elif type == 'monthly':
                df = pd.read_sql(
                    "SELECT data_year as 年份, data_month as 月份, days as 天数, "
                    "sold_rooms as 售出房间, occupancy_rate as 出租率, "
                    "revpar as 单房收益, adr as 平均房价, total_revenue as 累计房费 "
                    "FROM monthly_data WHERE (data_year||'-'||printf('%02d',data_month)) >= ? "
                    "AND (data_year||'-'||printf('%02d',data_month)) <= ? ORDER BY data_year, data_month",
                    conn, params=(start_date[:7] if start_date else '2020-01', end_date[:7] if end_date else '2099-12')
                )
            elif type == 'quarterly':
                df = pd.read_sql(
                    "SELECT data_year||'Q'||data_quarter as 季度, days as 天数, "
                    "sold_rooms as 售出房间, occupancy_rate as 出租率, "
                    "revpar as 单房收益, adr as 平均房价, total_revenue as 累计房费 "
                    "FROM quarterly_data ORDER BY data_year, data_quarter",
                    conn
                )
                if start_date:
                    year = int(start_date[:4])
                    df = df[df['季度'].str.startswith(str(year))]
            elif type == 'yearly':
                df = pd.read_sql(
                    "SELECT data_year as 年份, valid_days as 有效天数, "
                    "sold_rooms as 售出房间, occupancy_rate as 出租率, "
                    "revpar as 单房收益, adr as 平均房价, total_revenue as 累计房费 "
                    "FROM yearly_data ORDER BY data_year",
                    conn
                )
        
        if df.empty:
            raise HTTPException(status_code=404, detail="所选范围无数据")
        
        export_name = f"{label}_{start_date}_{end_date or start_date}.xlsx".replace(':', '').replace(' ', '_')
        export_path = os.path.join(EXPORT_DIR, export_name)
        df.to_excel(export_path, index=False)
        
        return FileResponse(
            export_path,
            filename=export_name,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"导出{label}失败：{str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"导出失败：{str(e)}")

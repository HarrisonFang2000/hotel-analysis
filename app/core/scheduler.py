"""
定时任务调度
使用APScheduler实现所有定时任务
"""
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import json

from app.db.database import db_transaction
from app.core.calculator import calc_daily, calc_monthly, calc_quarterly, calc_yearly
from app.utils.backup import backup_database
from app.utils.logger import get_logger
from app.constants import DataSource, DEFAULT_TIMEZONE

logger = get_logger(__name__)
scheduler = BackgroundScheduler(timezone=DEFAULT_TIMEZONE)

# 时区对象
try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo(DEFAULT_TIMEZONE)
except ImportError:
    # Python 3.8 fallback
    import pytz
    TZ = pytz.timezone(DEFAULT_TIMEZONE)


def now_local() -> datetime:
    """获取当前本地时间"""
    return datetime.now(TZ)


def today_str() -> str:
    """获取当前本地日期字符串 YYYY-MM-DD"""
    return now_local().strftime("%Y-%m-%d")


def get_config_value(key: str, default: str = "") -> str:
    """从数据库获取配置值"""
    with db_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT config_value FROM sys_config WHERE config_key = ?", (key,))
        row = cursor.fetchone()
        return row["config_value"] if row else default


def get_config_int(key: str, default: int = 0) -> int:
    """安全获取整数配置值"""
    try:
        return int(get_config_value(key, str(default)))
    except (ValueError, TypeError):
        return default


def daily_aggregate(target_date: str = "") -> None:
    """每日00:01生成前一天日报，优先h24，回退到当天最大小时"""
    logger.info("开始执行日报聚合任务")
    try:
        yesterday = target_date if target_date else (now_local() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        with db_transaction() as conn:
            cursor = conn.cursor()
            # 优先取h24，没有则回退到当天最大小时
            cursor.execute(
                "SELECT * FROM hourly_data WHERE data_date = ? AND data_hour = 24",
                (yesterday,)
            )
            hour_data = cursor.fetchone()
            
            if not hour_data:
                cursor.execute(
                    "SELECT * FROM hourly_data WHERE data_date = ? ORDER BY data_hour DESC LIMIT 1",
                    (yesterday,)
                )
                hour_data = cursor.fetchone()
            
            if not hour_data:
                logger.warning(f"{yesterday} 无任何小时数据，跳过日报生成")
                return
            
            # 计算日报数据
            daily_data = calc_daily(
                sold_rooms=hour_data["sold_rooms"],
                total_revenue=hour_data["total_revenue"],
                min_price=hour_data["min_price"]
            )
            
            # 插入或更新日报（保留手动编辑的 data_source）
            cursor.execute("SELECT data_source FROM daily_data WHERE data_date = ?", (yesterday,))
            existing = cursor.fetchone()
            ds = DataSource.AUTO_IMPORT
            if existing and existing["data_source"] and existing["data_source"] >= 2:
                ds = existing["data_source"]  # 保留手动编辑标记
            
            cursor.execute("""
                INSERT OR REPLACE INTO daily_data 
                (data_date, min_price, sold_rooms, remain_rooms, occupancy_rate, revpar, total_revenue, adr, data_source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                yesterday,
                daily_data["min_price"],
                daily_data["sold_rooms"],
                daily_data["remain_rooms"],
                daily_data["occupancy_rate"],
                daily_data["revpar"],
                daily_data["total_revenue"],
                daily_data["adr"],
                ds
            ))
            
            logger.info(f"日报生成成功：{yesterday}")
    
    except Exception as e:
        logger.error(f"日报聚合失败：{str(e)}", exc_info=True)
    
    # ★ 事务外触发月报重算
    if target_date:
        try:
            monthly_aggregate_for_date(target_date)
        except Exception:
            pass


def monthly_aggregate() -> None:
    """每月1日00:01生成上月月报"""
    logger.info("开始执行月报聚合任务")
    try:
        last_month = now_local().replace(day=1) - timedelta(days=1)
        year = last_month.year
        month = last_month.month
        monthly_aggregate_for_month(year, month)
        # 触发季报重算
        quarterly_aggregate_for_month(year, month)
    except Exception as e:
        logger.error(f"月报聚合失败：{str(e)}", exc_info=True)


def monthly_aggregate_for_date(date_str: str) -> None:
    """根据日期重算对应月报"""
    try:
        date_obj = datetime.strptime(date_str.replace('/', '-'), "%Y-%m-%d")
        monthly_aggregate_for_month(date_obj.year, date_obj.month)
    except Exception as e:
        logger.error(f"重算月报失败：{str(e)}", exc_info=True)


def monthly_aggregate_for_month(year: int, month: int) -> None:
    """重算指定月份月报"""
    logger.info(f"开始重算{year}年{month}月月报")
    try:
        month_start = f"{year}-{month:02d}-01"
        if month == 12:
            next_month_start = f"{year+1}-01-01"
        else:
            next_month_start = f"{year}-{month+1:02d}-01"
        
        with db_transaction() as conn:
            cursor = conn.cursor()
            # 汇总当月所有日报数据 + 统计有数据的实际天数
            cursor.execute("""
                SELECT SUM(sold_rooms) as total_sold, SUM(total_revenue) as total_revenue,
                       COUNT(*) as valid_days
                FROM daily_data
                WHERE data_date >= ? AND data_date < ?
            """, (month_start, next_month_start))
            agg = cursor.fetchone()
            
            total_sold = agg["total_sold"] or 0
            total_revenue = agg["total_revenue"] or 0.0
            valid_days = agg["valid_days"] or 0
            
            if total_sold == 0 and total_revenue == 0:
                logger.warning(f"{year}年{month}月无日报数据，跳过月报生成")
                return
            
            # 计算月报数据（使用实际有数据的天数）
            monthly_data = calc_monthly(year, month, total_sold, total_revenue, valid_days)
            
            # 插入或更新月报
            cursor.execute("""
                INSERT OR REPLACE INTO monthly_data
                (data_year, data_month, days, sold_rooms, occupancy_rate, revpar, total_revenue, adr)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                year,
                month,
                monthly_data["days"],
                monthly_data["sold_rooms"],
                monthly_data["occupancy_rate"],
                monthly_data["revpar"],
                monthly_data["total_revenue"],
                monthly_data["adr"]
            ))
            
            logger.info(f"月报生成成功：{year}年{month}月")
    
    except Exception as e:
        logger.error(f"月报生成失败：{str(e)}", exc_info=True)


def quarterly_aggregate() -> None:
    """每季度首月1日00:02生成上季度季报"""
    logger.info("开始执行季报聚合任务")
    try:
        last_quarter_month = now_local().replace(day=1) - timedelta(days=1)
        year = last_quarter_month.year
        month = last_quarter_month.month
        quarterly_aggregate_for_month(year, month)
        # 触发年报重算
        yearly_aggregate_for_year(year)
    except Exception as e:
        logger.error(f"季报聚合失败：{str(e)}", exc_info=True)


def quarterly_aggregate_for_month(year: int, month: int) -> None:
    """根据月份重算对应季报"""
    try:
        quarter = (month - 1) // 3 + 1
        quarterly_aggregate_for_quarter(year, quarter)
    except Exception as e:
        logger.error(f"重算季报失败：{str(e)}", exc_info=True)


def quarterly_aggregate_for_quarter(year: int, quarter: int) -> None:
    """重算指定季度季报"""
    logger.info(f"开始重算{year}年Q{quarter}季报")
    try:
        start_month = (quarter - 1) * 3 + 1
        months = [start_month, start_month+1, start_month+2]
        
        with db_transaction() as conn:
            cursor = conn.cursor()
            placeholders = ",".join(["?"] * len(months))
            cursor.execute(f"""
                SELECT SUM(sold_rooms) as total_sold, SUM(total_revenue) as total_revenue,
                       SUM(days) as valid_days
                FROM monthly_data
                WHERE data_year = ? AND data_month IN ({placeholders})
            """, (year, *months))
            agg = cursor.fetchone()
            
            total_sold = agg["total_sold"] or 0
            total_revenue = agg["total_revenue"] or 0.0
            valid_days = agg["valid_days"] or 0
            
            if total_sold == 0 and total_revenue == 0:
                logger.warning(f"{year}年Q{quarter}无月报数据，跳过季报生成")
                return
            
            # 计算季报数据（使用实际有数据的天数）
            quarterly_data = calc_quarterly(year, quarter, total_sold, total_revenue, valid_days)
            
            # 插入或更新季报
            cursor.execute("""
                INSERT OR REPLACE INTO quarterly_data
                (data_year, data_quarter, days, sold_rooms, occupancy_rate, revpar, total_revenue, adr)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                year,
                quarter,
                quarterly_data["days"],
                quarterly_data["sold_rooms"],
                quarterly_data["occupancy_rate"],
                quarterly_data["revpar"],
                quarterly_data["total_revenue"],
                quarterly_data["adr"]
            ))
            
            logger.info(f"季报生成成功：{year}年Q{quarter}")
    
    except Exception as e:
        logger.error(f"季报生成失败：{str(e)}", exc_info=True)


def yearly_aggregate() -> None:
    """每年1月1日00:03生成上年年报"""
    logger.info("开始执行年报聚合任务")
    try:
        last_year = now_local().year - 1
        yearly_aggregate_for_year(last_year)
    except Exception as e:
        logger.error(f"年报聚合失败：{str(e)}", exc_info=True)


def yearly_aggregate_for_year(year: int) -> None:
    """重算指定年份年报"""
    logger.info(f"开始重算{year}年年报")
    try:
        with db_transaction() as conn:
            cursor = conn.cursor()
            # 汇总当年月报数据
            cursor.execute("""
                SELECT SUM(sold_rooms) as total_sold, SUM(total_revenue) as total_revenue
                FROM monthly_data
                WHERE data_year = ?
            """, (year,))
            agg = cursor.fetchone()
            
            total_sold = agg["total_sold"] or 0
            total_revenue = agg["total_revenue"] or 0.0
            
            # 统计有效天数
            cursor.execute("SELECT COUNT(*) as cnt FROM daily_data WHERE data_date LIKE ?", (f"{year}-%",))
            valid_days = cursor.fetchone()["cnt"]
            
            if valid_days == 0:
                logger.warning(f"{year}年无日报数据，跳过年报生成")
                return
            
            # 计算年报数据
            yearly_data = calc_yearly(year, total_sold, total_revenue, valid_days)
            
            # 插入或更新年报
            cursor.execute("""
                INSERT OR REPLACE INTO yearly_data
                (data_year, valid_days, sold_rooms, occupancy_rate, revpar, total_revenue, adr)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                year,
                yearly_data["valid_days"],
                yearly_data["sold_rooms"],
                yearly_data["occupancy_rate"],
                yearly_data["revpar"],
                yearly_data["total_revenue"],
                yearly_data["adr"]
            ))
            
            logger.info(f"年报生成成功：{year}年")
    
    except Exception as e:
        logger.error(f"年报生成失败：{str(e)}", exc_info=True)


def auto_backup() -> None:
    """自动备份任务"""
    backup_database()


def log_cleanup() -> None:
    """日志清理任务"""
    logger.info("开始清理临时文件和旧日志")
    # 清理导入临时文件
    import os
    import glob
    from app.constants import IMPORT_DIR, LOG_DIR
    
    # 清理7天前的导入文件
    import_files = glob.glob(os.path.join(IMPORT_DIR, "*"))
    cutoff = now_local().timestamp() - 7 * 86400
    for f in import_files:
        if os.path.isfile(f) and os.path.getmtime(f) < cutoff:
            os.remove(f)
    
    logger.info("临时文件清理完成")


def auto_collect_hourly() -> None:
    """每小时自动从去呼呼采集数据
    00:01 → 采集昨天 → hour=24（昨日结算）
    01:01-23:01 → 采集今天 → hour=当前小时
    采集完成后检查上一小时是否缺失，补漏写入相同数据
    """
    from app.core.collector import auto_collect
    try:
        now = now_local()
        if now.hour == 0:
            target_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")
            data_hour = 24
        else:
            target_date = now.strftime("%Y-%m-%d")
            data_hour = now.hour
        
        logger.info(f"⏰ 定时采集: {target_date} hour={data_hour}")
        result = auto_collect(target_date, data_hour)
        if result["success"]:
            logger.info(f"✅ 定时采集完成: 房间{result['total_sold']}, 房费¥{result['total_revenue']}")
            
            # 兜底补漏：检查上一小时是否有数据，缺失则用当前数据补上
            if data_hour > 1:
                prev_hour = data_hour - 1
                sold = result.get('total_sold', 0)
                rev = result.get('total_revenue', 0)
                if sold > 0 or rev > 0:
                    with db_transaction() as conn:
                        c = conn.cursor()
                        c.execute("SELECT id FROM hourly_data WHERE data_date=? AND data_hour=?",
                                  (target_date, prev_hour))
                        if not c.fetchone():
                            from app.core.calculator import calc_hourly
                            hd = calc_hourly(sold, rev)
                            c.execute("""INSERT OR IGNORE INTO hourly_data
                                (data_date, data_hour, sold_rooms, available_rooms, occupancy_rate,
                                 min_price, revpar, total_revenue, adr, data_source)
                                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                                (target_date, prev_hour, hd['sold_rooms'], hd['available_rooms'],
                                 hd['occupancy_rate'], 0, hd['revpar'], hd['total_revenue'],
                                 hd['adr'], DataSource.AUTO_IMPORT))
                            logger.warning(f"🔧 补漏: {target_date} h{prev_hour} (调度器上次未触发)")
        else:
            logger.warning(f"⚠️ 定时采集失败: {result.get('errors', [])}")
    except Exception as e:
        logger.error(f"定时采集异常: {e}", exc_info=True)


def init_scheduler() -> None:
    """初始化所有定时任务"""
    # ★ 每小时自动采集（整点+偏移分钟）
    offset = get_config_int("collect_offset_minute", 2)
    scheduler.add_job(
        auto_collect_hourly,
        trigger=CronTrigger(minute=offset),
        id="auto_collect_hourly",
        replace_existing=True
    )
    logger.info(f"每小时自动采集已启用（每小时的{offset:02d}分执行）")

    # 日报聚合：每天00:01
    scheduler.add_job(
        daily_aggregate,
        trigger=CronTrigger(hour=0, minute=1),
        id="daily_aggregate",
        replace_existing=True
    )
    
    # 月报聚合：每月1日00:01
    scheduler.add_job(
        monthly_aggregate,
        trigger=CronTrigger(day=1, hour=0, minute=1),
        id="monthly_aggregate",
        replace_existing=True
    )
    
    # 季报聚合：1/4/7/10月1日00:02
    scheduler.add_job(
        quarterly_aggregate,
        trigger=CronTrigger(month="1,4,7,10", day=1, hour=0, minute=2),
        id="quarterly_aggregate",
        replace_existing=True
    )
    
    # 年报聚合：每年1月1日00:03
    scheduler.add_job(
        yearly_aggregate,
        trigger=CronTrigger(month=1, day=1, hour=0, minute=3),
        id="yearly_aggregate",
        replace_existing=True
    )
    
    # 自动备份：每6小时一次（02,08,14,20点）
    scheduler.add_job(
        auto_backup,
        trigger=CronTrigger(hour="2,8,14,20", minute=0),
        id="auto_backup",
        replace_existing=True
    )
    
    # 日志清理：每天04:00
    scheduler.add_job(
        log_cleanup,
        trigger=CronTrigger(hour=4, minute=0),
        id="log_cleanup",
        replace_existing=True
    )
    
    # 启动调度器
    if not scheduler.running:
        scheduler.start()
        logger.info("定时任务调度器启动成功")


def check_missing_aggregates() -> None:
    """启动时检测缺失的日报/月报并补算"""
    try:
        yesterday = (now_local() - timedelta(days=1)).strftime("%Y-%m-%d")
        with db_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM daily_data WHERE data_date = ?", (yesterday,))
            if not cursor.fetchone():
                logger.info(f"昨日日报缺失，补算：{yesterday}")
                daily_aggregate()

        last_month = now_local().replace(day=1) - timedelta(days=1)
        with db_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM monthly_data WHERE data_year = ? AND data_month = ?",
                (last_month.year, last_month.month)
            )
            if not cursor.fetchone():
                logger.info(f"上月月报缺失，补算")
                monthly_aggregate_for_month(last_month.year, last_month.month)
    except Exception as e:
        logger.error(f"补算检查失败：{e}", exc_info=True)

"""
核心计算引擎
所有业务计算公式统一在此实现，禁止在其他地方重复实现
所有计算结果统一保留DECIMAL_PLACES位小数
"""
import calendar
from typing import Dict, Any
from datetime import date

from app.constants import TOTAL_ROOMS, DECIMAL_PLACES


def round2(value: float) -> float:
    """统一保留2位小数"""
    return round(float(value), DECIMAL_PLACES)


def calc_hourly(sold_rooms: int, total_revenue: float, min_price: float = 0.0) -> Dict[str, Any]:
    """
    计算小时级指标
    :param sold_rooms: 已售房间数
    :param total_revenue: 累计房费
    :param min_price: 起售价格
    :return: 计算后的全量字段
    """
    if sold_rooms < 0 or sold_rooms > TOTAL_ROOMS:
        raise ValueError(f"已售房间数必须在0-{TOTAL_ROOMS}之间")
    if total_revenue < 0:
        raise ValueError("累计房费不能为负数")
    if min_price < 0:
        raise ValueError("起售价格不能为负数")
    
    available_rooms = TOTAL_ROOMS - sold_rooms
    occupancy_rate = round2(sold_rooms / TOTAL_ROOMS * 100)
    revpar = round2(total_revenue / TOTAL_ROOMS)
    adr = round2(total_revenue / sold_rooms) if sold_rooms > 0 else 0.0
    
    return {
        "sold_rooms": sold_rooms,
        "available_rooms": available_rooms,
        "occupancy_rate": occupancy_rate,
        "min_price": round2(min_price),
        "revpar": revpar,
        "total_revenue": round2(total_revenue),
        "adr": adr
    }


def calc_daily(sold_rooms: int, total_revenue: float, min_price: float = 0.0) -> Dict[str, Any]:
    """
    计算日级指标
    :param sold_rooms: 售出房间数
    :param total_revenue: 当日累计房费
    :param min_price: 当日起售价格
    :return: 计算后的全量字段
    """
    if sold_rooms < 0 or sold_rooms > TOTAL_ROOMS:
        raise ValueError(f"售出房间数必须在0-{TOTAL_ROOMS}之间")
    if total_revenue < 0:
        raise ValueError("累计房费不能为负数")
    if min_price < 0:
        raise ValueError("起售价格不能为负数")
    
    remain_rooms = TOTAL_ROOMS - sold_rooms
    occupancy_rate = round2(sold_rooms / TOTAL_ROOMS * 100)
    revpar = round2(total_revenue / TOTAL_ROOMS)
    adr = round2(total_revenue / sold_rooms) if sold_rooms > 0 else 0.0
    
    return {
        "sold_rooms": sold_rooms,
        "remain_rooms": remain_rooms,
        "occupancy_rate": occupancy_rate,
        "min_price": round2(min_price),
        "revpar": revpar,
        "total_revenue": round2(total_revenue),
        "adr": adr
    }


def calc_monthly(year: int, month: int, total_sold: int, total_revenue: float, valid_days: int = None) -> Dict[str, Any]:
    """
    计算月级指标
    :param year: 年份
    :param month: 月份
    :param total_sold: 当月累计售出房间数
    :param total_revenue: 当月累计房费
    :param valid_days: 当月有日报数据的天数，默认取日历天数
    :return: 计算后的全量字段
    """
    if month < 1 or month > 12:
        raise ValueError("月份必须在1-12之间")
    if total_sold < 0:
        raise ValueError("售出房间数不能为负数")
    if total_revenue < 0:
        raise ValueError("累计房费不能为负数")
    
    if valid_days is None or valid_days <= 0:
        valid_days = calendar.monthrange(year, month)[1]
    occupancy_rate = round2(total_sold / (TOTAL_ROOMS * valid_days) * 100)
    revpar = round2(total_revenue / (TOTAL_ROOMS * valid_days))
    adr = round2(total_revenue / total_sold) if total_sold > 0 else 0.0
    
    return {
        "days": valid_days,
        "sold_rooms": total_sold,
        "occupancy_rate": occupancy_rate,
        "revpar": revpar,
        "total_revenue": round2(total_revenue),
        "adr": adr
    }


def calc_quarterly(year: int, quarter: int, total_sold: int, total_revenue: float, valid_days: int = None) -> Dict[str, Any]:
    """
    计算季度指标
    :param year: 年份
    :param quarter: 季度1-4
    :param total_sold: 当季累计售出房间数
    :param total_revenue: 当季累计房费
    :param valid_days: 当季有数据的实际天数，默认取日历天数
    :return: 计算后的全量字段
    """
    if quarter < 1 or quarter > 4:
        raise ValueError("季度必须在1-4之间")
    if total_sold < 0:
        raise ValueError("售出房间数不能为负数")
    if total_revenue < 0:
        raise ValueError("累计房费不能为负数")
    
    if valid_days is None or valid_days <= 0:
        months = [(quarter - 1) * 3 + 1, (quarter - 1) * 3 + 2, (quarter - 1) * 3 + 3]
        valid_days = sum(calendar.monthrange(year, m)[1] for m in months)
    occupancy_rate = round2(total_sold / (TOTAL_ROOMS * valid_days) * 100)
    revpar = round2(total_revenue / (TOTAL_ROOMS * valid_days))
    adr = round2(total_revenue / total_sold) if total_sold > 0 else 0.0
    
    return {
        "days": valid_days,
        "sold_rooms": total_sold,
        "occupancy_rate": occupancy_rate,
        "revpar": revpar,
        "total_revenue": round2(total_revenue),
        "adr": adr
    }


def calc_yearly(year: int, total_sold: int, total_revenue: float, valid_days: int) -> Dict[str, Any]:
    """
    计算年度指标
    :param year: 年份
    :param total_sold: 当年累计售出房间数
    :param total_revenue: 当年累计房费
    :param valid_days: 当年有数据的天数
    :return: 计算后的全量字段
    """
    if valid_days <= 0:
        raise ValueError("有效天数必须大于0")
    if total_sold < 0:
        raise ValueError("售出房间数不能为负数")
    if total_revenue < 0:
        raise ValueError("累计房费不能为负数")
    
    occupancy_rate = round2(total_sold / (TOTAL_ROOMS * valid_days) * 100)
    revpar = round2(total_revenue / (TOTAL_ROOMS * valid_days))
    adr = round2(total_revenue / total_sold) if total_sold > 0 else 0.0
    
    return {
        "valid_days": valid_days,
        "sold_rooms": total_sold,
        "occupancy_rate": occupancy_rate,
        "revpar": revpar,
        "total_revenue": round2(total_revenue),
        "adr": adr
    }

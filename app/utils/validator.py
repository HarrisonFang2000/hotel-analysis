"""
数据校验工具
统一校验业务数据合法性
"""
import re
from typing import Tuple, Any
from datetime import datetime

from app.constants import TOTAL_ROOMS, MIN_HOUR, MAX_HOUR, MIN_MONTH, MAX_MONTH, MIN_QUARTER, MAX_QUARTER


def validate_date(date_str: str) -> bool:
    """校验日期格式YYYY-MM-DD"""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def validate_hour(hour: int) -> bool:
    """校验小时1-24"""
    return isinstance(hour, int) and MIN_HOUR <= hour <= MAX_HOUR


def validate_rooms(rooms: int) -> bool:
    """校验房间数0-113"""
    return isinstance(rooms, int) and 0 <= rooms <= TOTAL_ROOMS


def validate_money(money: float) -> bool:
    """校验金额非负"""
    return isinstance(money, (int, float)) and money >= 0


def validate_percent(percent: float) -> bool:
    """校验百分比0-100"""
    return isinstance(percent, (int, float)) and 0 <= percent <= 100


def validate_month(month: int) -> bool:
    """校验月份1-12"""
    return isinstance(month, int) and MIN_MONTH <= month <= MAX_MONTH


def validate_quarter(quarter: int) -> bool:
    """校验季度1-4"""
    return isinstance(quarter, int) and MIN_QUARTER <= quarter <= MAX_QUARTER


def validate_username(username: str) -> bool:
    """校验账号非空"""
    return isinstance(username, str) and len(username.strip()) > 0


def validate_url(url: str) -> bool:
    """校验URL格式"""
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return bool(url_pattern.match(url))


def validate_hourly_data(data: dict) -> Tuple[bool, str]:
    """校验小时数据合法性"""
    if "sold_rooms" in data and not validate_rooms(data["sold_rooms"]):
        return False, "已售房间数必须在0-113之间"
    if "total_revenue" in data and not validate_money(data["total_revenue"]):
        return False, "累计房费不能为负数"
    if "min_price" in data and not validate_money(data["min_price"]):
        return False, "起售价格不能为负数"
    return True, ""


def validate_daily_data(data: dict) -> Tuple[bool, str]:
    """校验日报数据合法性"""
    if "sold_rooms" in data and not validate_rooms(data["sold_rooms"]):
        return False, "售出房间数必须在0-113之间"
    if "total_revenue" in data and not validate_money(data["total_revenue"]):
        return False, "累计房费不能为负数"
    if "min_price" in data and not validate_money(data["min_price"]):
        return False, "起售价格不能为负数"
    return True, ""

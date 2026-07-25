# -*- coding: utf-8 -*-
"""
全局常量定义
所有硬编码配置、枚举值统一在此定义
"""
import os
import sys
from enum import IntEnum

# ------------------------------ 路径解析 ------------------------------
# PyInstaller打包后：sys._MEIPASS是临时解压目录，sys.executable是EXE位置
# 开发模式：__file__是源码路径
# 数据目录统一放在项目根目录的 data/ 下，dev和EXE共用，PyInstaller构建永不动它
def _get_base_dir() -> str:
    """获取程序根目录（项目根目录，data/ 的父目录）"""
    if getattr(sys, 'frozen', False):
        # EXE位置: dist/酒店数据分析系统/酒店数据分析系统.exe
        # 往上3级回到项目根目录
        return os.path.dirname(os.path.dirname(os.path.dirname(sys.executable)))
    else:
        # app/constants.py → 往上2级回到项目根目录
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = _get_base_dir()

# ------------------------------ 基础业务常量 ------------------------------
TOTAL_ROOMS = 113          # 总房间数，固定值
DECIMAL_PLACES = 2         # 金额、比率统一保留2位小数
DEFAULT_PORT = 8080
DEFAULT_TIMEZONE = "Asia/Shanghai"

# 路径常量（绝对路径，不受CWD影响）
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_FILE = os.path.join(DATA_DIR, "hotel_data.db")
IMPORT_DIR = os.path.join(DATA_DIR, "import")
EXPORT_DIR = os.path.join(DATA_DIR, "export")
BACKUP_DIR = os.path.join(DATA_DIR, "backup")
LOG_DIR = os.path.join(DATA_DIR, "logs")
CONFIG_FILE = os.path.join(DATA_DIR, "config.ini")
LOCK_FILE = os.path.join(DATA_DIR, ".lock")

# ------------------------------ 枚举定义 ------------------------------
class DataSource(IntEnum):
    """数据来源枚举"""
    AUTO_IMPORT = 1    # 自动导入
    MANUAL_INPUT = 2   # 手动录入
    MANUAL_EDIT = 3    # 手动修改

class ReportType:
    """报表类型常量"""
    DAILY_ROOM = "daily_room"       # 日租房
    HOURLY_ROOM = "hourly_room"     # 钟点房
    OTHER_CONSUME = "other_consume" # 其他消费
    INCOME_CHECK = "income_check"   # 应收收入（开发模式用）

# ------------------------------ 时间常量 ------------------------------
MIN_HOUR = 1
MAX_HOUR = 24
MIN_MONTH = 1
MAX_MONTH = 12
MIN_QUARTER = 1
MAX_QUARTER = 4

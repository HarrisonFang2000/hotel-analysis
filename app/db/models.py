# -*- coding: utf-8 -*-
"""
数据库表结构定义
所有建表SQL和初始数据统一在此维护
"""
from typing import List

CREATE_TABLE_SQL: List[str] = [
    # 1. 系统配置表
    """
    CREATE TABLE IF NOT EXISTS sys_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        config_key TEXT NOT NULL UNIQUE,
        config_value TEXT NOT NULL DEFAULT '',
        config_desc TEXT NOT NULL DEFAULT '',
        update_time TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    )
    """,
    # 2. 小时数据表
    """
    CREATE TABLE IF NOT EXISTS hourly_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data_date TEXT NOT NULL,
        data_hour INTEGER NOT NULL CHECK (data_hour >= 1 AND data_hour <= 24),
        sold_rooms INTEGER NOT NULL DEFAULT 0 CHECK (sold_rooms >= 0 AND sold_rooms <= 113),
        available_rooms INTEGER NOT NULL DEFAULT 113 CHECK (available_rooms >= 0 AND available_rooms <= 113),
        occupancy_rate REAL NOT NULL DEFAULT 0 CHECK (occupancy_rate >= 0 AND occupancy_rate <= 100),
        min_price REAL DEFAULT 0 CHECK (min_price >= 0),
        revpar REAL NOT NULL DEFAULT 0 CHECK (revpar >= 0),
        total_revenue REAL NOT NULL DEFAULT 0 CHECK (total_revenue >= 0),
        adr REAL NOT NULL DEFAULT 0 CHECK (adr >= 0),
        data_source INTEGER NOT NULL DEFAULT 1,
        create_time TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        update_time TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        UNIQUE (data_date, data_hour)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_hourly_date ON hourly_data(data_date)",
    # 3. 日报数据表
    """
    CREATE TABLE IF NOT EXISTS daily_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data_date TEXT NOT NULL UNIQUE,
        min_price REAL DEFAULT 0 CHECK (min_price >= 0),
        sold_rooms INTEGER NOT NULL DEFAULT 0 CHECK (sold_rooms >= 0 AND sold_rooms <= 113),
        remain_rooms INTEGER NOT NULL DEFAULT 113 CHECK (remain_rooms >= 0 AND remain_rooms <= 113),
        occupancy_rate REAL NOT NULL DEFAULT 0 CHECK (occupancy_rate >= 0 AND occupancy_rate <= 100),
        revpar REAL NOT NULL DEFAULT 0 CHECK (revpar >= 0),
        total_revenue REAL NOT NULL DEFAULT 0 CHECK (total_revenue >= 0),
        adr REAL NOT NULL DEFAULT 0 CHECK (adr >= 0),
        data_source INTEGER NOT NULL DEFAULT 1,
        create_time TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        update_time TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_daily_date ON daily_data(data_date DESC)",
    # 4. 月报数据表
    """
    CREATE TABLE IF NOT EXISTS monthly_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data_year INTEGER NOT NULL,
        data_month INTEGER NOT NULL CHECK (data_month >= 1 AND data_month <= 12),
        days INTEGER NOT NULL CHECK (days >= 0 AND days <= 31),
        sold_rooms INTEGER NOT NULL DEFAULT 0 CHECK (sold_rooms >= 0),
        occupancy_rate REAL NOT NULL DEFAULT 0 CHECK (occupancy_rate >= 0 AND occupancy_rate <= 100),
        revpar REAL NOT NULL DEFAULT 0 CHECK (revpar >= 0),
        total_revenue REAL NOT NULL DEFAULT 0 CHECK (total_revenue >= 0),
        adr REAL NOT NULL DEFAULT 0 CHECK (adr >= 0),
        create_time TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        update_time TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        UNIQUE (data_year, data_month)
    )
    """,
    # 5. 季报数据表
    """
    CREATE TABLE IF NOT EXISTS quarterly_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data_year INTEGER NOT NULL,
        data_quarter INTEGER NOT NULL CHECK (data_quarter >= 1 AND data_quarter <= 4),
        days INTEGER NOT NULL CHECK (days >= 0 AND days <= 92),
        sold_rooms INTEGER NOT NULL DEFAULT 0 CHECK (sold_rooms >= 0),
        occupancy_rate REAL NOT NULL DEFAULT 0 CHECK (occupancy_rate >= 0 AND occupancy_rate <= 100),
        revpar REAL NOT NULL DEFAULT 0 CHECK (revpar >= 0),
        total_revenue REAL NOT NULL DEFAULT 0 CHECK (total_revenue >= 0),
        adr REAL NOT NULL DEFAULT 0 CHECK (adr >= 0),
        create_time TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        UNIQUE (data_year, data_quarter)
    )
    """,
    # 6. 年报数据表
    """
    CREATE TABLE IF NOT EXISTS yearly_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data_year INTEGER NOT NULL UNIQUE,
        valid_days INTEGER NOT NULL DEFAULT 0 CHECK (valid_days >= 0),
        sold_rooms INTEGER NOT NULL DEFAULT 0 CHECK (sold_rooms >= 0),
        occupancy_rate REAL NOT NULL DEFAULT 0 CHECK (occupancy_rate >= 0 AND occupancy_rate <= 100),
        revpar REAL NOT NULL DEFAULT 0 CHECK (revpar >= 0),
        total_revenue REAL NOT NULL DEFAULT 0 CHECK (total_revenue >= 0),
        adr REAL NOT NULL DEFAULT 0 CHECK (adr >= 0),
        create_time TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    )
    """,
    # 7. 导入记录表
    """
    CREATE TABLE IF NOT EXISTS import_record (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_name TEXT NOT NULL,
        report_type TEXT NOT NULL,
        data_date TEXT,
        import_status INTEGER NOT NULL DEFAULT 1,
        error_msg TEXT DEFAULT '',
        create_time TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    )
    """,
    # 8. 操作日志表
    """
    CREATE TABLE IF NOT EXISTS operation_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_name TEXT NOT NULL,
        record_id INTEGER NOT NULL,
        before_value TEXT NOT NULL DEFAULT '{}',
        after_value TEXT NOT NULL DEFAULT '{}',
        operator TEXT NOT NULL DEFAULT 'local',
        create_time TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    )
    """,
    # 9. 用户表
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        pin TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'operator' CHECK (role IN ('super_admin','admin','operator')),
        active INTEGER NOT NULL DEFAULT 1,
        create_time TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    )
    """,
    # 10. 审计日志表（简化版操作日志）
    """
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_name TEXT NOT NULL DEFAULT '',
        user_role TEXT NOT NULL DEFAULT '',
        action TEXT NOT NULL,
        detail TEXT NOT NULL DEFAULT '',
        create_time TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_log(create_time DESC)",
    "CREATE INDEX IF NOT EXISTS idx_log_table ON operation_log(table_name, record_id)"
]

# 版本化数据库迁移（按版本号顺序执行）
# 格式: (version, description, SQL)
MIGRATION_SQL = [
    (1, "添加adr列到全部5张数据表", "ALTER TABLE hourly_data ADD COLUMN adr REAL NOT NULL DEFAULT 0 CHECK (adr >= 0)"),
    (1, "添加adr列到全部5张数据表", "ALTER TABLE daily_data ADD COLUMN adr REAL NOT NULL DEFAULT 0 CHECK (adr >= 0)"),
    (1, "添加adr列到全部5张数据表", "ALTER TABLE monthly_data ADD COLUMN adr REAL NOT NULL DEFAULT 0 CHECK (adr >= 0)"),
    (1, "添加adr列到全部5张数据表", "ALTER TABLE quarterly_data ADD COLUMN adr REAL NOT NULL DEFAULT 0 CHECK (adr >= 0)"),
    (1, "添加adr列到全部5张数据表", "ALTER TABLE yearly_data ADD COLUMN adr REAL NOT NULL DEFAULT 0 CHECK (adr >= 0)"),
]

INIT_DATA_SQL: List[str] = [
    "INSERT OR IGNORE INTO sys_config (config_key, config_value, config_desc) VALUES ('collection_interval', '60', '数据采集间隔，单位分钟，取值范围10-1440')",
    "INSERT OR IGNORE INTO sys_config (config_key, config_value, config_desc) VALUES ('dev_mode', '0', '开发模式开关，0关闭1开启，开启后显示对账校验')",
    "INSERT OR IGNORE INTO sys_config (config_key, config_value, config_desc) VALUES ('port', '8080', '本地服务端口')",
    "INSERT OR IGNORE INTO sys_config (config_key, config_value, config_desc) VALUES ('auto_backup_hours', '6', '自动备份间隔，单位小时')",
    "INSERT OR IGNORE INTO sys_config (config_key, config_value, config_desc) VALUES ('meituan_enabled', '0', '美团房价采集开关，1开启0关闭')",
    "INSERT OR IGNORE INTO sys_config (config_key, config_value, config_desc) VALUES ('meituan_username', '', '美团商家登录手机号')",
    "INSERT OR IGNORE INTO sys_config (config_key, config_value, config_desc) VALUES ('meituan_password', '', '美团商家登录密码')",
    "INSERT OR IGNORE INTO sys_config (config_key, config_value, config_desc) VALUES ('meituan_calendar_url', '', '美团房价日历页面URL')",
    # 默认超管: 超管 / 123456 (SHA256哈希)
    "INSERT OR IGNORE INTO users (name, pin, role) VALUES ('超管', '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92', 'super_admin')",
    # 默认管理员: 管理员 / 123456
    "INSERT OR IGNORE INTO users (name, pin, role) VALUES ('管理员', '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92', 'admin')",
]

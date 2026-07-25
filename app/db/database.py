"""
SQLite数据库连接管理
提供上下文管理器，自动处理连接、提交、回滚、关闭
"""
import sqlite3
import os
from typing import Optional, Generator
from contextlib import contextmanager

from app.constants import DB_FILE, DATA_DIR


def init_db_dir() -> None:
    """初始化数据库目录，不存在则创建"""
    os.makedirs(DATA_DIR, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    """获取数据库连接，开启WAL模式和外键约束"""
    conn = sqlite3.connect(DB_FILE, timeout=30,
                           detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=5000;")  # 5秒等锁
    return conn


@contextmanager
def db_transaction() -> Generator[sqlite3.Connection, None, None]:
    """
    数据库事务上下文管理器
    自动提交，异常自动回滚
    使用示例:
        with db_transaction() as conn:
            conn.execute("INSERT INTO ...")
    """
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = get_connection()
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()


def init_database() -> None:
    """初始化数据库，执行建表语句、版本迁移和初始数据"""
    init_db_dir()
    from app.db.models import CREATE_TABLE_SQL, MIGRATION_SQL, INIT_DATA_SQL
    
    with db_transaction() as conn:
        cursor = conn.cursor()
        
        # 1. 建表
        for sql in CREATE_TABLE_SQL:
            cursor.execute(sql)
        
        # 2. 创建迁移版本表（如果不存在）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                description TEXT NOT NULL DEFAULT '',
                applied_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
        """)
        
        # 3. 自动检测已有列的旧数据库——检查全部5张表是否有adr列
        cursor.execute("SELECT MAX(version) FROM schema_version")
        row = cursor.fetchone()
        applied = row[0] or 0
        
        if applied == 0:
            # 检查全部5张数据表是否已有adr列（防止部分迁移）
            all_have_adr = True
            for tbl in ['hourly_data', 'daily_data', 'monthly_data', 'quarterly_data', 'yearly_data']:
                cursor.execute(f"PRAGMA table_info({tbl})")
                cols = [c[1] for c in cursor.fetchall()]
                if 'adr' not in cols:
                    all_have_adr = False
                    break
            if all_have_adr:
                # 全部表已有adr列，补录v1迁移记录，跳过重复执行
                cursor.execute("INSERT OR IGNORE INTO schema_version(version, description) VALUES(1, '添加adr列(已存在-自动跳过)')")
                applied = 1
        
        # 4. 按版本号顺序执行未应用的迁移（每执行一条重新读取version以防重复）
        for ver, desc, sql in MIGRATION_SQL:
            if ver > applied:
                try:
                    cursor.execute(sql)
                    cursor.execute("INSERT OR IGNORE INTO schema_version(version, description) VALUES(?,?)", (ver, desc))
                    print(f"[DB] 迁移 v{ver}: {desc} ✓")
                except Exception as e:
                    if 'duplicate column' in str(e).lower():
                        cursor.execute("INSERT OR IGNORE INTO schema_version(version, description) VALUES(?,?)", (ver, desc + '(已存在)'))
                        print(f"[DB] 迁移 v{ver}: {desc} (已存在，跳过)")
                    else:
                        print(f"[DB] 迁移 v{ver}: {desc} ✗ ({e})")
                # 重新读取applied，防止同版本内重复执行已成功的迁移
                cursor.execute("SELECT MAX(version) FROM schema_version")
                row = cursor.fetchone()
                applied = row[0] or 0
        
        # 5. 初始数据
        for sql in INIT_DATA_SQL:
            cursor.execute(sql)

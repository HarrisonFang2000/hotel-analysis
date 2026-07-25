"""
数据库备份工具
自动备份数据库，保留最近30天备份，含完整性校验
"""
import os
import shutil
import glob
import sqlite3
from datetime import datetime

from app.constants import BACKUP_DIR, DB_FILE
from app.utils.logger import get_logger

logger = get_logger(__name__)

MAX_BACKUPS = 50  # 最多保留备份数


def backup_database() -> bool:
    """
    备份数据库（含完整性校验）
    :return: 备份成功返回True
    """
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        if not os.path.exists(DB_FILE):
            logger.warning("数据库文件不存在，跳过备份")
            return False
        
        # 先校验源库完整性
        try:
            check_conn = sqlite3.connect(DB_FILE)
            check_conn.execute("PRAGMA integrity_check")
            check_conn.close()
        except Exception as e:
            logger.error(f"源数据库完整性检查失败，跳过备份: {e}")
            return False
        
        # 备份文件名：hotel_data_YYYYMMDD_HHMMSS.db
        backup_name = f"hotel_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        backup_path = os.path.join(BACKUP_DIR, backup_name)
        
        shutil.copy2(DB_FILE, backup_path)
        
        # 校验备份文件
        try:
            check_conn = sqlite3.connect(backup_path)
            check_conn.execute("PRAGMA integrity_check")
            check_conn.close()
        except Exception:
            os.remove(backup_path)
            logger.error("备份文件校验失败，已删除损坏备份")
            return False
        
        logger.info(f"数据库备份成功: {backup_name}")
        
        # 清理旧备份
        cleanup_old_backups()
        return True
    except Exception as e:
        logger.error(f"数据库备份失败: {str(e)}", exc_info=True)
        return False


def cleanup_old_backups() -> None:
    """清理旧备份：超过30天或超过50个"""
    try:
        backup_files = sorted(
            glob.glob(os.path.join(BACKUP_DIR, "hotel_data_*.db")),
            key=os.path.getmtime
        )
        
        # 按时间清理30天前的
        cutoff = datetime.now().timestamp() - 30 * 86400
        for f in backup_files:
            if os.path.getmtime(f) < cutoff:
                os.remove(f)
                logger.info(f"清理过期备份: {os.path.basename(f)}")
        
        # 按数量清理超出上限的
        remaining = sorted(
            glob.glob(os.path.join(BACKUP_DIR, "hotel_data_*.db")),
            key=os.path.getmtime
        )
        while len(remaining) > MAX_BACKUPS:
            os.remove(remaining[0])
            logger.info(f"清理超额备份: {os.path.basename(remaining[0])}")
            remaining.pop(0)
            
    except Exception as e:
        logger.error(f"清理旧备份失败: {str(e)}", exc_info=True)

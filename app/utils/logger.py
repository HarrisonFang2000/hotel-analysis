"""
日志工具
统一日志格式，按天切割，存在data/logs目录
"""
import os
import logging
from logging.handlers import TimedRotatingFileHandler
from typing import Optional

from app.constants import LOG_DIR


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    获取logger实例
    :param name: logger名称，一般用__name__
    :param level: 日志级别
    :return: logger实例
    """
    os.makedirs(LOG_DIR, exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 避免重复添加handler
    if logger.handlers:
        return logger
    
    # 日志格式
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # 文件handler，按天切割，保留30天
    file_handler = TimedRotatingFileHandler(
        filename=os.path.join(LOG_DIR, "app.log"),
        when="D",
        interval=1,
        backupCount=30,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    
    # 控制台handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.WARNING)  # 控制台只输出警告及以上
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

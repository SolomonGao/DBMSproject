# logger.py - 日志模块
"""
统一的日志管理模块
支持控制台输出（带颜色）和文件日志
"""

import sys
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime


class ColoredFormatter(logging.Formatter):
    """带颜色的日志格式化器"""
    
    # ANSI 颜色码
    COLORS = {
        'DEBUG': '\033[36m',      # 青色
        'INFO': '\033[32m',       # 绿色
        'WARNING': '\033[33m',    # 黄色
        'ERROR': '\033[31m',      # 红色
        'CRITICAL': '\033[35m',   # 紫色
        'RESET': '\033[0m',       # 重置
    }
    
    def __init__(self, fmt: str, use_colors: bool = True):
        super().__init__(fmt)
        self.use_colors = use_colors
    
    def format(self, record: logging.LogRecord) -> str:
        if self.use_colors and sys.platform != 'win32':
            # Windows 需要启用 ANSI 支持，简化处理
            levelname = record.levelname
            if levelname in self.COLORS:
                record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
        
        return super().format(record)


class LoggerManager:
    """日志管理器 - 单例模式"""
    
    _instance: Optional['LoggerManager'] = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if LoggerManager._initialized:
            return
        
        self.logger = logging.getLogger("mcp_app")
        self.logger.setLevel(logging.DEBUG)
        self.handlers: list[logging.Handler] = []
        LoggerManager._initialized = True
    
    def setup(
        self,
        level: str = "INFO",
        log_file: Optional[Path] = None,
        console: bool = True,
        file_level: str = "DEBUG",
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5
    ) -> logging.Logger:
        """
        配置日志
        
        Args:
            level: 控制台日志级别
            log_file: 日志文件路径
            console: 是否输出到控制台
            file_level: 文件日志级别
            max_bytes: 单个日志文件最大大小
            backup_count: 保留的备份文件数
        """
        # 清除现有处理器
        self.clear_handlers()
        self.logger.setLevel(getattr(logging, level.upper()))
        
        # 创建格式器
        console_fmt = ColoredFormatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            use_colors=True
        )
        file_fmt = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s'
        )
        
        # 控制台处理器
        if console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(getattr(logging, level.upper()))
            console_handler.setFormatter(console_fmt)
            self.logger.addHandler(console_handler)
            self.handlers.append(console_handler)
        
        # 文件处理器
        if log_file:
            log_file = Path(log_file)
            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                from logging.handlers import RotatingFileHandler
                file_handler = RotatingFileHandler(
                    log_file,
                    maxBytes=max_bytes,
                    backupCount=backup_count,
                    encoding='utf-8'
                )
                file_handler.setLevel(getattr(logging, file_level.upper()))
                file_handler.setFormatter(file_fmt)
                self.logger.addHandler(file_handler)
                self.handlers.append(file_handler)
            except Exception as e:
                self.logger.warning(f"无法创建文件日志处理器: {e}")
        
        return self.logger
    
    def clear_handlers(self):
        """清除所有处理器"""
        for handler in self.handlers:
            self.logger.removeHandler(handler)
            handler.close()
        self.handlers.clear()
    
    def get_logger(self, name: Optional[str] = None) -> logging.Logger:
        """获取命名日志器"""
        if name:
            return self.logger.getChild(name)
        return self.logger


# 全局日志管理器实例
logger_manager = LoggerManager()


def setup_logging(
    level: str = "INFO",
    log_dir: Optional[Path] = None,
    console: bool = True
) -> logging.Logger:
    """
    快速配置日志
    
    Args:
        level: 日志级别
        log_dir: 日志目录（None 则不写入文件）
        console: 是否输出到控制台
    
    Returns:
        配置好的日志器
    """
    log_file = None
    if log_dir:
        log_dir = Path(log_dir)
        timestamp = datetime.now().strftime("%Y%m%d")
        log_file = log_dir / f"mcp_app_{timestamp}.log"
    
    return logger_manager.setup(
        level=level,
        log_file=log_file,
        console=console
    )


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """获取日志器"""
    return logger_manager.get_logger(name)


# 便捷的日志函数（用于快速调试）
def debug(msg: str, *args, **kwargs):
    """调试日志"""
    logger_manager.get_logger().debug(msg, *args, **kwargs)


def info(msg: str, *args, **kwargs):
    """信息日志"""
    logger_manager.get_logger().info(msg, *args, **kwargs)


def warning(msg: str, *args, **kwargs):
    """警告日志"""
    logger_manager.get_logger().warning(msg, *args, **kwargs)


def error(msg: str, *args, **kwargs):
    """错误日志"""
    logger_manager.get_logger().error(msg, *args, **kwargs)


def critical(msg: str, *args, **kwargs):
    """严重错误日志"""
    logger_manager.get_logger().critical(msg, *args, **kwargs)


def exception(msg: str, *args, **kwargs):
    """异常日志（自动记录堆栈）"""
    logger_manager.get_logger().exception(msg, *args, **kwargs)

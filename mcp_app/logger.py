# logger.py - Logging Module
"""
Unified logging management module
Supports console output (with colors) and file logging
"""

import sys
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime


def sanitize_for_log(text: str) -> str:
    """Clean illegal UTF-8 characters from log text"""
    if not isinstance(text, str):
        text = str(text)
    # Remove surrogate pairs
    text = text.encode('utf-8', 'ignore').decode('utf-8')
    # Replace control characters (keep newlines and tabs)
    import unicodedata
    text = ''.join(
        char for char in text 
        if unicodedata.category(char)[0] != 'C' or char in '\n\t\r'
    )
    return text.replace('\x00', '')


class SafeStreamHandler(logging.StreamHandler):
    """Safe stream handler - handles encoding errors"""
    
    def emit(self, record: logging.LogRecord):
        try:
            # Clean message content
            if isinstance(record.msg, str):
                record.msg = sanitize_for_log(record.msg)
            if record.args:
                # Clean formatting arguments
                safe_args = tuple(
                    sanitize_for_log(arg) if isinstance(arg, str) else arg
                    for arg in record.args
                )
                record.args = safe_args
            
            super().emit(record)
        except UnicodeEncodeError:
            # If encoding error persists, force encoding
            try:
                msg = self.format(record)
                safe_msg = msg.encode('utf-8', 'ignore').decode('utf-8')
                self.stream.write(safe_msg + self.terminator)
                self.flush()
            except Exception:
                pass  # Last resort: ignore


class ColoredFormatter(logging.Formatter):
    """Colored log formatter"""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m',       # Reset
    }
    
    def __init__(self, fmt: str, use_colors: bool = True):
        super().__init__(fmt)
        self.use_colors = use_colors
    
    def format(self, record: logging.LogRecord) -> str:
        # Clean message
        if isinstance(record.msg, str):
            record.msg = sanitize_for_log(record.msg)
        
        if self.use_colors and sys.platform != 'win32':
            # Windows needs ANSI support enabled, simplified handling
            levelname = record.levelname
            if levelname in self.COLORS:
                record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
        
        return super().format(record)


class LoggerManager:
    """Logger Manager - Singleton Pattern"""
    
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
        Configure logging
        
        Args:
            level: Console log level
            log_file: Log file path
            console: Whether to output to console
            file_level: File log level
            max_bytes: Maximum size of single log file
            backup_count: Number of backup files to keep
        """
        # Clear existing handlers
        self.clear_handlers()
        self.logger.setLevel(getattr(logging, level.upper()))
        
        # Create formatters
        console_fmt = ColoredFormatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            use_colors=True
        )
        file_fmt = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s'
        )
        
        # Console handler
        if console:
            console_handler = SafeStreamHandler(sys.stdout)
            console_handler.setLevel(getattr(logging, level.upper()))
            console_handler.setFormatter(console_fmt)
            self.logger.addHandler(console_handler)
            self.handlers.append(console_handler)
        
        # File handler
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
                self.logger.warning(f"Failed to create file log handler: {e}")
        
        return self.logger
    
    def clear_handlers(self):
        """Clear all handlers"""
        for handler in self.handlers:
            self.logger.removeHandler(handler)
            handler.close()
        self.handlers.clear()
    
    def get_logger(self, name: Optional[str] = None) -> logging.Logger:
        """Get named logger"""
        if name:
            return self.logger.getChild(name)
        return self.logger


# Global logger manager instance
logger_manager = LoggerManager()


def setup_logging(
    level: str = "INFO",
    log_dir: Optional[Path] = None,
    console: bool = True
) -> logging.Logger:
    """
    Quick logging setup
    
    Args:
        level: Log level
        log_dir: Log directory (None for no file output)
        console: Whether to output to console
    
    Returns:
        Configured logger
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
    """Get logger"""
    return logger_manager.get_logger(name)


# Convenient logging functions (for quick debugging)
def debug(msg: str, *args, **kwargs):
    """Debug log"""
    logger_manager.get_logger().debug(msg, *args, **kwargs)


def info(msg: str, *args, **kwargs):
    """Info log"""
    logger_manager.get_logger().info(msg, *args, **kwargs)


def warning(msg: str, *args, **kwargs):
    """Warning log"""
    logger_manager.get_logger().warning(msg, *args, **kwargs)


def error(msg: str, *args, **kwargs):
    """Error log"""
    logger_manager.get_logger().error(msg, *args, **kwargs)


def critical(msg: str, *args, **kwargs):
    """Critical error log"""
    logger_manager.get_logger().critical(msg, *args, **kwargs)


def exception(msg: str, *args, **kwargs):
    """Exception log (auto-records stack trace)"""
    logger_manager.get_logger().exception(msg, *args, **kwargs)

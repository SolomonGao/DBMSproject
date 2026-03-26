"""
异步数据库连接池模块

提供统一的异步数据库连接池管理和查询执行接口。
"""

from .pool import DatabasePool, get_db_pool, close_db_pool
from .errors import (
    # 错误码
    DBErrorCode,
    # 异常类
    DatabaseError,
    ConnectionLostError,
    ConnectionTimeoutError,
    PoolExhaustedError,
    QueryTimeoutError,
    AuthenticationError,
    QuerySyntaxError,
    TableNotFoundError,
    ColumnNotFoundError,
    # 函数
    classify_mysql_error,
)

__all__ = [
    # 连接池
    "DatabasePool",
    "get_db_pool",
    "close_db_pool",
    # 错误码
    "DBErrorCode",
    # 异常类
    "DatabaseError",
    "ConnectionLostError",
    "ConnectionTimeoutError",
    "PoolExhaustedError",
    "QueryTimeoutError",
    "AuthenticationError",
    "QuerySyntaxError",
    "TableNotFoundError",
    "ColumnNotFoundError",
    # 函数
    "classify_mysql_error",
]

"""
数据库错误处理模块

提供 MySQL 错误分类、特定异常类型和错误处理工具。
"""

from enum import Enum
from typing import Optional
import aiomysql


class DBErrorCode(Enum):
    """MySQL 常见错误码分类"""
    # 连接类错误
    CONNECTION_LOST = 2006          # MySQL server has gone away
    CONNECTION_TIMEOUT = 2013       # Lost connection during query
    CONNECTION_REFUSED = 2003       # Can't connect to MySQL server
    
    # 权限类错误
    ACCESS_DENIED = 1045            # Access denied for user
    
    # 资源类错误
    TOO_MANY_CONNECTIONS = 1040     # Too many connections
    OUT_OF_MEMORY = 1037            # Out of memory
    
    # 锁类错误
    LOCK_WAIT_TIMEOUT = 1205        # Lock wait timeout exceeded
    DEADLOCK = 1213                 # Deadlock found
    
    # 查询类错误
    PARSE_ERROR = 1064              # SQL syntax error
    UNKNOWN_TABLE = 1109            # Unknown table
    UNKNOWN_COLUMN = 1054           # Unknown column
    DUPLICATE_ENTRY = 1062          # Duplicate entry


class DatabaseError(Exception):
    """
    数据库操作异常基类
    
    Attributes:
        message: 错误描述
        error_code: MySQL 错误码
        original_error: 原始异常对象
    """
    def __init__(
        self, 
        message: str, 
        error_code: Optional[int] = None, 
        original_error: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.original_error = original_error
    
    def __str__(self) -> str:
        if self.error_code:
            return f"[Error {self.error_code}] {self.message}"
        return self.message
    
    def is_retryable(self) -> bool:
        """判断此错误是否可以通过重试解决"""
        return False


class ConnectionLostError(DatabaseError):
    """连接丢失错误（可重试）"""
    def is_retryable(self) -> bool:
        return True


class ConnectionTimeoutError(DatabaseError):
    """连接超时错误（可重试）"""
    def is_retryable(self) -> bool:
        return True


class PoolExhaustedError(DatabaseError):
    """连接池耗尽错误"""
    pass


class QueryTimeoutError(DatabaseError):
    """查询超时/锁等待错误"""
    def is_retryable(self) -> bool:
        # 锁等待可以重试
        if self.error_code == DBErrorCode.LOCK_WAIT_TIMEOUT.value:
            return True
        return False


class AuthenticationError(DatabaseError):
    """数据库认证失败"""
    pass


class QuerySyntaxError(DatabaseError):
    """SQL 语法错误"""
    pass


class TableNotFoundError(DatabaseError):
    """表不存在"""
    pass


class ColumnNotFoundError(DatabaseError):
    """列不存在"""
    pass


def classify_mysql_error(error: aiomysql.Error) -> DatabaseError:
    """
    分类 MySQL 错误，转换为特定异常类型
    
    根据错误码将通用 MySQL 错误转换为特定异常类型，
    便于调用方根据错误类型做不同处理。
    
    Args:
        error: MySQL 原始错误对象
        
    Returns:
        DatabaseError: 分类后的特定异常
        
    Example:
        try:
            await cursor.execute("SELECT * FROM nonexistent")
        except aiomysql.Error as e:
            db_error = classify_mysql_error(e)
            if isinstance(db_error, TableNotFoundError):
                print(f"表不存在: {db_error}")
            elif db_error.is_retryable():
                print("可以重试")
    """
    # 提取错误码和消息
    error_code = None
    error_msg = str(error)
    
    # aiomysql.Error 通常是 pymysql.err.MySQLError 的子类
    # 错误码可能在 args[0] 或 errno 属性中
    if hasattr(error, 'args') and len(error.args) > 0:
        if isinstance(error.args[0], int):
            error_code = error.args[0]
    if error_code is None and hasattr(error, 'errno'):
        error_code = error.errno
    
    # 根据错误码分类
    # 连接类错误（可重试）
    if error_code == DBErrorCode.CONNECTION_LOST.value:
        return ConnectionLostError(
            f"数据库连接已断开: {error_msg}",
            error_code=error_code,
            original_error=error
        )
    
    if error_code == DBErrorCode.CONNECTION_TIMEOUT.value:
        return ConnectionTimeoutError(
            f"数据库连接超时: {error_msg}",
            error_code=error_code,
            original_error=error
        )
    
    if error_code == DBErrorCode.CONNECTION_REFUSED.value:
        return ConnectionLostError(
            f"无法连接到数据库服务器: {error_msg}",
            error_code=error_code,
            original_error=error
        )
    
    # 认证错误
    if error_code == DBErrorCode.ACCESS_DENIED.value:
        return AuthenticationError(
            f"数据库认证失败: {error_msg}",
            error_code=error_code,
            original_error=error
        )
    
    # 资源类错误
    if error_code == DBErrorCode.TOO_MANY_CONNECTIONS.value:
        return PoolExhaustedError(
            f"数据库连接过多: {error_msg}",
            error_code=error_code,
            original_error=error
        )
    
    # 锁类错误
    if error_code in [DBErrorCode.LOCK_WAIT_TIMEOUT.value, DBErrorCode.DEADLOCK.value]:
        return QueryTimeoutError(
            f"查询锁超时: {error_msg}",
            error_code=error_code,
            original_error=error
        )
    
    # 语法错误
    if error_code == DBErrorCode.PARSE_ERROR.value:
        return QuerySyntaxError(
            f"SQL 语法错误: {error_msg}",
            error_code=error_code,
            original_error=error
        )
    
    # 表不存在
    if error_code == DBErrorCode.UNKNOWN_TABLE.value:
        return TableNotFoundError(
            f"表不存在: {error_msg}",
            error_code=error_code,
            original_error=error
        )
    
    # 列不存在
    if error_code == DBErrorCode.UNKNOWN_COLUMN.value:
        return ColumnNotFoundError(
            f"列不存在: {error_msg}",
            error_code=error_code,
            original_error=error
        )
    
    # 其他未知错误
    return DatabaseError(
        f"数据库错误: {error_msg}",
        error_code=error_code,
        original_error=error
    )


# 导出所有内容
__all__ = [
    # 错误码枚举
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

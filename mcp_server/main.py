"""
Kimi Smart MCP Server

FastMCP 服务器入口，提供以下工具：
- calculate: 数学计算
- smart_search: 智能搜索  
- get_schema: 获取数据库表结构（Markdown 格式）
- get_schema_prompt: 获取数据库表结构（LLM Prompt 格式）
- execute_sql: 执行安全 SQL 查询
"""

import sys
import argparse
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from app.tools import init_tools
from app.database import close_db_pool, get_db_pool


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="Kimi Smart MCP Server")
    parser.add_argument(
        '--transport', 
        choices=['stdio', 'sse'], 
        default='stdio',
        help='传输模式: stdio (默认) 或 sse'
    )
    parser.add_argument(
        '--port', 
        type=int, 
        default=8000,
        help='SSE 模式端口 (默认: 8000)'
    )
    return parser.parse_args()


@asynccontextmanager
async def app_lifespan(mcp: FastMCP):
    """
    应用生命周期管理
    
    启动时初始化资源，关闭时清理资源。
    """
    # ===== 启动阶段 =====
    sys.stderr.write("正在初始化 MCP Server...\n")
    
    try:
        # 初始化数据库连接池
        await get_db_pool()
        sys.stderr.write("数据库连接池初始化成功\n")
        
        # 健康检查
        pool = await get_db_pool()
        health = await pool.health_check()
        if health["status"] == "healthy":
            sys.stderr.write(
                f"数据库健康检查通过 (延迟: {health['latency_ms']}ms, "
                f"连接ID: {health.get('connection_id', 'N/A')})\n"
            )
            sys.stderr.write(f"连接池状态: {health['free_connections']}/{health['pool_size']} 空闲连接\n")
        else:
            sys.stderr.write(f"数据库健康检查失败: {health.get('error')}\n")
            
    except Exception as e:
        sys.stderr.write(f"数据库初始化失败: {e}\n")
        # 数据库不是必须的，继续启动
    
    sys.stderr.write("MCP Server 已就绪\n")
    
    yield  # 服务器运行中
    
    # ===== 关闭阶段 =====
    sys.stderr.write("正在关闭 MCP Server...\n")
    await close_db_pool()
    sys.stderr.write("资源清理完成\n")


def main():
    """主入口函数"""
    args = parse_args()
    
    # 创建 FastMCP 实例
    mcp = FastMCP("v1", lifespan=app_lifespan)
    
    # 使用装饰器模式注册所有工具
    init_tools(mcp)
    
    # 打印启动信息
    sys.stderr.write(f"KimiSmartTools MCP Server Starting...\n")
    sys.stderr.write(f"Transport: {args.transport}\n")
    
    try:
        if args.transport == 'stdio':
            mcp.run(transport='stdio')
        else:
            sys.stderr.write(f"SSE Server running on http://localhost:{args.port}/sse\n")
            mcp.run(transport='sse', port=args.port)
    except KeyboardInterrupt:
        sys.stderr.write("\n收到中断信号，正在关闭...\n")
    except Exception as e:
        sys.stderr.write(f"Critical Error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()

"""
GDELT MCP Server

专门针对 GDELT 事件数据库的 MCP 服务器。

提供的工具：
- 基础查询: get_schema, get_schema_guide, execute_sql
- 便捷查询: query_by_time_range, query_by_actor, query_by_location
- 统计分析: analyze_daily_events, analyze_top_actors, analyze_conflict_cooperation
- 可视化: generate_chart
"""

import sys
import argparse
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from app.tools import init_tools
from app.database import close_db_pool, get_db_pool


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="GDELT MCP Server")
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
    """应用生命周期管理"""
    sys.stderr.write("[GDELT] 正在初始化 MCP Server...\n")
    
    try:
        await get_db_pool()
        sys.stderr.write("[GDELT] 数据库连接池初始化成功\n")
        
        pool = await get_db_pool()
        health = await pool.health_check()
        if health["status"] == "healthy":
            sys.stderr.write(
                f"[GDELT] 数据库健康检查通过 (延迟: {health['latency_ms']}ms)\n"
            )
        else:
            sys.stderr.write(f"[GDELT] 数据库健康检查失败: {health.get('error')}\n")
    except Exception as e:
        sys.stderr.write(f"[GDELT] 数据库初始化失败: {e}\n")
    
    sys.stderr.write("[GDELT] MCP Server 已就绪\n")
    
    yield
    
    sys.stderr.write("[GDELT] 正在关闭 MCP Server...\n")
    await close_db_pool()
    sys.stderr.write("[GDELT] 资源清理完成\n")


def main():
    """主入口函数"""
    args = parse_args()
    
    mcp = FastMCP("gdelt-server", lifespan=app_lifespan)
    
    # 注册所有 GDELT 工具
    init_tools(mcp)
    
    sys.stderr.write(f"[GDELT] Server Starting...\n")
    sys.stderr.write(f"[GDELT] Transport: {args.transport}\n")
    
    try:
        if args.transport == 'stdio':
            mcp.run(transport='stdio')
        else:
            sys.stderr.write(f"[GDELT] SSE Server: http://localhost:{args.port}/sse\n")
            mcp.run(transport='sse', port=args.port)
    except KeyboardInterrupt:
        sys.stderr.write("\n[GDELT] 收到中断信号\n")
    except Exception as e:
        sys.stderr.write(f"[GDELT] Error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()

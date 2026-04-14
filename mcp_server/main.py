"""
GDELT MCP Server

MCP server specifically for GDELT event database.

Tools provided:
- Basic queries: get_schema, get_schema_guide, execute_sql
- Convenient queries: query_by_time_range, query_by_actor, query_by_location
- Statistical analysis: analyze_daily_events, analyze_top_actors, analyze_conflict_cooperation
- Visualization: generate_chart
"""

import sys
import argparse
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from app.tools import init_tools
from app.database import close_db_pool, get_db_pool


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="GDELT MCP Server")
    parser.add_argument(
        '--transport',
        choices=['stdio', 'sse'],
        default='stdio',
        help='Transport mode: stdio (default) or sse'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8000,
        help='SSE mode port (default: 8000)'
    )
    return parser.parse_args()


@asynccontextmanager
async def app_lifespan(mcp: FastMCP):
    """Application lifecycle management"""
    sys.stderr.write("[GDELT] Initializing MCP Server...\n")
    
    try:
        await get_db_pool()
        sys.stderr.write("[GDELT] Database connection pool initialized\n")
        
        pool = await get_db_pool()
        health = await pool.health_check()
        if health["status"] == "healthy":
            sys.stderr.write(
                f"[GDELT] Database health check passed (latency: {health['latency_ms']}ms)\n"
            )
        else:
            sys.stderr.write(f"[GDELT] Database health check failed: {health.get('error')}\n")
    except Exception as e:
        sys.stderr.write(f"[GDELT] Database initialization failed: {e}\n")
    
    sys.stderr.write("[GDELT] MCP Server ready\n")
    
    yield
    
    sys.stderr.write("[GDELT] Shutting down MCP Server...\n")
    await close_db_pool()
    sys.stderr.write("[GDELT] Resource cleanup completed\n")


def main():
    """Main entry function"""
    args = parse_args()
    
    mcp = FastMCP("gdelt-server", lifespan=app_lifespan)
    
    # Register all GDELT tools
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
        sys.stderr.write("\n[GDELT] Interrupt signal received\n")
    except Exception as e:
        sys.stderr.write(f"[GDELT] Error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()

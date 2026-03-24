import sys
import argparse
from fastmcp import FastMCP
from app.tools import init_tools
from app.tools.database import get_schema, execute_sql


def parse_args():
    parser = argparse.ArgumentParser(description="Kimi Smart MCP Server")
    parser.add_argument('--transport', choices=['stdio', 'sse'], default='stdio')
    parser.add_argument('--port', type=int, default=8000)
    return parser.parse_args()

def main():
    args = parse_args()
    mcp = FastMCP("v1")
    init_tools(mcp)
    mcp.add_tool(get_schema)
    mcp.add_tool(execute_sql)
    # 打印非通信信息必须通过 stderr
    sys.stderr.write(f"🛠️  KimiSmartTools MCP Server Starting...\n")
    sys.stderr.write(f"📡 Transport: {args.transport}\n")

    try:
        if args.transport == 'stdio':
            mcp.run(transport='stdio')
        else:
            sys.stderr.write(f"🌍 SSE Server running on http://localhost:{args.port}/sse\n")
            mcp.run(transport='sse', port=args.port)
    except Exception as e:
        sys.stderr.write(f"❌ Critical Error: {e}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
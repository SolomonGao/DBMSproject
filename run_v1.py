#!/usr/bin/env python3
# run_v1.py - CLI v1 启动脚本（支持交互式配置）
"""
GDELT MCP Client App v1 - 交互式配置版本

使用方法:
    python run_v1.py [选项]

选项:
    --config               强制启动配置向导
    --log-level {DEBUG,INFO,WARNING,ERROR}  设置日志级别
    --no-file-log          禁用文件日志
    -h, --help             显示帮助

特性:
    - 交互式 LLM 提供商选择 (Kimi/Claude/Gemini)
    - 自动检测并提示配置
    - 支持多提供商切换
"""

import argparse
import asyncio
import sys
from pathlib import Path

# 确保可以导入 mcp_app
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from mcp_app.config_wizard import ConfigWizard
from mcp_app.config import load_config, print_config
from mcp_app.llm import LLMClient
from mcp_app.client import MCPClient
from mcp_app.cli import ChatCLI
from mcp_app.logger import setup_logging, get_logger

logger = get_logger("main")


async def main():
    """主函数"""
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description="GDELT MCP Client App v1",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run_v1.py                          # 启动应用（首次会提示配置）
  python run_v1.py --config                 # 强制重新配置
  python run_v1.py --log-level DEBUG        # 调试模式
        """
    )
    parser.add_argument(
        '--config',
        action='store_true',
        help='强制启动配置向导'
    )
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default=None,
        help='日志级别（覆盖 .env 配置）'
    )
    parser.add_argument(
        '--no-file-log',
        action='store_true',
        help='禁用文件日志'
    )
    args = parser.parse_args()
    
    # 初始化配置向导
    wizard = ConfigWizard()
    
    # 检查/启动配置
    if args.config:
        # 强制启动配置向导
        print("🚀 强制启动配置向导...")
        success = wizard.run()
        if not success:
            sys.exit(1)
        print("\n配置完成！正在启动应用...\n")
    else:
        # 检查配置，如不存在则提示
        if not wizard.check_and_prompt():
            sys.exit(1)
    
    # 1. 加载配置
    print("🚀 启动 GDELT MCP Client App v1...")
    
    try:
        config = load_config()
    except ValueError as e:
        print(f"❌ 配置错误: {e}")
        print("\n建议运行: python run_v1.py --config")
        sys.exit(1)
    
    # 2. 设置日志
    log_level = args.log_level or config.log_level
    log_dir = None if args.no_file_log else config.log_dir
    
    setup_logging(
        level=log_level,
        log_dir=log_dir,
        console=True
    )
    
    logger.info("=" * 60)
    logger.info("GDELT MCP Client App v1 启动")
    logger.info("=" * 60)
    
    # 3. 打印配置
    print_config(config)
    
    # 4. 初始化 MCP 客户端
    mcp_client = MCPClient(
        server_path=config.mcp_server_path,
        transport=config.mcp_transport,
        port=config.mcp_port
    )
    
    try:
        # 5. 连接到 MCP Server
        connected = await mcp_client.connect()
        if not connected:
            logger.error("无法连接到 MCP Server，请检查:")
            logger.error("  1. MCP Server 文件是否存在")
            logger.error("  2. Python 环境是否正确")
            sys.exit(1)
        
        # 6. 发现工具
        await mcp_client.discover_tools()
        
    except Exception as e:
        logger.exception(f"MCP 初始化失败: {e}")
        sys.exit(1)
    
    # 7. 初始化 LLM 客户端
    try:
        llm_client = LLMClient(
            provider=config.llm_provider,
            api_key=config.get_api_key(),
            base_url=config.llm_base_url,
            model=config.llm_model,
            temperature=config.llm_temperature,
            max_tokens=config.llm_max_tokens
        )
        logger.info(f"LLM 客户端初始化完成 (提供商: {config.llm_provider})")
    except Exception as e:
        logger.exception(f"LLM 初始化失败: {e}")
        sys.exit(1)
    
    # 8. 启动 CLI
    cli = ChatCLI(config, llm_client, mcp_client)
    
    # 处理信号
    import signal
    def signal_handler(sig, frame):
        logger.info(f"收到信号 {sig}，正在退出...")
        asyncio.create_task(mcp_client.close())
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await cli.chat_loop()
    finally:
        # 清理资源
        logger.info("正在清理资源...")
        await mcp_client.close()
        if 'llm_client' in locals():      # <--- 加上这一行
            await llm_client.close()      # <--- 加上这一行
        logger.info("应用已退出")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 再见！")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"程序错误: {e}")
        sys.exit(1)

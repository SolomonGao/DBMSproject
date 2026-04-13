#!/usr/bin/env python3
# run_v1.py - CLI v1 startup script（Supportsinteractive configuration）
"""
GDELT MCP Client App v1 - interactive configurationversion

usemethod:
    python run_v1.py [selectitem]

selectitem:
    --config               Force start configuration wizard
    --log-level {DEBUG,INFO,WARNING,ERROR}  Setloglevel
    --no-file-log          禁usefilelog
    -h, --help             displayHelp

feature:
    - 交互pattern LLM Provides商selectselect (Kimi/Claude/Gemini)
    - 自动detectandHintconfig
    - SupportsmultiProvides商切换
"""

import argparse
import asyncio
import sys
from pathlib import Path

# 确保可thereforeImport mcp_app
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
    """主function"""
    
    # parsecommandrowArgs
    parser = argparse.ArgumentParser(
        description="GDELT MCP Client App v1",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  python run_v1.py                          # startApply（首timewillHintconfig）
  python run_v1.py --config                 # 强system重newconfig
  python run_v1.py --log-level DEBUG        # Debugmodelpattern
        """
    )
    parser.add_argument(
        '--config',
        action='store_true',
        help='Force start configuration wizard'
    )
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default=None,
        help='loglevel（覆盖 .env config）'
    )
    parser.add_argument(
        '--no-file-log',
        action='store_true',
        help='禁usefilelog'
    )
    args = parser.parse_args()
    
    # Initializeconfigwizard
    wizard = ConfigWizard()
    
    # Check/startconfig
    if args.config:
        # Force start configuration wizard
        print("🚀 Force start configuration wizard...")
        success = wizard.run()
        if not success:
            sys.exit(1)
        print("\nconfigcompleted！correctinstartApply...\n")
    else:
        # Checkconfig，ifdoes not exist则Hint
        if not wizard.check_and_prompt():
            sys.exit(1)
    
    # 1. Loadconfig
    print("🚀 start GDELT MCP Client App v1...")
    
    try:
        config = load_config()
    except ValueError as e:
        print(f"❌ configerror: {e}")
        print("\nbuild议运row: python run_v1.py --config")
        sys.exit(1)
    
    # 2. Setlog
    log_level = args.log_level or config.log_level
    log_dir = None if args.no_file_log else config.log_dir
    
    setup_logging(
        level=log_level,
        log_dir=log_dir,
        console=True
    )
    
    logger.info("=" * 60)
    logger.info("GDELT MCP Client App v1 start")
    logger.info("=" * 60)
    
    # 3. printconfig
    print_config(config)
    
    # 4. Initialize MCP 客户end
    mcp_client = MCPClient(
        server_path=config.mcp_server_path,
        transport=config.mcp_transport,
        port=config.mcp_port
    )
    
    try:
        # 5. jointo MCP Server
        connected = await mcp_client.connect()
        if not connected:
            logger.error("unablejointo MCP Server，pleasecheck:")
            logger.error("  1. MCP Server fileisNosavein")
            logger.error("  2. Python environmentisNocorrect确")
            sys.exit(1)
        
        # 6. send现tool
        await mcp_client.discover_tools()
        
    except Exception as e:
        logger.exception(f"MCP Initializefailed: {e}")
        sys.exit(1)
    
    # 7. Initialize LLM 客户end
    try:
        llm_client = LLMClient(
            provider=config.llm_provider,
            api_key=config.get_api_key(),
            base_url=config.llm_base_url,
            model=config.llm_model,
            temperature=config.llm_temperature,
            max_tokens=config.llm_max_tokens
        )
        logger.info(f"LLM 客户endInitializecompleted (Provides商: {config.llm_provider})")
    except Exception as e:
        logger.exception(f"LLM Initializefailed: {e}")
        sys.exit(1)
    
    # 8. start CLI
    cli = ChatCLI(config, llm_client, mcp_client)
    
    # Process信号
    import signal
    def signal_handler(sig, frame):
        logger.info(f"acceptto信号 {sig}，correctinExit...")
        asyncio.create_task(mcp_client.close())
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await cli.chat_loop()
    finally:
        # cleanup资源
        logger.info("correctincleanup资源...")
        await mcp_client.close()
        if 'llm_client' in locals():      # <--- adduploadthis一row
            await llm_client.close()      # <--- adduploadthis一row
        logger.info("ApplyalreadyExit")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 再view！")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"程序error: {e}")
        sys.exit(1)

# GDELT MCP Client App

A standalone MCP client application with multi-LLM support, integrating with the Model Context Protocol (MCP) to connect tool servers with Large Language Models (LLMs). Built for GDELT 2.0 dataset analysis (2024 North American events).

**Institution**: Virginia Tech ("Ut Prosim" - That I May Serve)  
**Research Team**: Xing Gao, Xiangxin Tang, Yuxin Miao, Ziliang Chen

---

## Features

- 🤖 **Multi-LLM Support**: Kimi Code, Moonshot, Claude, Gemini
- 🔧 **MCP Protocol**: Full Model Context Protocol integration
- 🛠️ **Tool Calling**: Automatic tool discovery and execution
- 🗄️ **GDELT Database**: MySQL integration for event data analysis
- 📊 **Logging**: Colorful console output with file logging
- ⚙️ **Interactive CLI**: Chat interface with command support

---

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Or using pyproject.toml:
```bash
pip install -e .
```

### 2. Configure API Key

**Option A: Using Configuration Wizard (Recommended)**
```bash
python run_v1.py --config
```

**Option B: Manual Configuration**
```bash
# Copy example config
copy config.example.json config.json

# Edit config.json with your API keys
```

### 3. Run Application

```bash
python run_v1.py
```

**Debug Mode:**
```bash
python run_v1.py --log-level DEBUG
```

**Disable File Logging:**
```bash
python run_v1.py --no-file-log
```

---

## Usage Example

Launch the interactive chat interface:

```
============================================================
⚙️ 欢迎使用 GDELT MCP Client v1
============================================================

📋 配置摘要:
   ⭐ LLM 提供商: Kimi Code
   🔑 API Key: sk-abc1...xyz9
   🤖 LLM 模型: kimi-k2-0905-preview
   🔧 MCP Server: stdio模式

💡 可用命令:
   /help    - 显示帮助信息
   /clear   - 清空对话历史
   /tools   - 显示可用工具列表
   /status  - 显示状态信息
   /quit    - 退出程序

📝 直接输入消息开始对话...
------------------------------------------------------------

👤 你: 帮我计算一下圆周率的平方根
🤖 AI: 
🛠️  调用工具: calculate
✅ 工具返回: 结果: 1.77
圆周率的平方根约等于 1.77。
```

---

## Available Commands

| Command | Alias | Description |
|---------|-------|-------------|
| `/help` | `/h`, `help` | Show help information |
| `/clear` | `/c`, `clear` | Clear conversation history |
| `/tools` | `/t`, `tools` | List available tools |
| `/status` | `/s`, `status` | Show current status |
| `/quit` | `/q`, `/exit` | Exit application |

---

## Project Structure

```
project/
├── mcp_app/                    # Core application package
│   ├── __init__.py
│   ├── logger.py              # Logging module (colorful output & file)
│   ├── config.py              # Configuration management (.env based)
│   ├── config_json.py         # JSON configuration management
│   ├── config_wizard_json.py  # Interactive configuration wizard
│   ├── providers.py           # LLM provider configurations
│   ├── client.py              # MCP client wrapper
│   ├── llm.py                 # LLM interface wrapper
│   └── cli.py                 # CLI interface
│
├── mcp_server/                 # MCP Server
│   ├── __init__.py
│   ├── main.py                # FastMCP service entry point
│   └── app/                   # MCP Server application modules
│       ├── __init__.py
│       ├── models.py          # Pydantic input models
│       ├── tools/             # Tool registration modules
│       │   ├── __init__.py
│       │   ├── calculator.py
│       │   └── search.py
│       └── services/          # Business logic services
│           ├── __init__.py
│           ├── calculator.py
│           └── analysis.py
│
├── db_scripts/                 # Database scripts
│   ├── gdelt_db_v1.sql        # Database schema
│   ├── import_event.py        # Data import script
│   └── data_view.py           # Data preview
│
├── data/                       # GDELT data files (CSV chunks)
│   └── *.csv
│
├── logs/                       # Log files (created at runtime)
│   └── mcp_app_YYYYMMDD.log
│
├── run_v1.py                   # Application entry point ⭐
├── test_api_v2.py              # API connection test script
├── requirements.txt            # Python dependencies
├── pyproject.toml             # Project configuration (PEP 621)
├── config.json                # User configuration (created by wizard)
├── config.example.json        # Configuration template
├── .env                        # Environment variables (legacy)
├── .env_example_v1            # Environment template
├── README.md                  # This file
├── DOCUMENTATION.md           # Detailed technical documentation
└── index.html                 # Project frontend page
```

---

## Configuration

Configuration is stored in `config.json` (created automatically by the wizard):

```json
{
  "llm_provider": "kimi_code",
  "api_keys": {
    "kimi_code": "sk-your-api-key",
    "moonshot": "",
    "anthropic": "",
    "gemini": ""
  },
  "mcp": {
    "server_path": "",
    "transport": "stdio",
    "port": 8000
  },
  "llm": {
    "model": "kimi-k2-0905-preview",
    "base_url": "https://api.kimi.com/coding/v1",
    "temperature": 0.7,
    "max_tokens": 4096
  },
  "logging": {
    "level": "INFO",
    "log_to_file": true,
    "log_dir": "./logs"
  },
  "debug": false
}
```

### Supported LLM Providers

| Provider | API Key Variable | Base URL | Default Model |
|----------|-----------------|----------|---------------|
| **Kimi Code** (Recommended) | `KIMI_CODE_API_KEY` | https://api.kimi.com/coding/v1 | kimi-k2-0905-preview |
| Moonshot AI | `MOONSHOT_API_KEY` | https://api.moonshot.cn/v1 | kimi-k2-0905-preview |
| Claude | `ANTHROPIC_API_KEY` | https://api.anthropic.com/v1 | claude-3-5-sonnet-20241022 |
| Gemini | `GEMINI_API_KEY` | https://generativelanguage.googleapis.com/v1beta | gemini-1.5-pro |

---

## MCP Server

### Run Standalone

```bash
# STDIO mode (default)
python mcp_server/main.py

# SSE mode
python mcp_server/main.py --transport sse --port 8000
```

### Available Tools

1. **calculate** - Execute mathematical calculations safely
2. **smart_search** - Search knowledge base

---

## Database Setup (Optional)

For GDELT data analysis:

```bash
# 1. Create database
mysql -u root -p < db_scripts/gdelt_db_v1.sql

# 2. Import data
python db_scripts/import_event.py
```

---

## Logging System

- **Console Output**: Colored by level (INFO=green, WARNING=yellow, ERROR=red)
- **File Logging**: Auto-rotated daily, keeps 5 backups
- **Log Location**: `logs/mcp_app_YYYYMMDD.log`

---

## Command Line Arguments

```bash
python run_v1.py --help
```

| Argument | Description |
|----------|-------------|
| `--config` | Run configuration wizard |
| `--log-level {DEBUG,INFO,WARNING,ERROR}` | Set log level |
| `--no-file-log` | Disable file logging |

---

## Architecture

```
┌─────────────────┐
│    run_v1.py    │  Entry point
└────────┬────────┘
         │
┌────────▼────────┐
│    mcp_app      │
├─────────────────┤
│  config*.py     │  Configuration management
│  logger.py      │  Unified logging
│  client.py      │  MCP client (stdio/sse)
│  llm.py         │  LLM API wrapper
│  cli.py         │  Interactive interface
└─────────────────┘
         │
┌────────▼────────┐
│  mcp_server/    │  FastMCP tools
└─────────────────┘
```

---

## Data Source

**GDELT 2.0 Dataset** - North America Events (2024)
- 100 CSV files (000000-000099 chunks + full file)
- Geographic coverage: United States, Canada, Mexico
- Temporal coverage: Full year 2024

---

## Tech Stack

- Python 3.10+
- MCP (Model Context Protocol) >= 1.0.0
- FastMCP
- OpenAI SDK
- Pydantic >= 2.9.0
- MySQL 8.0+ (with spatial extensions)

---

## License

Virginia Tech Research Project

---

## Resources

- **Project Proposal**: `Proposal_Tang_Gao_Miao_Chen.pdf`
- **Detailed Docs**: `DOCUMENTATION.md`
- **GDELT Project**: https://www.gdeltproject.org/
- **MCP Protocol**: https://modelcontextprotocol.io/

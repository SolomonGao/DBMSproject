# GDELT MCP Client App

一个类似 OpenClaw 的独立 MCP 客户端应用，集成了 Kimi AI 和工具调用功能。

## 功能特点

- 🤖 **Kimi AI 集成**: 使用 Moonshot AI (Kimi) 作为对话模型
- 🔧 **MCP 工具调用**: 自动发现并调用 MCP Server 提供的工具
- 💬 **交互式 CLI**: 简洁的命令行聊天界面
- 📊 **完善的日志**: 支持控制台和文件日志，带颜色输出
- ⚙️ **灵活配置**: 通过 `.env` 文件自定义所有参数

## 快速开始

### 1. 安装依赖

```bash
pip install mcp fastmcp openai python-dotenv
```

### 2. 配置 API Key

```bash
# 复制配置模板
copy .env_example .env

# 编辑 .env 文件，填入你的 Moonshot API Key
```

最少配置：
```
MOONSHOT_API_KEY=your_moonshot_api_key_here
```

### 3. 运行应用

```bash
python run.py
```

或使用调试模式：
```bash
python run.py --log-level DEBUG
```

## 使用方法

启动后会进入交互式聊天界面：

```
============================================================
⚙️ 欢迎使用 GDELT MCP Client
============================================================

📋 配置摘要:
   🌙 Moonshot API: sk-abc1...xyz9
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

👤 你: 北京今天天气怎么样？
🤖 AI: 
🛠️  调用工具: get_weather
✅ 工具返回: 北京 2026-03-14: 晴, 22°C
北京今天是晴天，温度 22°C，天气不错！
```

## 可用命令

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助信息 |
| `/clear` | 清空对话历史 |
| `/tools` | 列出所有可用工具 |
| `/status` | 显示当前状态 |
| `/quit` | 退出应用 |

## 项目结构

```
project/
├── mcp_app/              # 应用主包
│   ├── __init__.py
│   ├── logger.py         # 日志模块（支持彩色输出和文件）
│   ├── config.py         # 配置管理
│   ├── client.py         # MCP 客户端
│   ├── llm.py            # LLM 接口
│   └── cli.py            # CLI 界面
├── mcp_server/           # MCP 服务器
│   └── server.py
├── logs/                 # 日志文件目录（运行时创建）
├── run.py                # 启动脚本
├── .env                  # 用户配置（需创建）
└── .env_example          # 配置模板
```

## 配置说明

通过 `.env` 文件配置：

| 变量名 | 必填 | 默认值 | 说明 |
|--------|------|--------|------|
| `MOONSHOT_API_KEY` | ✅ | - | Kimi API Key |
| `MCP_SERVER_PATH` | ❌ | 自动检测 | MCP Server 路径 |
| `MCP_TRANSPORT` | ❌ | stdio | 传输模式 (stdio/sse) |
| `LLM_MODEL` | ❌ | kimi-k2-0905-preview | 模型名称 |
| `LLM_TEMPERATURE` | ❌ | 0.7 | 温度参数 |
| `LOG_LEVEL` | ❌ | INFO | 日志级别 |
| `LOG_TO_FILE` | ❌ | true | 是否写入文件日志 |

## 日志系统

日志支持：
- **控制台输出**: 带颜色（INFO=绿色, WARNING=黄色, ERROR=红色）
- **文件日志**: 自动按日期分割，保留 5 个备份
- **日志级别**: DEBUG/INFO/WARNING/ERROR 可调

日志文件位置：`logs/mcp_app_YYYYMMDD.log`

## 命令行参数

```bash
python run.py --help
```

| 参数 | 说明 |
|------|------|
| `--log-level {DEBUG,INFO,WARNING,ERROR}` | 设置日志级别 |
| `--no-file-log` | 禁用文件日志 |

## 架构设计

### 模块化设计

```
┌─────────────┐
│   run.py    │  启动入口
└──────┬──────┘
       │
┌──────▼──────┐
│  mcp_app    │
├─────────────┤
│  config.py  │  配置加载和验证
│  logger.py  │  统一日志管理
│  client.py  │  MCP 客户端封装
│  llm.py     │  LLM API 封装
│  cli.py     │  交互界面
└─────────────┘
```

### 日志使用示例

```python
from mcp_app.logger import get_logger

logger = get_logger("module_name")
logger.info("信息日志")
logger.error("错误日志")
```

## 技术栈

- Python 3.10+
- MCP (Model Context Protocol)
- FastMCP
- OpenAI SDK
- Moonshot AI (Kimi)

## 许可证

Virginia Tech Research Project

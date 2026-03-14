# GDELT MCP Client App - 技术文档

## 目录
1. [项目概述](#项目概述)
2. [架构设计](#架构设计)
3. [项目结构详解](#项目结构详解)
4. [模块详细说明](#模块详细说明)
5. [MCP Server 说明](#mcp-server-说明)
6. [运行流程](#运行流程)
7. [配置指南](#配置指南)
8. [扩展开发](#扩展开发)

---

## 项目概述

### 什么是这个项目？

**GDELT MCP Client App** 是一个独立的 AI 客户端应用程序，类似 OpenClaw 的设计理念：

- **独立运行**: 用户配置自己的 API Key 后直接运行，无需后端服务
- **MCP 集成**: 通过 Model Context Protocol (MCP) 连接工具服务器
- **AI 驱动**: 集成 Moonshot AI (Kimi) 作为对话模型
- **工具调用**: AI 可以自动调用各种工具完成任务

### 核心流程

```
用户输入 → LLM 判断 → [调用工具 → 执行 → 返回结果] → LLM 生成回复 → 展示给用户
                ↑___________________________________________|
```

---

## 架构设计

### 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                         用户层                               │
│  ┌─────────────┐                                            │
│  │   命令行    │  ← 用户输入/输出                            │
│  └──────┬──────┘                                            │
└─────────┼───────────────────────────────────────────────────┘
          │
┌─────────▼───────────────────────────────────────────────────┐
│                      mcp_app 包                              │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌─────────┐  │
│  │   cli.py  │  │  llm.py   │  │ client.py │  │logger.py│  │
│  │  (界面层)  │  │  (AI层)   │  │(MCP客户端)│  │(日志层) │  │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └────┬────┘  │
│        │              │              │             │       │
│  ┌─────▼──────────────▼──────────────▼─────────────▼─────┐ │
│  │                    config.py (配置层)                  │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    外部服务层                                │
│  ┌─────────────────┐    ┌──────────────────┐               │
│  │ Moonshot AI API │    │  mcp_server/     │               │
│  │   (Kimi模型)     │    │  (本地工具服务)   │               │
│  └─────────────────┘    └──────────────────┘               │
└─────────────────────────────────────────────────────────────┘
```

### 数据流向

```
1. run.py 启动应用
2. config.py 加载配置
3. logger.py 初始化日志
4. client.py 连接 MCP Server
5. client.py 发现可用工具
6. llm.py 初始化 AI 客户端
7. cli.py 启动交互界面
8. 用户输入 → llm.chat() → 可能需要工具调用
9. 如需工具 → client.call_tool() → 返回结果 → llm 继续生成
10. 最终结果展示给用户
```

---

## 项目结构详解

```
project/
│
├── mcp_app/                    # 核心应用包
│   ├── __init__.py            # 包初始化
│   ├── logger.py              # 日志模块 ⭐
│   ├── config.py              # 配置管理 ⭐
│   ├── client.py              # MCP 客户端 ⭐
│   ├── llm.py                 # LLM 接口 ⭐
│   └── cli.py                 # 命令行界面
│
├── mcp_server/                 # MCP 服务器
│   ├── __init__.py
│   └── server.py              # FastMCP 服务
│
├── db_scripts/                 # 数据库脚本（数据导入）
│   ├── gdelt_db_v1.sql        # 数据库Schema
│   ├── import_event.py        # 数据导入脚本
│   └── data_view.py           # 数据预览
│
├── data/                       # GDELT 数据文件
│   └── *.csv                  # 事件数据
│
├── logs/                       # 日志目录（运行时创建）
│   └── mcp_app_YYYYMMDD.log   # 日志文件
│
├── run.py                      # 应用启动入口 ⭐
├── requirements.txt            # Python 依赖
├── pyproject.toml             # 项目配置
├── .env                        # 环境变量（用户配置）
├── .env_example               # 环境变量模板
├── README.md                  # 使用说明
└── DOCUMENTATION.md           # 本技术文档
```

---

## 模块详细说明

### 1. logger.py - 日志模块

**作用**: 提供统一的日志管理，支持彩色控制台输出和文件日志

**关键类**:
- `ColoredFormatter`: 带 ANSI 颜色的格式化器
- `LoggerManager`: 单例日志管理器
- 便捷函数: `debug()`, `info()`, `warning()`, `error()`, `critical()`

**Import 方式**:
```python
# 方式1: 获取命名日志器（推荐）
from mcp_app.logger import get_logger

logger = get_logger("module_name")
logger.info("这是一条信息")
logger.error("这是一条错误")

# 方式2: 使用全局快捷函数
from mcp_app.logger import info, error, debug

info("快速记录信息")
error("快速记录错误")
debug("调试信息")

# 方式3: 设置日志系统
from mcp_app.logger import setup_logging

setup_logging(
    level="DEBUG",           # 日志级别
    log_dir="./logs",        # 日志目录
    console=True             # 是否输出到控制台
)
```

**配置参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `level` | str | "INFO" | 日志级别: DEBUG/INFO/WARNING/ERROR |
| `log_dir` | Path/None | None | 日志目录，None 则不写文件 |
| `console` | bool | True | 是否输出到控制台 |
| `max_bytes` | int | 10MB | 单个日志文件大小限制 |
| `backup_count` | int | 5 | 保留的备份文件数 |

**颜色说明**:
- DEBUG: 青色
- INFO: 绿色
- WARNING: 黄色
- ERROR: 红色
- CRITICAL: 紫色

**使用示例**:
```python
# 完整示例
from mcp_app.logger import setup_logging, get_logger
import logging

# 初始化日志系统
setup_logging(
    level="DEBUG",
    log_dir="./logs",
    console=True
)

# 获取日志器
logger = get_logger("my_module")

# 不同级别的日志
logger.debug("调试信息，用于开发")
logger.info("普通信息，用户可见")
logger.warning("警告信息，需要注意")
logger.error("错误信息，需要处理")
logger.exception("异常信息，自动包含堆栈")

# 格式化输出
user = "Alice"
action = "login"
logger.info(f"用户 {user} 执行了 {action}")
```

---

### 2. config.py - 配置管理模块

**作用**: 从 .env 文件和 YAML 文件加载配置，验证配置有效性

**关键类**:
- `AppConfig`: 配置数据类，包含所有配置项
- `ConfigLoader`: 配置加载器，处理文件读取和解析

**Import 方式**:
```python
# 方式1: 快速加载（推荐）
from mcp_app.config import load_config

config = load_config()
print(config.moonshot_api_key)

# 方式2: 指定配置文件
from mcp_app.config import ConfigLoader

loader = ConfigLoader(env_file="./custom.env")
config = loader.load()

# 方式3: 打印配置
from mcp_app.config import print_config

print_config(config)  # 打印脱敏后的配置
```

**配置项说明**:
```python
@dataclass
class AppConfig:
    # API Keys
    moonshot_api_key: str           # Moonshot API Key
    
    # MCP Server 配置
    mcp_server_path: str            # Server 文件路径
    mcp_transport: str              # stdio 或 sse
    mcp_port: int                   # SSE 模式端口
    
    # LLM 配置
    llm_model: str                  # 模型名称
    llm_base_url: str               # API 地址
    llm_temperature: float          # 温度参数
    llm_max_tokens: int             # 最大 Token 数
    
    # 日志配置
    log_level: str                  # 日志级别
    log_dir: Optional[Path]         # 日志目录
    log_to_file: bool               # 是否写入文件
    
    # 应用配置
    debug: bool                     # 调试模式
```

**环境变量映射**:
| 环境变量 | 配置属性 | 必填 | 默认值 |
|----------|----------|------|--------|
| `MOONSHOT_API_KEY` | `moonshot_api_key` | ✅ | - |
| `MCP_SERVER_PATH` | `mcp_server_path` | ❌ | 自动检测 |
| `MCP_TRANSPORT` | `mcp_transport` | ❌ | stdio |
| `MCP_PORT` | `mcp_port` | ❌ | 8000 |
| `LLM_MODEL` | `llm_model` | ❌ | kimi-k2-0905-preview |
| `LLM_BASE_URL` | `llm_base_url` | ❌ | https://api.moonshot.cn/v1 |
| `LLM_TEMPERATURE` | `llm_temperature` | ❌ | 0.7 |
| `LLM_MAX_TOKENS` | `llm_max_tokens` | ❌ | 4096 |
| `LOG_LEVEL` | `log_level` | ❌ | INFO |
| `LOG_TO_FILE` | `log_to_file` | ❌ | true |
| `DEBUG` | `debug` | ❌ | false |

**使用示例**:
```python
from mcp_app.config import load_config, AppConfig

# 加载配置
try:
    config = load_config()
except ValueError as e:
    print(f"配置错误: {e}")
    exit(1)

# 访问配置
print(f"API Key: {config.get_masked_api_key()}")
print(f"模型: {config.llm_model}")
print(f"Server: {config.mcp_server_path}")

# 转换为字典（用于日志）
config_dict = config.to_dict()
```

---

### 3. client.py - MCP 客户端模块

**作用**: 连接 MCP Server，发现工具，执行工具调用

**关键类**:
- `MCPClient`: MCP 客户端主类

**Import 方式**:
```python
from mcp_app.client import MCPClient
import asyncio

# 创建客户端
client = MCPClient(
    server_path="./mcp_server/server.py",
    transport="stdio",      # 或 "sse"
    port=8000               # SSE 模式使用
)

# 异步连接
async def main():
    # 连接 Server
    connected = await client.connect()
    if not connected:
        print("连接失败")
        return
    
    # 发现工具
    tools = await client.discover_tools()
    print(f"发现 {len(tools)} 个工具")
    
    # 调用工具
    result = await client.call_tool("calculate", {"expression": "1+1"})
    print(result)
    
    # 关闭连接
    await client.close()

asyncio.run(main())
```

**方法说明**:

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `__init__` | `server_path`, `transport`, `port` | - | 初始化客户端 |
| `connect()` | - | `bool` | 连接 MCP Server |
| `discover_tools()` | - | `List[Dict]` | 发现并转换工具 |
| `call_tool(name, args)` | 工具名, 参数 | `str` | 调用工具 |
| `create_tool_executor()` | - | `Callable` | 创建同步执行器 |
| `close()` | - | - | 关闭连接 |

**工具格式转换**:

MCP 格式 → OpenAI 格式:
```python
# MCP 格式
{
    "name": "calculate",
    "description": "执行数学计算",
    "inputSchema": {
        "type": "object",
        "properties": {
            "expression": {"type": "string"}
        }
    }
}

# 转换为 OpenAI 格式
{
    "type": "function",
    "function": {
        "name": "calculate",
        "description": "执行数学计算",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {"type": "string"}
            }
        }
    }
}
```

**使用示例**:
```python
import asyncio
from mcp_app.client import MCPClient

async def demo():
    client = MCPClient(
        server_path="./mcp_server/server.py",
        transport="stdio"
    )
    
    # 连接
    if await client.connect():
        print("✅ 连接成功")
        
        # 发现工具
        tools = await client.discover_tools()
        for tool in tools:
            print(f"工具: {tool['function']['name']}")
        
        # 调用天气工具
        result = await client.call_tool(
            "get_weather",
            {"city": "北京", "unit": "celsius"}
        )
        print(f"天气: {result}")
        
        # 关闭
        await client.close()

asyncio.run(demo())
```

---

### 4. llm.py - LLM 接口模块

**作用**: 封装 Moonshot AI (Kimi) API，处理对话和工具调用

**关键类**:
- `LLMClient`: LLM 客户端主类

**Import 方式**:
```python
from mcp_app.llm import LLMClient

# 创建客户端
llm = LLMClient(
    api_key="your-api-key",
    base_url="https://api.moonshot.cn/v1",
    model="kimi-k2-0905-preview",
    temperature=0.7,
    max_tokens=4096
)

# 添加系统提示词
llm.add_system_message("你是一个助手...")

# 添加用户消息
llm.add_user_message("你好")

# 发送请求（普通模式）
response = llm.chat()
print(response)

# 发送请求（带工具）
from mcp_app.client import MCPClient

client = MCPClient(...)
tools = await client.discover_tools()

def tool_executor(name, args):
    # 同步执行工具
    import asyncio
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(client.call_tool(name, args))

response = llm.chat(tools=tools, tool_executor=tool_executor)
print(response)
```

**方法说明**:

| 方法 | 参数 | 说明 |
|------|------|------|
| `__init__` | `api_key`, `base_url`, `model`, `temperature`, `max_tokens` | 初始化 |
| `add_system_message(content)` | 内容 | 添加系统消息 |
| `add_user_message(content)` | 内容 | 添加用户消息 |
| `add_assistant_message(content)` | 内容 | 添加助手消息 |
| `add_tool_result(tool_call_id, content)` | ID, 内容 | 添加工具结果 |
| `clear_history(keep_system=True)` | 是否保留系统消息 | 清空历史 |
| `get_history_length()` | - | 获取历史长度 |
| `chat(tools, tool_executor)` | 工具列表, 执行器 | 发送请求 |

**对话流程示例**:
```python
from mcp_app.llm import LLMClient

# 初始化
llm = LLMClient(
    api_key="sk-xxx",
    base_url="https://api.moonshot.cn/v1",
    model="kimi-k2-0905-preview"
)

# 设置系统提示
llm.add_system_message("你是一个数学助手")

# 第一轮对话
llm.add_user_message("1+1等于几？")
response = llm.chat()
print(response)  # AI: 1+1 等于 2

# 第二轮对话（AI 会自动使用上下文）
llm.add_user_message("再加3呢？")
response = llm.chat()
print(response)  # AI: 2+3 等于 5

# 查看历史
print(f"历史消息数: {llm.get_history_length()}")

# 清空历史（保留系统消息）
llm.clear_history()
```

**工具调用流程**:
```python
import asyncio
from mcp_app.llm import LLMClient
from mcp_app.client import MCPClient

async def chat_with_tools():
    # 初始化
    llm = LLMClient(api_key="sk-xxx", base_url="...", model="...")
    mcp = MCPClient(server_path="...", transport="stdio")
    
    # 连接 MCP
    await mcp.connect()
    tools = await mcp.discover_tools()
    
    # 定义工具执行器
    def execute_tool(name, args):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(mcp.call_tool(name, args))
    
    # 对话
    llm.add_system_message("你可以使用工具帮助用户")
    llm.add_user_message("北京今天天气怎么样？")
    
    # chat 会自动处理工具调用
    response = llm.chat(tools=tools, tool_executor=execute_tool)
    print(response)  # 北京今天晴，温度22°C...
    
    await mcp.close()

asyncio.run(chat_with_tools())
```

---

### 5. cli.py - 命令行界面模块

**作用**: 提供交互式命令行界面，处理用户输入和命令

**关键类**:
- `ChatCLI`: CLI 主类

**Import 方式**:
```python
from mcp_app.cli import ChatCLI
from mcp_app.config import load_config
from mcp_app.llm import LLMClient
from mcp_app.client import MCPClient

# 加载配置
config = load_config()

# 初始化组件
llm = LLMClient(...)
mcp = MCPClient(...)

# 创建 CLI
cli = ChatCLI(config, llm, mcp)

# 启动对话循环
cli.chat_loop()
```

**可用命令**:

| 命令 | 别名 | 说明 |
|------|------|------|
| `/help` | `/h`, `help` | 显示帮助 |
| `/clear` | `/c`, `clear` | 清空对话历史 |
| `/tools` | `/t`, `tools` | 显示工具列表 |
| `/status` | `/s`, `status` | 显示状态信息 |
| `/quit` | `/q`, `/exit`, `quit` | 退出程序 |

**内部流程**:
```python
# chat_loop() 伪代码
while running:
    user_input = input("👤 你: ")
    
    if user_input.startswith('/'):
        handle_command(user_input)  # 处理命令
    else:
        llm.add_user_message(user_input)
        response = llm.chat(tools=tools, tool_executor=executor)
        print(f"🤖 AI: {response}")
```

---

## MCP Server 说明

### server.py - MCP 服务器

**作用**: 提供工具服务，通过 MCP 协议与客户端通信

**依赖**:
```python
pip install fastmcp
```

**核心组件**:

| 组件 | 说明 | 示例 |
|------|------|------|
| `@mcp.tool()` | 装饰器，定义工具 | `@mcp.tool() async def calculate(...)` |
| `@mcp.resource()` | 装饰器，定义资源 | `@mcp.resource("config://app")` |
| `FastMCP` | 服务器类 | `mcp = FastMCP("名称")` |

**现有工具**:

```python
# 1. calculate - 数学计算
@mcp.tool()
async def calculate(params: CalcInput, ctx: Context) -> str:
    """执行数学计算"""
    # 支持: sqrt, pow, abs, round, max, min, pi, e
    # 示例: "sqrt(16) + pow(2, 3)" → "12.00"

# 2. get_weather - 获取天气（模拟）
@mcp.tool()
async def get_weather(params: WeatherInput, ctx: Context) -> str:
    """获取天气"""
    # 支持城市: 北京, 上海, 广州
    # 支持单位: celsius, fahrenheit

# 3. analyze_code - 代码分析
@mcp.tool()
async def analyze_code(params: CodeInput, ctx: Context) -> str:
    """分析代码统计信息"""
    # 返回: 总行数, 非空行数

# 4. smart_search - 知识搜索（模拟）
@mcp.tool()
async def smart_search(params: SearchInput, ctx: Context) -> str:
    """搜索知识库"""
    # 关键词: mcp, kimi, fastmcp
```

**运行 Server**:

```bash
# stdio 模式（默认）
python mcp_server/server.py

# SSE 模式
python mcp_server/server.py --transport sse --port 8000
```

**添加新工具示例**:

```python
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("MyServer")

# 1. 定义输入模型
class TranslateInput(BaseModel):
    text: str = Field(..., description="要翻译的文本")
    target_lang: str = Field(default="en", description="目标语言")

# 2. 定义工具
@mcp.tool()
async def translate(params: TranslateInput, ctx: Context) -> str:
    """翻译文本"""
    # 实现翻译逻辑
    return f"翻译结果: {params.text}"

# 3. 运行
if __name__ == "__main__":
    mcp.run(transport='stdio')
```

---

## 运行流程

### 启动流程图

```
┌──────────┐
│  run.py  │
└────┬─────┘
     │ 1. 解析命令行参数
     ▼
┌──────────────┐
│  load_config │ ◄── 从 .env 加载配置
└────┬─────────┘
     │ 2. 配置日志
     ▼
┌──────────────┐
│setup_logging │ ◄── 初始化 logger
└────┬─────────┘
     │ 3. 初始化 MCP Client
     ▼
┌──────────────┐
│ MCPClient()  │
└────┬─────────┘
     │ 4. 连接 Server
     ▼
┌──────────────┐
│   connect    │ ◄── stdio/sse 连接
└────┬─────────┘
     │ 5. 发现工具
     ▼
┌──────────────┐
│discover_tools│ ◄── 获取可用工具列表
└────┬─────────┘
     │ 6. 初始化 LLM
     ▼
┌──────────────┐
│ LLMClient()  │
└────┬─────────┘
     │ 7. 启动 CLI
     ▼
┌──────────────┐
│  chat_loop   │ ◄── 交互循环
└──────────────┘
```

### 对话流程图

```
用户输入
    │
    ▼
是否命令？ ──是──► 执行命令 ──► 等待输入
    │否
    ▼
add_user_message()
    │
    ▼
llm.chat(tools, executor)
    │
    ▼
调用 Kimi API
    │
    ▼
是否需要工具？ ──否──► 直接返回结果 ──► 显示给用户
    │是
    ▼
调用 tool_executor
    │
    ▼
client.call_tool()
    │
    ▼
执行 MCP Server 工具
    │
    ▼
返回工具结果
    │
    ▼
add_tool_result()
    │
    ▼
再次调用 Kimi API
    │
    ▼
生成最终回复 ──► 显示给用户
    │
    ▼
等待下一条输入
```

---

## 配置指南

### 最小配置 (.env)

```bash
# 唯一必填项
MOONSHOT_API_KEY=sk-your-actual-api-key-here
```

### 完整配置 (.env)

```bash
# ========== API Keys ==========
MOONSHOT_API_KEY=sk-your-actual-api-key-here

# ========== MCP Server ==========
MCP_SERVER_PATH=C:/Users/xxx/project/mcp_server/server.py
MCP_TRANSPORT=stdio
MCP_PORT=8000

# ========== LLM 配置 ==========
LLM_MODEL=kimi-k2-0905-preview
LLM_BASE_URL=https://api.moonshot.cn/v1
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=4096

# ========== 日志配置 ==========
LOG_LEVEL=INFO
LOG_TO_FILE=true

# ========== 开发配置 ==========
DEBUG=false
```

### 命令行参数

```bash
# 基本用法
python run.py

# 调试模式（详细日志）
python run.py --log-level DEBUG

# 仅控制台日志（不写入文件）
python run.py --no-file-log

# 组合使用
python run.py --log-level DEBUG --no-file-log
```

---

## 扩展开发

### 添加新的 LLM 提供商

```python
# llm.py 中添加新类
class OpenAIClient:
    def __init__(self, api_key, model="gpt-4"):
        self.client = OpenAI(api_key=api_key)
        self.model = model
    
    def chat(self, messages, tools=None):
        # 实现 OpenAI 调用
        pass

# config.py 中添加配置
llm_provider: str = "moonshot"  # 或 openai
openai_api_key: str = ""

# run.py 中根据配置初始化
if config.llm_provider == "openai":
    llm = OpenAIClient(...)
else:
    llm = LLMClient(...)
```

### 添加新的 MCP 工具

```python
# mcp_server/server.py

class MyInput(BaseModel):
    data: str = Field(...)

@mcp.tool()
async def my_tool(params: MyInput, ctx: Context) -> str:
    """我的工具描述"""
    result = process(params.data)
    return f"结果: {result}"
```

### 添加新的 CLI 命令

```python
# cli.py 中的 handle_command 方法

def handle_command(self, command: str) -> bool:
    cmd = command.lower().strip()
    
    # 添加新命令
    if cmd in ['/mycommand', '/m']:
        self.do_something()
        return True
    
    # ... 原有命令

# 添加新方法
def do_something(self):
    """执行自定义操作"""
    logger.info("执行自定义命令")
    print("自定义命令执行成功！")
```

---

## 依赖列表

### 必需依赖

```
mcp>=1.0.0          # MCP 协议实现
fastmcp>=1.0.0      # FastMCP 框架
openai>=1.55.0      # OpenAI SDK（用于 Kimi）
python-dotenv>=1.0.0 # 环境变量加载
pydantic>=2.9.0     # 数据验证
```

### 可选依赖

```
pyyaml>=6.0         # YAML 配置支持
```

### 开发依赖

```
pytest>=8.0.0       # 测试框架
pytest-asyncio      # 异步测试
```

---

## 常见问题

### Q: 如何获取 Moonshot API Key？
A: 访问 https://platform.moonshot.cn/ 注册并创建 API Key

### Q: 日志文件在哪里？
A: `logs/mcp_app_YYYYMMDD.log`

### Q: 如何禁用日志颜色？
A: 修改 `logger.py` 中的 `use_colors=False`

### Q: 支持哪些传输模式？
A: `stdio`（本地子进程）和 `sse`（HTTP 流）

### Q: 如何添加更多工具？
A: 在 `mcp_server/server.py` 中使用 `@mcp.tool()` 装饰器添加

---

## 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.0.0 | 2026-03-14 | 初始版本，基本功能完成 |

---

**文档结束**

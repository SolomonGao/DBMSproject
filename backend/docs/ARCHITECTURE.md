# GDELT Narrative API - 架构文档

> 版本: 1.0.0  
> 更新日期: 2026-03-13  
> 作者: VT Research Team

---

## 1. 项目概述

### 1.1 项目简介

GDELT Narrative API 是一个基于 **MCP (Model Context Protocol)** 架构的时空叙事 AI 系统，用于分析北美地区的 GDELT 2.0 事件数据。

**核心能力**：
- 通过自然语言查询 GDELT 数据库
- AI 自动发现目标事件的前因后果
- 生成时空叙事分析报告
- RESTful API 接口

### 1.2 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| Web 框架 | FastAPI | 0.115+ |
| 数据库 | MySQL 8.0 + SQLAlchemy 2.0 | async |
| AI 模型 | Moonshot AI (Kimi) | k2-0905-preview |
| 协议 | Model Context Protocol | 1.0+ |
| 日志 | structlog | 24.4+ |
| 配置 | Pydantic Settings | 2.6+ |

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        客户端 (Frontend)                         │
│                   (index.html / Web / Mobile)                    │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP/JSON
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Application                         │
│                    (backend/src/gdelt_api/)                      │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌──────────────────┐  ┌─────────────────┐ │
│  │   API Layer     │  │  Service Layer   │  │  Data Layer     │ │
│  │   (api/)        │→ │  (services/)     │→ │  (db/)          │ │
│  │                 │  │                  │  │                 │ │
│  │ • 路由定义       │  │ • 业务逻辑        │  │ • 数据库连接     │ │
│  │ • 输入验证       │  │ • 流程编排        │  │ • 查询构建      │ │
│  │ • 依赖注入       │  │ • 外部调用        │  │ • ORM 模型      │ │
│  │ • 异常处理       │  │ • 事务管理        │  │ • 连接池        │ │
│  └─────────────────┘  └──────────────────┘  └─────────────────┘ │
│           ↓                     ↓                    ↓          │
│  ┌─────────────────┐  ┌──────────────────┐  ┌─────────────────┐ │
│  │   MCP Layer     │  │   Core Layer     │  │   Model Layer   │ │
│  │   (mcp/)        │  │   (core/)        │  │   (models/)     │ │
│  │                 │  │                  │  │                 │ │
│  │ • MCP Client    │  │ • 异常定义        │  │ • Pydantic      │ │
│  │ • 连接池        │  │ • 结构化日志      │  │ • 数据验证      │ │
│  │ • 工具调用      │  │ • 事件总线        │  │ • 序列化       │ │
│  └─────────────────┘  └──────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                               │
                               │ stdio/subprocess
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                       MCP Server                                 │
│                     (mcp_server/)                                │
│                                                                  │
│  • 暴露数据库查询工具 (Text2SQL)                                  │
│  • 暴露数据分析工具                                              │
│  • 通过 stdio 与主应用通信                                       │
└──────────────────────────────┬──────────────────────────────────┘
                               │ SQL
                               ▼
                      ┌─────────────────┐
                      │   MySQL 8.0     │
                      │   (gdelt_db)    │
                      │                 │
                      │ • events_table  │
                      │ • Spatial Index │
                      └─────────────────┘
```

### 2.2 组件关系图

```
HTTP Request
    │
    ▼
┌──────────────┐
│  Middleware  │ (CORS, GZip, Logging)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│    Router    │ (api/v1/endpoints/)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Dependencies │ (注入 Service, DB Session)
└──────┬───────┘
       │
       ▼
┌──────────────┐    ┌──────────────┐
│   Service    │←──→│   LLM Service│
│   (业务)      │    │  (Kimi API)  │
└──────┬───────┘    └──────────────┘
       │
       ├────────────┐
       │            │
       ▼            ▼
┌──────────┐  ┌──────────┐
│  DB Repo │  │ MCP Client│
└────┬─────┘  └─────┬────┘
     │              │
     ▼              ▼
┌─────────┐    ┌──────────┐
│  MySQL  │    │ MCP Server│
└─────────┘    └─────┬────┘
                     │
                     ▼
                ┌─────────┐
                │  MySQL  │
                └─────────┘
```

---

## 3. 目录结构详解

```
backend/
├── src/gdelt_api/                 # 主应用包
│   ├── __init__.py               # 包初始化
│   ├── main.py                   # FastAPI 入口 + 生命周期管理
│   │
│   ├── api/                      # API 层
│   │   ├── __init__.py
│   │   ├── dependencies.py       # FastAPI 依赖注入定义
│   │   ├── errors.py             # 全局异常处理器
│   │   └── v1/                   # API 版本 1
│   │       ├── __init__.py       # 路由聚合
│   │       └── endpoints/        # 具体端点实现
│   │           ├── __init__.py
│   │           ├── health.py     # 健康检查
│   │           ├── chat.py       # 聊天接口
│   │           └── events.py     # 事件查询接口
│   │
│   ├── config/                   # 配置管理
│   │   ├── __init__.py
│   │   └── settings.py           # Pydantic Settings 配置类
│   │
│   ├── core/                     # 核心基础设施
│   │   ├── __init__.py
│   │   ├── exceptions.py         # 自定义异常类
│   │   ├── logging.py            # 结构化日志配置
│   │   └── events.py             # 异步事件总线
│   │
│   ├── db/                       # 数据访问层
│   │   ├── __init__.py
│   │   ├── base.py               # SQLAlchemy Base 定义
│   │   └── session.py            # 异步会话 + 连接池管理
│   │
│   ├── mcp/                      # MCP 集成层
│   │   ├── __init__.py
│   │   ├── client.py             # MCP 客户端实现
│   │   └── pool.py               # MCP 连接池
│   │
│   ├── models/                   # 数据模型层
│   │   ├── __init__.py
│   │   ├── chat.py               # 聊天相关模型
│   │   ├── event.py              # 事件相关模型
│   │   └── common.py             # 通用响应模型
│   │
│   ├── services/                 # 业务逻辑层
│   │   ├── __init__.py
│   │   ├── chat_service.py       # 聊天业务流程
│   │   ├── event_service.py      # 事件查询服务
│   │   └── llm_service.py        # LLM API 封装
│   │
│   └── utils/                    # 工具函数
│       ├── __init__.py
│       ├── datetime.py           # 日期时间处理
│       └── security.py           # 安全相关工具
│
├── tests/                        # 测试套件
│   ├── __init__.py
│   ├── conftest.py               # pytest 配置 + fixtures
│   ├── unit/                     # 单元测试
│   ├── integration/              # 集成测试
│   └── e2e/                      # 端到端测试
│
├── alembic/                      # 数据库迁移
│   ├── versions/                 # 迁移脚本
│   ├── env.py                    # Alembic 环境配置
│   └── script.py.mako            # 迁移模板
│
├── docs/                         # 文档
│   └── ARCHITECTURE.md           # 本文档
│
├── Dockerfile                    # 容器镜像定义
└── scripts/                      # 脚本工具
```

---

## 4. 各层详细说明

### 4.1 配置层 (config/)

**文件**: `settings.py`

**职责**: 集中管理所有配置，支持环境变量覆盖

**核心类**:

```python
class Settings(BaseSettings):
    env: Literal["development", "testing", "production"]
    debug: bool
    database: DatabaseSettings      # 嵌套配置
    llm: LLMSettings               # LLM 配置
    mcp: MCPSettings               # MCP 配置
```

**设计要点**:
- 使用 `pydantic-settings` 自动读取 `.env` 文件
- 类型安全：所有配置项都有类型注解
- 环境隔离：开发/测试/生产配置分离
- 敏感信息保护：密码等从环境变量读取

**使用方式**:

```python
from gdelt_api.config import get_settings

settings = get_settings()
db_url = settings.database.async_url
```

---

### 4.2 核心层 (core/)

#### 4.2.1 异常处理 (exceptions.py)

**职责**: 定义统一的异常体系，确保 API 返回格式一致

**异常层次**:

```
GDELTAPIError (基类)
├── NotFoundError          (404)
├── ValidationError        (422)
├── AuthenticationError    (401)
├── AuthorizationError     (403)
├── ConflictError          (409)
├── RateLimitError         (429)
├── LLMError              (502)
├── MCPError              (502)
└── DatabaseError         (503)
```

**使用示例**:

```python
from gdelt_api.core.exceptions import NotFoundError

if not event:
    raise NotFoundError(f"Event {id} not found")
# 自动返回:
# {"success": false, "error": {"code": "NOT_FOUND", "message": "...", "status": 404}}
```

#### 4.2.2 结构化日志 (logging.py)

**职责**: 统一日志格式，支持开发和生产两种模式

**开发模式** (Console):
```
2024-03-13T17:30:00 [INFO] chat_request message_count=3
```

**生产模式** (JSON):
```json
{"timestamp": "2024-03-13T17:30:00", "level": "INFO", "event": "chat_request", "message_count": 3}
```

**使用方式**:

```python
from gdelt_api.core.logging import get_logger

logger = get_logger(__name__)
logger.info("event_created", event_id=123, user_id=456)
```

#### 4.2.3 事件总线 (events.py)

**职责**: 组件间解耦通信，发布-订阅模式

**使用场景**:
- 应用启动/关闭事件
- 数据变更通知
- 异步任务触发

---

### 4.3 模型层 (models/)

#### 4.3.1 设计原则

**分层模型**:

| 类型 | 用途 | 示例 |
|------|------|------|
| Request Model | 验证请求数据 | `ChatRequest` |
| Response Model | 序列化响应数据 | `ChatResponse` |
| Query Model | 查询参数 | `EventQuery` |
| Domain Model | 领域对象 | `GDELTEvent` |

#### 4.3.2 Pydantic 模型示例

```python
class ChatRequest(BaseModel):
    messages: List[Message] = Field(min_length=1)
    temperature: float | None = Field(None, ge=0, le=2)
    
    @field_validator("messages")
    def must_have_user_message(cls, v):
        if not any(m.role == "user" for m in v):
            raise ValueError("Must have at least one user message")
        return v
```

**特性**:
- 自动数据验证
- 类型转换
- 自定义验证器
- OpenAPI 文档自动生成

---

### 4.4 数据层 (db/)

#### 4.4.1 数据库会话管理 (session.py)

**架构决策**: 异步 SQLAlchemy + 连接池

```python
# 连接池配置
engine = create_async_engine(
    url,
    pool_size=10,        # 基础连接数
    max_overflow=20,     # 额外连接数
    pool_timeout=30,     # 获取连接超时
    pool_recycle=3600,   # 连接回收时间
)
```

**两种会话模式**:

1. **上下文管理器** (Service 层使用):
```python
async with get_db() as session:
    result = await session.execute(query)
    # 自动 commit/rollback
```

2. **FastAPI 依赖注入** (Router 层使用):
```python
async def endpoint(session: AsyncSession = Depends(get_session)):
    # FastAPI 自动管理生命周期
```

#### 4.4.2 ORM 基础 (base.py)

```python
class Base(DeclarativeBase):
    # 统一命名规范
    metadata = MetaData(naming_convention={...})
    
    # 通用字段
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

---

### 4.5 MCP 层 (mcp/)

#### 4.5.1 什么是 MCP?

Model Context Protocol - 让 LLM 安全调用外部工具的标准协议。

**工作流程**:
```
1. 后端启动时连接 MCP Server (stdio 方式)
2. 获取可用工具列表 (如 query_database, calculate)
3. LLM 请求时传入工具定义
4. LLM 决定调用工具 → 后端通过 MCP Client 执行
5. 返回结果给 LLM 生成最终回复
```

#### 4.5.2 MCPClient (client.py)

**职责**:
- 管理 MCP Server 子进程生命周期
- 工具调用封装
- 错误处理

**关键方法**:

```python
async def connect(self, server_script: str):
    """启动 MCP Server 并建立连接"""
    
async def call_tool(self, name: str, arguments: dict) -> str:
    """调用远程工具"""
    
def get_openai_tools(self) -> list[dict]:
    """转换为 OpenAI 格式供 LLM 使用"""
```

#### 4.5.3 连接池 (pool.py)

**为什么需要池？**

- 每个 MCP 连接 = 一个 Python 子进程
- 进程创建/销毁开销大 (~100ms)
- 池化复用提高并发性能

---

### 4.6 服务层 (services/)

**设计模式**: 贫血领域模型 + 事务脚本

#### 4.6.1 ChatService (chat_service.py)

**职责**: 编排完整的聊天业务流程

**流程图**:
```
用户消息 → LLM (带工具) 
              ↓
        需要工具？──否──→ 直接返回
              ↓是
        执行 MCP 工具
              ↓
        结果 + 历史 → LLM
              ↓
        生成最终回复
```

**代码结构**:

```python
class ChatService:
    def __init__(self, settings, mcp_client):
        self.llm = LLMService(settings)
        self.mcp = mcp_client
    
    async def chat(self, request: ChatRequest) -> ChatResponse:
        # 1. 准备消息
        messages = self._prepare_messages(request)
        
        # 2. 首次 LLM 调用
        response = await self.llm.chat(messages, tools)
        
        # 3. 处理工具调用
        if response.tool_calls:
            results = await self._execute_tools(response.tool_calls)
            # 4. 二次 LLM 调用
            final = await self.llm.chat(messages + results)
        
        return ChatResponse(...)
```

#### 4.6.2 EventService (event_service.py)

**职责**: 事件数据查询逻辑

**功能**:
- 多条件筛选 (时间、地点、演员、事件类型)
- 地理位置查询
- 分页和排序
- 关联事件查询 (前因分析)

#### 4.6.3 LLMService (llm_service.py)

**职责**: 封装 Kimi API 调用

**特性**:
- 自动重试 (tenacity)
- 错误转换 (外部异常 → LLMError)
- 工具格式转换
- Token 用量追踪

---

### 4.7 API 层 (api/)

#### 4.7.1 依赖注入 (dependencies.py)

**FastAPI 依赖注入示例**:

```python
async def get_chat_service(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> ChatService:
    mcp_client = request.app.state.mcp_client
    return ChatService(settings, mcp_client)
```

**使用**:

```python
@router.post("/chat")
async def chat(
    request: ChatRequest,
    service: ChatService = Depends(get_chat_service)  # 自动注入
):
    return await service.chat(request)
```

**好处**:
- 解耦：路由不需要知道服务如何创建
- 可测试：容易替换为 Mock
- 生命周期管理：FastAPI 自动处理

#### 4.7.2 异常处理 (errors.py)

注册全局处理器，将异常转换为标准响应格式。

#### 4.7.3 路由 (v1/endpoints/)

**设计规范**:
- 每个资源一个文件
- 使用 APIRouter
- 声明 response_model
- 自动文档生成

**示例**:

```python
@router.get(
    "/events",
    response_model=APIResponse[PaginatedResponse[GDELTEvent]],
    summary="Search events",
    description="Search GDELT events with filters"
)
async def search_events(
    query: EventQuery = Depends(),  # 自动解析 Query Params
    service: EventService = Depends(get_event_service)
):
    events, total = await service.search_events(query)
    return APIResponse(success=True, data=...)
```

---

## 5. 请求生命周期

### 5.1 完整请求流程

以 **"查询华盛顿事件并生成叙事"** 为例：

```
┌──────────┐
│  客户端   │
└────┬─────┘
     │ POST /api/v1/chat
     │ {"messages": [{"role": "user", "content": "华盛顿发生了什么？"}]}
     ▼
┌──────────────────────────────────────────────┐
│  1. FastAPI 接收请求                          │
│     - CORS 检查                                │
│     - 路由匹配 (/api/v1/chat)                  │
│     - JSON 解析 → ChatRequest                  │
│     - Pydantic 验证                            │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────┐
│  2. 依赖注入                                  │
│     - get_settings() → Settings              │
│     - get_mcp_client() → MCPClient           │
│     - get_chat_service() → ChatService       │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────┐
│  3. ChatService.chat()                        │
│     a. 构建消息历史                           │
│     b. 获取可用工具 (MCPClient.get_openai_tools)
│        → [{"type": "function", "function": {...}}]
└──────────────────┬───────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────┐
│  4. LLMService.chat() (第一次)                │
│     - 调用 Kimi API                           │
│     - 传入 messages + tools                   │
│     - LLM 决定调用 "query_events" 工具        │
│     ← ToolCall(id="call_1", name="query_events")
└──────────────────┬───────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────┐
│  5. MCPClient.call_tool()                     │
│     - 序列化参数                               │
│     - 通过 stdio 发送给 MCP Server            │
│     - MCP Server 执行 SQL 查询                 │
│     ← 事件列表 (JSON)                          │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────┐
│  6. LLMService.chat() (第二次)                │
│     - 将工具结果加入 messages                 │
│     - 再次调用 Kimi                           │
│     - 生成自然语言回复                        │
│     ← "华盛顿昨日发生了抗议活动..."            │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────┐
│  7. 构建响应                                  │
│     - ChatResponse 序列化                     │
│     - APIResponse 包装                        │
│     ← {"success": true, "data": {...}}        │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
┌──────────┐
│  客户端   │ ← {"reply": "华盛顿昨日...", "messages": [...]}
└──────────┘
```

---

## 6. 配置管理

### 6.1 环境变量

**配置文件**: `.env`

```bash
# 数据库 (必需)
DB_PASSWORD=your_mysql_password
DB_HOST=localhost
DB_PORT=3306
DB_NAME=gdelt_db

# AI (必需)
API_KEY=sk-your-moonshot-api-key

# 应用 (可选，有默认值)
DEBUG=false                      # true: 开启文档和调试日志
ENV=development                  # development/testing/production
LOG_LEVEL=INFO                   # DEBUG/INFO/WARNING/ERROR
LOG_FORMAT=json                  # json/console

# MCP (可选)
MCP_SERVER_SCRIPT=mcp_server/server.py
MCP_TIMEOUT=30

# 服务器 (可选)
HOST=0.0.0.0
PORT=8000
```

### 6.2 多环境支持

```python
# development: 本地开发，详细日志，开启文档
# testing: 测试环境，内存数据库
# production: 生产环境，JSON日志，禁用文档
```

---

## 7. 开发指南

### 7.1 添加新 API 端点

**步骤**:

1. **定义模型** (`models/`):
```python
class MyRequest(BaseModel):
    field: str
```

2. **实现服务** (`services/`):
```python
class MyService:
    async def process(self, request): ...
```

3. **添加依赖** (`api/dependencies.py`):
```python
async def get_my_service(...) -> MyService: ...
```

4. **创建路由** (`api/v1/endpoints/my.py`):
```python
@router.post("", response_model=APIResponse[...])
async def my_endpoint(service: MyService = Depends(...)): ...
```

5. **注册路由** (`api/v1/__init__.py`):
```python
api_router.include_router(my.router, prefix="/my")
```

### 7.2 添加 MCP 工具

在 `mcp_server/server.py` 中添加：

```python
@mcp.tool()
def my_new_tool(param: str) -> str:
    """工具描述"""
    return result
```

重启后端自动加载。

### 7.3 测试

**单元测试**:
```python
async def test_chat_service(mock_llm, mock_mcp):
    service = ChatService(mock_llm, mock_mcp)
    result = await service.chat(request)
    assert result.reply
```

**集成测试**:
```python
async def test_chat_endpoint(client):
    response = await client.post("/api/v1/chat", json={...})
    assert response.status_code == 200
```

---

## 8. 性能优化

### 8.1 数据库

- 连接池复用连接
- 使用异步查询避免阻塞
- 添加适当索引

### 8.2 MCP

- 连接池避免频繁创建进程
- 工具调用批量处理

### 8.3 缓存

（可扩展）添加 Redis 缓存：
```python
@cache(expire=300)
async def get_event(event_id: int): ...
```

---

## 9. 监控与日志

### 9.1 关键指标

- 请求延迟 (P50, P95, P99)
- 错误率
- LLM Token 使用量
- MCP 工具调用次数

### 9.2 日志格式

**开发**:
```
2024-03-13T17:30:00 [INFO] chat_request message_count=3 user_id=123
```

**生产**:
```json
{
  "timestamp": "2024-03-13T17:30:00Z",
  "level": "INFO",
  "event": "chat_request",
  "message_count": 3,
  "user_id": 123,
  "request_id": "uuid"
}
```

---

## 10. 安全考虑

### 10.1 数据验证

所有输入都通过 Pydantic 验证。

### 10.2 敏感信息

- API Key 存储在环境变量
- 日志中隐藏密码
- 数据库连接使用 SSL (生产)

### 10.3 CORS

配置允许的域名，不使用 `*` 生产环境。

---

## 11. 部署

### 11.1 Docker

```bash
docker-compose up -d
```

### 11.2 手动部署

```bash
pip install -e "."
python -m gdelt_api.main
```

---

## 12. 故障排查

### 12.1 启动失败

- 检查 `.env` 配置
- 确认 MySQL 可连接
- 查看日志 `LOG_LEVEL=DEBUG`

### 12.2 MCP 连接失败

- 检查 `mcp_server/server.py` 路径
- 确认 MCP 依赖已安装

### 12.3 LLM 调用失败

- 检查 `API_KEY` 是否有效
- 查看 LLM 服务状态

---

## 附录：名词解释

| 术语 | 说明 |
|------|------|
| MCP | Model Context Protocol，模型上下文协议 |
| GDELT | Global Database of Events, Language, and Tone |
| CAMEO | Conflict and Mediation Event Observations (事件编码体系) |
| Pydantic | Python 数据验证库 |
| SQLAlchemy | Python ORM 框架 |
| FastAPI | 现代 Python Web 框架 |
| stdio | 标准输入输出 (MCP 通信方式) |

---

**文档维护**: 如有架构变更，请同步更新本文档。
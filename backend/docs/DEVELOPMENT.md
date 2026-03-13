# GDELT API - 开发指南

快速上手指南：如何在这个架构中添加功能、调试和测试。

---

## 目录

1. [环境搭建](#1-环境搭建)
2. [项目结构速查](#2-项目结构速查)
3. [添加新功能](#3-添加新功能)
4. [调试技巧](#4-调试技巧)
5. [测试指南](#5-测试指南)
6. [常见问题](#6-常见问题)

---

## 1. 环境搭建

### 1.1 快速开始

```bash
# 1. 进入项目目录
cd C:\Users\73823\Desktop\DBM\project

# 2. 安装依赖
pip install -e "."

# 3. 配置环境变量
copy .env_example .env
# 编辑 .env，填入你的 DB_PASSWORD 和 API_KEY

# 4. 运行
make run-dev
# 或手动
cd backend
set PYTHONPATH=.\src
python -m uvicorn gdelt_api.main:app --reload
```

### 1.2 验证安装

访问：
- http://localhost:8000/docs - API 文档
- http://localhost:8000/api/v1/health - 健康检查

---

## 2. 项目结构速查

**添加功能时修改的文件**：

| 功能类型 | 修改位置 | 示例 |
|---------|---------|------|
| 新 API 接口 | `api/v1/endpoints/*.py` | `events.py` |
| 业务逻辑 | `services/*.py` | `chat_service.py` |
| 数据模型 | `models/*.py` | `chat.py` |
| 数据库相关 | `db/*.py` | `session.py` |
| 工具/辅助 | `utils/*.py` | `datetime.py` |
| 配置 | `config/settings.py` | 新增配置项 |

---

## 3. 添加新功能

### 3.1 场景：添加新 API 端点

**示例**：添加 `/api/v1/statistics` 返回事件统计

#### 步骤 1：定义模型

创建 `backend/src/gdelt_api/models/statistics.py`：

```python
from pydantic import BaseModel, Field

class EventStatistics(BaseModel):
    total_events: int = Field(..., description="Total event count")
    unique_actors: int = Field(..., description="Unique actor count")
    avg_tone: float = Field(..., description="Average tone")
    
class StatisticsQuery(BaseModel):
    start_date: str | None = Field(None, description="Start date (YYYY-MM-DD)")
    end_date: str | None = Field(None, description="End date (YYYY-MM-DD)")
```

在 `models/__init__.py` 导出：
```python
from .statistics import EventStatistics, StatisticsQuery
```

#### 步骤 2：实现服务

修改 `services/event_service.py`，添加方法：

```python
async def get_statistics(self, query: StatisticsQuery) -> EventStatistics:
    """Get event statistics."""
    # 构建查询
    sql = select(
        func.count().label("total"),
        func.count(distinct(Event.actor1_name)).label("actors"),
        func.avg(Event.avg_tone).label("tone")
    )
    
    if query.start_date:
        sql = sql.where(Event.event_date >= query.start_date)
    if query.end_date:
        sql = sql.where(Event.event_date <= query.end_date)
    
    result = await self.session.execute(sql)
    row = result.one()
    
    return EventStatistics(
        total_events=row.total,
        unique_actors=row.actors,
        avg_tone=round(row.tone or 0, 2)
    )
```

#### 步骤 3：创建路由

创建 `api/v1/endpoints/statistics.py`：

```python
from fastapi import APIRouter, Depends

from gdelt_api.api.dependencies import get_event_service
from gdelt_api.models.common import APIResponse
from gdelt_api.models.statistics import EventStatistics, StatisticsQuery
from gdelt_api.services import EventService

router = APIRouter()

@router.get(
    "",
    response_model=APIResponse[EventStatistics],
    summary="Get event statistics",
)
async def get_statistics(
    query: StatisticsQuery = Depends(),
    service: EventService = Depends(get_event_service),
):
    """Get statistics about events in the database."""
    stats = await service.get_statistics(query)
    return APIResponse(success=True, data=stats)
```

#### 步骤 4：注册路由

修改 `api/v1/__init__.py`：

```python
from gdelt_api.api.v1.endpoints import chat, events, health, statistics

api_router.include_router(statistics.router, prefix="/statistics", tags=["statistics"])
```

#### 步骤 5：测试

```bash
curl "http://localhost:8000/api/v1/statistics?start_date=2024-01-01"
```

---

### 3.2 场景：添加 MCP 工具

MCP 工具让 AI 能够执行特定功能。

**示例**：添加天气查询工具（模拟）

修改 `mcp_server/server.py`：

```python
@mcp.tool()
def get_weather(city: str, date: str | None = None) -> str:
    """
    Get weather information for a city.
    
    Args:
        city: City name (e.g., "Washington", "New York")
        date: Date in YYYY-MM-DD format (optional, defaults to today)
    
    Returns:
        Weather description
    """
    # 模拟天气数据
    weather_data = {
        "Washington": "Sunny, 22°C",
        "New York": "Cloudy, 18°C",
        "Los Angeles": "Clear, 25°C"
    }
    
    weather = weather_data.get(city, "Unknown")
    date_str = date or "today"
    
    return f"Weather in {city} on {date_str}: {weather}"
```

**自动生效**：重启后端后，AI 就能调用这个工具了。

**测试**：
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"华盛顿今天天气怎么样？"}]}'
```

---

### 3.3 场景：修改配置

**示例**：添加新的 API 提供商

修改 `config/settings.py`：

```python
class LLMSettings(BaseSettings):
    api_key: str = Field(default="", alias="API_KEY")
    base_url: str = Field(default="...", alias="LLM_BASE_URL")
    model: str = Field(default="kimi-k2-0905-preview", alias="LLM_MODEL")
    # 新增
    timeout: int = Field(default=60, alias="LLM_TIMEOUT")
    max_retries: int = Field(default=3, alias="LLM_MAX_RETRIES")
```

在 `.env` 中添加：
```bash
LLM_TIMEOUT=60
LLM_MAX_RETRIES=3
```

使用：
```python
settings = get_settings()
timeout = settings.llm.timeout
```

---

## 4. 调试技巧

### 4.1 查看日志

**开发模式**（Console 格式）：
```bash
LOG_LEVEL=DEBUG make run-dev
```

输出示例：
```
2024-03-13T17:30:00 [DEBUG] mcp_request tool=query_events args={...}
2024-03-13T17:30:01 [INFO] llm_response tokens_used=150
```

**关键日志事件**：
- `application_starting` - 应用启动
- `mcp_connected` - MCP 连接成功
- `chat_request` - 收到聊天请求
- `tool_call_failed` - 工具调用失败

### 4.2 API 调试

**使用 Swagger UI**：
访问 http://localhost:8000/docs

**使用 curl**：
```bash
# 测试健康检查
curl http://localhost:8000/api/v1/health | python -m json.tool

# 测试聊天
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"test"}]}' \
  | python -m json.tool
```

### 4.3 数据库调试

**查看生成的 SQL**：
```python
# 在代码中添加
from sqlalchemy import echo
engine = create_async_engine(url, echo=True)  # 打印所有 SQL
```

或在 `settings.py` 设置：
```python
debug: bool = True  # 自动开启 SQL 日志
```

### 4.4 MCP 调试

检查 MCP 连接状态：
```bash
curl http://localhost:8000/api/v1/health/ready
```

查看可用工具：
```python
# 在代码中
mcp_client = request.app.state.mcp_client
print(mcp_client.get_openai_tools())
```

---

## 5. 测试指南

### 5.1 运行测试

```bash
# 所有测试
make test

# 仅单元测试
pytest -m unit

# 仅集成测试
pytest -m integration

# 带覆盖率
make test-coverage
```

### 5.2 编写单元测试

**测试 Service 层**：

创建 `tests/unit/test_chat_service.py`：

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

from gdelt_api.models.chat import ChatRequest, Message
from gdelt_api.services.chat_service import ChatService

@pytest.mark.unit
async def test_chat_without_tools():
    """Test chat when no tools are called."""
    # Arrange
    mock_settings = MagicMock()
    mock_mcp = MagicMock()
    mock_mcp.get_openai_tools.return_value = []
    
    service = ChatService(mock_settings, mock_mcp)
    
    # Mock LLM
    service.llm_service = AsyncMock()
    service.llm_service.chat.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(
            content="Hello",
            tool_calls=None
        ))]
    )
    
    request = ChatRequest(messages=[Message(role="user", content="Hi")])
    
    # Act
    result = await service.chat(request)
    
    # Assert
    assert result.reply == "Hello"
    assert len(result.tool_calls) == 0
```

### 5.3 编写集成测试

**测试 API 端点**：

创建 `tests/integration/test_chat.py`：

```python
import pytest
from httpx import AsyncClient

@pytest.mark.integration
async def test_chat_endpoint(client: AsyncClient):
    """Test chat endpoint."""
    response = await client.post(
        "/api/v1/chat",
        json={
            "messages": [{"role": "user", "content": "Hello"}]
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "data" in data
```

### 5.4 Mock 外部服务

**Mock LLM API**：

```python
from unittest.mock import patch

@patch("gdelt_api.services.llm_service.AsyncOpenAI")
async def test_with_mock_llm(mock_openai):
    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="Mocked"))]
    )
    mock_openai.return_value = mock_client
    
    # 测试代码...
```

---

## 6. 常见问题

### Q1: 修改代码后没有生效？

**检查**：
1. 是否启用了 `--reload`？
2. 是否修改了正确的文件？
3. 是否有语法错误？查看终端报错

### Q2: 导入错误 (ImportError)？

**解决**：
```bash
# 确保 PYTHONPATH 设置正确
cd backend
set PYTHONPATH=.\src

# 或安装为包
pip install -e "."
```

### Q3: MCP Server 连接失败？

**排查步骤**：
1. 检查 `mcp_server/server.py` 是否存在
2. 检查依赖是否安装：`pip install mcp fastmcp`
3. 查看日志中的错误信息
4. 手动测试 MCP Server：`python mcp_server/server.py`

### Q4: 数据库连接失败？

**检查**：
1. MySQL 是否运行？
2. `.env` 中的密码是否正确？
3. 数据库是否存在？

```bash
# 测试连接
mysql -u root -p -e "SELECT 1"
```

### Q5: 如何添加日志？

```python
from gdelt_api.core.logging import get_logger

logger = get_logger(__name__)

# 不同级别
logger.debug("debug_info", variable=value)
logger.info("operation_complete", result=result)
logger.warning("something_odd", detail=detail)
logger.error("operation_failed", error=str(e))
```

### Q6: 如何禁用某些功能？

**禁用 MCP**（用于测试）：
```python
# 修改 main.py 的 lifespan
# 注释掉 MCP 连接代码
```

**禁用数据库**：
```bash
# 使用内存数据库测试
DB_URL=sqlite+aiosqlite:///:memory:
```

---

## 7. 性能优化建议

### 7.1 数据库优化

```python
# 添加索引（在 migrations 中）
op.create_index("ix_events_date", "events", ["event_date"])
op.create_index("ix_events_country", "events", ["country_code"])
```

### 7.2 缓存

添加缓存装饰器（需要安装 redis）：

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def expensive_computation(param: str) -> str:
    return result
```

### 7.3 异步优化

```python
# 并行调用多个工具
import asyncio

results = await asyncio.gather(
    tool1(),
    tool2(),
    tool3(),
    return_exceptions=True
)
```

---

## 8. 部署检查清单

部署前确认：

- [ ] `.env` 中 `DEBUG=false`
- [ ] `.env` 中 `ENV=production`
- [ ] `LOG_FORMAT=json`
- [ ] API Key 有效且未泄露
- [ ] 数据库连接使用 SSL
- [ ] 防火墙开放正确端口
- [ ] 健康检查端点可访问
- [ ] 日志收集配置完成

---

**需要帮助？** 查看 ARCHITECTURE.md 了解详细架构设计。
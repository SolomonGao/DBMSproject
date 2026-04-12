# Router 部署指南 (Ollama + Qwen 2.5B)

## 架构

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐     ┌─────────────┐
│    User     │────▶│  Router (Qwen)   │────▶│    LLM      │────▶│ MCP Server  │
│   Input     │     │  - 输入清理      │     │  (Kimi)     │     │  (Tools)    │
└─────────────┘     │  - 意图识别      │     └─────────────┘     └─────────────┘
                    │  - 工具预选择    │
                    └──────────────────┘
                           │
                    ┌──────▼──────┐
                    │ 本地 Ollama │
                    │ qwen2.5:3b  │
                    └─────────────┘
```

## 快速部署

### 1. 安装 Ollama

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh

# 验证安装
ollama --version
```

### 2. 拉取 Qwen 2.5B 模型

```bash
ollama pull qwen2.5:3b

# 验证
ollama list
# 应该看到 qwen2.5:3b
```

### 3. 测试模型

```bash
ollama run qwen2.5:3b

# 测试输入
>>> 你好
你好！有什么可以帮助你的吗？

# 退出
/bye
```

### 4. 启动 MCP Client

```bash
cd "/Volumes/Mac Driver/capstone/DBMSproject"
docker-compose up -d

# 进入容器
docker exec -it gdelt_app bash

# 启动应用
python run_v1.py
```

## 功能说明

### Router 会自动处理：

| 功能 | 说明 | 输出 |
|------|------|------|
| 输入清理 | 去除空格、零宽字符、标准化 | 干净的用户输入 |
| 意图识别 | query/analysis/chat/command | 意图类型 + 置信度 |
| 工具预选择 | 建议可能需要的工具 | 工具列表 |
| 安全检查 | SQL 注入、敏感词检测 | 安全标记 |

### 意图类型：

- `query`: 数据查询（如"查 Virginia 的新闻"）
- `analysis`: 统计分析（如"统计冲突趋势"）
- `chat`: 闲聊（如"你好"、"谢谢"）
- `command`: 系统命令（如 `/clear`）
- `blocked`: 被安全拦截

## 使用方法

### 启动时

```
➜ 欢迎使用 GDELT MCP Client!
ℹ️  Router enabled (Qwen 2.5B)
```

### 使用命令

```
你: /router          # 切换 Router 开关
✅ Router 已关闭

你: /router
✅ Router 已开启

你: /status          # 查看状态
📊 当前状态
----------------------------------------
MCP Server: ✅ 已连接
可用工具: 14 个
对话历史: 5 条消息
日志级别: INFO
Router: ✅ 开启
----------------------------------------
```

### 对话示例

**数据查询：**
```
你: 查一下 Virginia 的新闻
ℹ️  [Router] 数据查询: ['query_by_actor', 'query_by_time_range']
🤖 AI: 我来帮您查询 Virginia 相关的新闻...
```

**数据分析：**
```
你: 统计 2024 年冲突趋势
ℹ️  [Router] 数据分析: ['get_dashboard', 'analyze_time_series']
🤖 AI: 我来为您分析 2024 年的冲突趋势...
```

**闲聊：**
```
你: 你好
ℹ️  [Router] 闲聊模式
🤖 AI: 你好！有什么可以帮助您的吗？
```

## 配置

### 修改 Router 模型

编辑 `mcp_app/cli.py`：

```python
self.router = OllamaRouter(
    base_url="http://localhost:11434",
    model="qwen2.5:3b"  # 可以换成其他模型
)
```

可选模型：
- `qwen2.5:3b` - 推荐，中文好，速度快
- `llama3.2:3b` - 英文场景
- `phi3:3.8b` - 微软模型

### 使用远程 Ollama

```python
# 如果有独立部署的 Ollama 服务器
self.router = OllamaRouter(
    base_url="http://192.168.1.100:11434",
    model="qwen2.5:3b"
)
```

## 性能

| 指标 | 数值 |
|------|------|
| 模型大小 | ~1.9GB (qwen2.5:3b) |
| 显存需求 | ~4GB |
| 首 Token 延迟 | ~50-100ms (M1 Mac) |
| 推理速度 | ~50 tokens/s |

## 故障排除

### Router 未初始化

```
⚠️ Router unavailable, using direct mode
```

**解决：**
```bash
# 检查 Ollama 是否运行
ollama list

# 检查模型是否存在
ollama pull qwen2.5:3b

# 重启 Ollama
ollama serve
```

### 模型响应慢

**可能原因：**
- CPU 运行（建议用 GPU）
- 内存不足（建议 8GB+）

**优化：**
```bash
# 使用量化版本（更小更快）
ollama pull qwen2.5:3b-q4_0
```

### 意图识别不准确

可以调整 `router.py` 中的提示词，或增加训练数据。

## 高级用法

### 跳过 LLM（直接查询）

可以在 Router 中实现简单查询直接执行：

```python
if router_decision.intent == "query" and router_decision.confidence > 0.9:
    # 直接执行工具，不走 LLM
    result = await execute_tool(router_decision.suggested_tools[0])
    print(result)
    continue
```

这样可以进一步降低成本和延迟。

## 总结

Router 层带来：
- ✅ **更低的成本** - 简单查询不走大模型
- ✅ **更快的响应** - 本地模型 100ms 内响应
- ✅ **更好的安全** - 输入过滤和检查
- ✅ **更智能的路由** - 预选择合适工具

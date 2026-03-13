# GDELT Narrative API - Backend

时空叙事 AI 系统的后端服务。

---

## 🚀 快速启动

### 1. 安装依赖

```bash
cd ..
pip install -e "."
```

### 2. 配置环境

```bash
copy ..\.env .\.env
# 编辑 .env，填入数据库密码和 API Key
```

### 3. 启动服务

```bash
# Windows
set PYTHONPATH=.\src
python -m uvicorn gdelt_api.main:app --reload

# 或使用 Makefile
make run-dev
```

### 4. 验证

访问 http://localhost:8000/docs 查看 API 文档。

---

## 📁 目录说明

```
src/gdelt_api/
├── api/            # REST API 路由
├── config/         # 配置管理
├── core/           # 日志、异常、事件
├── db/             # 数据库连接
├── mcp/            # MCP 客户端
├── models/         # 数据模型
├── services/       # 业务逻辑
└── utils/          # 工具函数
```

---

## 🧪 开发

```bash
# 运行测试
make test

# 代码检查
make lint

# 格式化
make format
```

---

## 📚 文档

- [架构设计](./docs/ARCHITECTURE.md) - 系统架构详解
- [开发指南](./docs/DEVELOPMENT.md) - 如何添加功能

---

## 🔧 配置

关键环境变量：

```bash
DB_PASSWORD=xxx        # MySQL 密码
API_KEY=sk-xxx         # Moonshot API Key
DEBUG=true             # 开发模式
LOG_LEVEL=INFO         # 日志级别
```

---

## 📞 接口

### 健康检查
```bash
curl http://localhost:8000/api/v1/health
```

### 聊天
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hello"}]}'
```

### 事件查询
```bash
curl "http://localhost:8000/api/v1/events?country_code=US&page=1"
```

---

## 🐳 Docker

```bash
docker-compose up -d
```

---

## ⚠️ 故障排查

**问题**: `ModuleNotFoundError: No module named 'gdelt_api'`

**解决**:
```bash
set PYTHONPATH=.\src
```

**问题**: MCP 连接失败

**解决**: 检查 `mcp_server/server.py` 是否存在，依赖是否安装。

---

## 📄 License

MIT
# Spatio-Temporal Narrative AI Agent

基于 MCP (Model Context Protocol) 架构的北美事件时空叙事分析系统，使用 GDELT 2.0 数据集（2024年北美事件）实现自主因果推理与事件链重构。

## 项目简介

本系统通过 MCP 协议桥接关系型 MySQL 数据库与大语言模型 (LLM)，支持：
- **Text2SQL** 自然语言查询转 SQL
- **RAG** 检索增强生成
- **时空事件分析** 基于地理坐标和时间序列的事件关联
- **因果叙事生成** 自动发现目标事件的前因后果链

## 技术栈

| 组件 | 技术 |
|------|------|
| 编程语言 | Python 3.10+ |
| 数据库 | MySQL 8.0+ (支持空间扩展) |
| MCP 框架 | FastMCP |
| LLM API | Kimi Code API |
| 数据处理 | pandas, numpy |
| 可视化 | matplotlib |

## 项目结构

```
project/
├── data/                       # GDELT CSV 数据文件 (93 chunks)
│   └── gdelt_2024_na_*.csv
├── db_scripts/                 # 数据库脚本
│   ├── gdelt_db_v1.sql         # MySQL 建表脚本
│   ├── import_event.py         # 数据导入脚本
│   └── data_view.py            # 数据预览工具
├── mcp_server/                 # MCP 服务器
│   └── server.py               # FastMCP 服务端
├── mcp_client/                 # MCP 客户端
│   └── client.py               # LLM 交互客户端
├── index.html                  # 项目展示页面
├── sample.csv                  # 数据样本
└── .env                        # 环境变量配置
```

## 快速开始

### 1. 环境准备

创建 `.env` 文件：

```bash
# MySQL 密码
DB_PASSWORD=your_mysql_password

# Kimi Code API Key (从 https://www.kimi.com/code/console 获取)
API_KEY=sk-kimi-xxxxx
```

### 2. 安装依赖

```bash
pip install mcp fastmcp mysql-connector-python pandas numpy openai python-dotenv pydantic
```

### 3. 数据库设置

```bash
# 创建数据库
mysql -u root -p < db_scripts/gdelt_db_v1.sql

# 导入数据 (约 4.5GB，需要较长时间)
python db_scripts/import_event.py
```

### 4. 运行系统

启动 MCP 服务器（终端 1）：
```bash
python mcp_server/server.py
```

启动 MCP 客户端（终端 2）：
```bash
python mcp_client/client.py
```

## 使用示例

客户端启动后，输入自然语言查询：

```
👤 用户: 计算 2+3*4
🔧 调用 FastMCP 工具: calculate
📊 结果: 结果: 14.0...
🤖 Kimi: 计算结果是 14

👤 用户: 北京的天气怎么样
🔧 调用 FastMCP 工具: get_weather
📊 结果: 北京 2025-03-12: 晴, 22°C...
🤖 Kimi: 北京今天天气晴朗，22°C

👤 用户: quit
```

## 数据库架构

**主表**: `events_table`

| 字段 | 类型 | 说明 |
|------|------|------|
| GlobalEventID | BIGINT | 事件唯一标识 |
| SQLDATE | DATE | 事件日期 |
| Actor1Name | VARCHAR | 主要参与者 |
| Actor2Name | VARCHAR | 次要参与者 |
| EventCode | VARCHAR | CAMEO 事件代码 |
| GoldsteinScale | FLOAT | 冲突/合作评分 |
| ActionGeo_Lat/Long | DECIMAL | 地理坐标 |
| ActionGeo_Point | POINT | 空间几何点 (SRID 4326) |
| SOURCEURL | TEXT | 新闻来源 URL |

## MCP 工具

| 工具名 | 功能 |
|--------|------|
| `calculate` | 数学计算 (sqrt, pow, abs 等) |
| `get_weather` | 天气查询 (演示数据) |
| `analyze_code` | 代码统计分析 |
| `smart_search` | 知识库搜索 |

## 数据来源

**GDELT 2.0 Dataset** - [Global Database of Events, Language, and Tone](https://www.gdeltproject.org/)
- 时间范围：2024年全年
- 地理范围：北美（美国、加拿大、墨西哥）
- 数据量：约 450 万条事件记录

## 团队成员

- Xing Gao
- Xiangxin Tang
- Yuxin Miao
- Ziliang Chen

**Virginia Tech** - "Ut Prosim" (That I May Serve)

## 许可证

本项目为学术研究用途。

## 致谢

- [GDELT Project](https://www.gdeltproject.org/)
- [MCP Protocol](https://modelcontextprotocol.io/)
- [FastMCP](https://github.com/jlowin/fastmcp)
- [Moonshot AI](https://www.moonshot.cn/)

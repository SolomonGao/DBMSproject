# GDELT MCP Event Analysis Platform

> **从"数据查询工具"到"国际事件洞察助手"**
>
> 一个融合自然语言交互、RAG语义搜索、空间-时间叙事分析的智能 GDELT 2.0 数据分析平台

**Institution**: Virginia Tech ("Ut Prosim" - That I May Serve)  
**Research Team**: Xing Gao, Xiangxin Tang, Yuxin Miao, Ziliang Chen

---

## 🎯 产品愿景

### 现状 vs 目标

| 维度 | 传统数据库查询 | 本系统（事件洞察助手） |
|------|--------------|---------------------|
| **用户输入** | "查询华盛顿1月的冲突事件" | "华盛顿最近发生了什么大事？" |
| **系统回复** | 原始数据表格 | 洞察摘要 + 关键事件时间线 |
| **交互方式** | CLI + 技术参数 | 自然语言对话 |
| **响应时间** | 60秒（实时聚合） | <5秒（预计算+缓存） |
| **事件引用** | GlobalEventID 742447353 | US-20240115-WDC-PROTEST-001 |
| **核心能力** | 数据检索 | 因果分析 + 态势感知 + RAG语义理解 |

### 核心用户场景

```
场景A: 每日新闻简报
👤 "今天有什么重要国际新闻？"
🤖 📊 今日简报 | 🔴 3起热点 | 📈 冲突趋势

场景B: 事件深度分析  
👤 "详细说说美伊对峙"
🤖 📰 摘要 | ⏱️ 时间线 | 👥 相关方 | 🔗 因果链

场景C: 区域态势感知
👤 "中东地区最近怎么样？"
🤖 🗺️ 态势地图 | 🔺 风险点 | 📈 趋势预测

场景D: 主题追踪
👤 "追踪2024年气候变化抗议"
🤖 📈 趋势图 | 📍 热点分布 | 🔍 关键诉求
```

---

## ✨ 核心特性

### 1. 🤖 双模型架构（意图驱动）

```
用户输入 → Router(Qwen 2.5B 本地) → 意图识别 → 工具预选择
                ↓
         LLM(Kimi/Claude) → 生成回复
                ↓
         MCP Server → 执行查询
```

| 组件 | 模型 | 作用 |
|------|------|------|
| **Router** | Qwen 2.5B (本地) | 意图识别、输入清理、工具预选择 |
| **LLM** | Kimi Code / Claude | 自然语言理解、回复生成、工具调用决策 |

### 2. 📚 RAG 语义搜索（向量数据库）

```
用户: "抗议者有什么诉求？"
   ↓
ChromaDB 语义检索: "protesters demanding climate action"
   ↓
返回真实新闻原文片段（非结构化数据）
   ↓
LLM 总结：抗议者要求政府采取气候行动...
```

- **向量模型**: all-MiniLM-L6-v2 (384维)
- **数据来源**: GDELT SOURCEURL 新闻爬取
- **数量**: 30万+ 新闻文章向量化

### 3. 🗺️ 空间-时间叙事分析

```
用户: "华盛顿抗议后的警方回应是什么？"
   ↓
Step 1: 空间-时间锚点定位
   - 地点: Washington (38.9, -77.0)
   - 时间: 2024-01-15
   - 半径: 500km, 7天窗口

Step 2: 追踪后续事件
   - 时空查询 ST_Distance_Sphere + DATE_ADD

Step 3: 因果链构建
   - Event A (抗议) → Event B (警方响应)

Step 4: 叙事合成
   - 返回时间线 + 相关方 + 演变过程
```

### 4. ⚡ 性能优化

| 优化技术 | 效果 | 实现 |
|---------|------|------|
| **预计算表** | 60s → <0.5s (120x) | ETL每日生成摘要/热点/网格 |
| **并行查询** | 5个查询并发执行 | `get_dashboard` 3-5x加速 |
| **查询缓存** | 重复查询 10-100x | LRU + TTL (300s) |
| **流式查询** | 内存 ↓ 90% | 大数据量分块读取 |
| **空间索引** | 地理查询 <2s | MySQL 8.0 空间扩展 |

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         用户层                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   CLI        │  │   Web (TODO) │  │   API (TODO) │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
└─────────┼─────────────────┼─────────────────┼───────────────────┘
          │                 │                 │
          └─────────────────┼─────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      智能层 (AI Layer)                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   Router    │  │    LLM      │  │   RAG Engine            │  │
│  │ (Ollama/    │→ │ (Kimi/      │← │  (ChromaDB)             │  │
│  │  Qwen 2.5B) │  │  Claude)    │  │  语义搜索               │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                            │ MCP Protocol
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      服务层 (Service Layer)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ MCP Tools    │  │  Cache       │  │   Streaming          │   │
│  │ • search_    │  │  (LRU+TTL)   │  │   (Chunked Query)    │   │
│  │   events     │  │              │  │                      │   │
│  │ • get_event  │  │              │  │                      │   │
│  │ • get_       │  │              │  │                      │   │
│  │   dashboard  │  │              │  │                      │   │
│  │ • search_    │  │              │  │                      │   │
│  │   news_      │  │              │  │                      │   │
│  │   context    │  │              │  │                      │   │
│  └───────┬──────┘  └──────────────┘  └──────────────────────┘   │
└──────────┼──────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────┐
│                       数据层 (Data Layer)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │  MySQL 8.0   │  │  ChromaDB    │  │   ETL Pipeline       │   │
│  │              │  │  (Vector)    │  │   (Daily @ 2AM)      │   │
│  │ • events     │  │              │  │                      │   │
│  │ • daily_     │  │ • news_      │  │ • 预计算表生成        │   │
│  │   summary    │  │   collection │  │ • 事件指纹生成        │   │
│  │ • region_    │  │              │  │ • 知识库更新          │   │
│  │   stats      │  │              │  │                      │   │
│  │ • event_     │  │              │  │                      │   │
│  │   fingerprints│ │              │  │                      │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ MCP 工具集（15个）

### 基础查询工具（4个）

| 工具 | 用途 | 示例 |
|------|------|------|
| `get_schema` | 查看表结构 | `get_schema()` |
| `execute_sql` | 自定义SQL | `execute_sql("SELECT * FROM events LIMIT 10")` |
| `query_by_time_range` | 时间查询 | `query_by_time_range("2024-01-01", "2024-01-31")` |
| `query_by_actor` | 参与方查询 | `query_by_actor("USA", limit=50)` |

### 统计分析工具（4个）

| 工具 | 用途 | 优化 |
|------|------|------|
| `get_dashboard` | 仪表盘（5查询并行） | ⭐ 并行执行，最快 |
| `analyze_time_series` | 时间序列分析 | 数据库端聚合 |
| `analyze_conflict_cooperation` | 冲突/合作趋势 | 预计算数据 |
| `get_geo_heatmap` | 地理热力图 | 网格预计算 |

### RAG / 高级工具（5个）

| 工具 | 用途 | 数据来源 |
|------|------|---------|
| `search_news_context` | ⭐ RAG语义搜索 | ChromaDB 向量库 |
| `stream_query_events` | 流式大数据查询 | MySQL 流式读取 |
| `get_cache_stats` | 缓存诊断 | 内存统计 |
| `clear_cache` | 清空缓存 | - |
| `generate_chart` | 图表配置生成 | - |

### 辅助工具（2个）

| 工具 | 用途 |
|------|------|
| `get_schema_guide` | 显示字段说明和示例 |
| `get_schema` | 查看表结构 |

---

## 🚀 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone <repository>
cd DBMSproject

# 切换到合并分支
git checkout merge-optimized

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
# 方式一：交互式配置
python run_v1.py --config

# 方式二：手动创建 .env 文件
cat > .env << EOF
KIMI_CODE_API_KEY=sk-your-key-here
LLM_PROVIDER=kimi_code
LLM_MODEL=kimi-k2-0711-preview
DB_PASSWORD=rootpassword
EOF
```

### 3. 启动 Docker 服务

```bash
# 启动 MySQL + App 容器
docker-compose up -d

# 检查状态
docker-compose ps

# 查看日志
docker-compose logs -f app
```

### 4. 运行主程序

```bash
# 启动交互式 CLI
python run_v1.py
```

### 5. 构建知识库（可选，首次使用）

```bash
# 启动知识库构建（后台守护）
python start_kb.py

# 查看缓存统计
python manage_cache.py stats
```

---

## 📊 数据架构

### 预计算表（ETL生成）

| 表名 | 记录数 | 用途 | 生成方式 |
|-----|-------|------|---------|
| `events_table` | 1589万 | 原始事件数据 | 导入 |
| `event_fingerprints` | 32.8万 | 事件指纹 | ETL自动生成 |
| `daily_summary` | 366 | 每日摘要 | ETL每日2AM |
| `region_daily_stats` | 1098 | 地区统计 | ETL每日2AM |
| `geo_heatmap_grid` | 4701 | 地理网格 | ETL每日2AM |

### 事件指纹系统

**标准指纹**（ETL预生成）：
```
格式: {COUNTRY}-{YYYYMMDD}-{LOCATION}-{TYPE}-{SEQ}
示例: US-20240115-WDC-PROTEST-001

US: 国家代码
20240115: 日期
WDC: 地点缩写（前3字母）
PROTEST: 事件类型（CAMEO映射）
001: 序号
```

**临时指纹**（实时生成）：
```
格式: EVT-{YYYY-MM-DD}-{GID}
示例: EVT-2024-12-30-1217480788

用途: ETL未处理的新数据也能立即查询
```

---

## 📈 性能基准

| 场景 | 优化前 | 优化后 | 提升 |
|-----|-------|-------|------|
| 每日简报 | 60s | <0.5s | **120x** |
| 热点事件 | 30s | <0.1s | **300x** |
| 区域概览 | 45s | <2s | **22x** |
| 事件详情 | 0.5s | <0.01s | **50x** |
| 地图热力图 | 超时 | <2s | **∞** |
| RAG语义搜索 | - | <1s | 新增 |

---

## 🗺️ 路线图（Roadmap）

### ✅ 已完成 (Phase 1-3)

- [x] **Phase 1**: 产品定位重塑（用户画像、场景定义）
- [x] **Phase 2**: 数据架构优化（预计算表、ETL Pipeline、指纹系统）
- [x] **Phase 3**: 工具重构精简（6个意图驱动工具、Router集成）
- [x] **Phase 3.5**: txx_docker 合并（RAG、缓存、并行查询）

### ⏳ 进行中 / 待开始

#### Phase 4: 工具补充增强（1周）
- [ ] `track_theme` - 主题追踪（追踪"俄乌冲突"等主题发展）
- [ ] `compare_regions` - 区域对比（对比多国冲突趋势）
- [ ] `export_events` - 数据导出（CSV/JSON格式）

#### Phase 5: 前端可视化（4周）
- [ ] React + TypeScript 项目初始化
- [ ] 事件地图视图（Leaflet）
- [ ] 事件详情卡片组件
- [ ] 时间轴视图
- [ ] 仪表盘视图（ECharts）
- [ ] 事件关联图谱（D3.js）

#### Phase 6: 智能增强（2周）
- [ ] LLM事件摘要生成
- [ ] 因果链自动分析
- [ ] 异常事件检测
- [ ] 智能推荐系统

---

## 📝 常用命令

```bash
# 启动服务
docker-compose up -d

# 运行主程序
python run_v1.py

# 构建知识库
python start_kb.py

# 缓存管理
python manage_cache.py stats      # 查看统计
python manage_cache.py monitor    # 实时监控
python manage_cache.py clear      # 清空缓存

# ETL 操作
./run_etl_2024.sh                 # 全年批处理
python db_scripts/etl_pipeline.py 2024-01-15  # 单天

# 数据库检查
docker exec gdelt_mysql mysql -u root -prootpassword gdelt -e "SHOW TABLES;"
```

---

## 📚 文档索引

| 文档 | 说明 |
|------|------|
| `README.md` | 本文档 - 全面介绍 |
| `ROADMAP.md` | 详细路线图和进度 |
| `AGENTS.md` | AI Agent开发指南 |
| `OPTIMIZATION_GUIDE.md` | 代码优化技术详解 |

---

## 🤝 贡献

**Institution**: Virginia Tech  
**Research Team**: Xing Gao, Xiangxin Tang, Yuxin Miao, Ziliang Chen

---

*最后更新: 2026-04-12*  
*版本: merge-optimized (txx_docker + 用户驱动版本)*

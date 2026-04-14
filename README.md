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

### 4. 💬 Web Chat UI（ChatGPT-style）

除了 CLI，系统现在提供完整的 Web 前端：

```
http://localhost:8080/chat
```

- **多会话管理**：侧边栏保存本地对话历史
- **Thinking Process**：每条回复可展开查看 Router 决策、工具调用、耗时明细
- **Stop 按钮**：请求发送中可随时中断思考
- **120 秒超时**：兼容长耗时数据库查询（如 70 秒+ 的大数据分析）
- **Prompt 卡片**：一键填入常用查询模板

### 5. ⚡ 性能优化

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
│  │   CLI        │  │   Web UI     │  │   API (TODO) │          │
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
│  │              │  │  (Vector)    │  │                      │   │
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

## 🛠️ MCP 工具集（18个）

### 核心意图驱动工具（6个）- 用户驱动版本

| 工具 | 用途 | 示例 | 返回 |
|------|------|------|------|
| `search_events` | ⭐ 智能事件搜索（核心入口） | `"1月华盛顿的抗议"` | 事件列表（带指纹ID） |
| `get_event_detail` | 获取事件详情（通过指纹） | `fingerprint="US-20240115-WDC-PROTEST-001"` | 详细信息 |
| `get_regional_overview` | 区域态势概览 | `region="Middle East"` | 态势评分+热点 |
| `get_hot_events` | 单日热点推荐 | `date="2024-01-15"` | TOP事件 |
| `get_top_events` | 时间段热度排行 | `start_date="2024-01-01"` | 热度排序 |
| `get_daily_brief` | 每日简报 | - | 摘要报告 |

### RAG & 语义理解（2个）- txx_docker

| 工具 | 用途 | 示例 | 数据来源 |
|------|------|------|---------|
| `search_news_context` | ⭐ RAG语义搜索 | `"protesters demanding climate action"` | ChromaDB 向量库 |
| `stream_events` | 流式大数据查询（内存友好） | `actor_name="Protest"` | MySQL SSCursor |

### 统计分析 & 优化工具（6个）- txx_docker

| 工具 | 用途 | 优化技术 |
|------|------|---------|
| `get_dashboard` | 仪表盘（多维度统计） | 5查询并行执行 |
| `analyze_time_series` | 时间序列分析 | 数据库端聚合 |
| `analyze_conflict_cooperation` | 冲突/合作趋势 | 预计算表 |
| `get_geo_heatmap` | 地理热力图 | 空间索引+网格 |
| `get_cache_stats` | 缓存诊断 | 内存统计 |
| `clear_cache` | 清空缓存 | - |

### 基础查询工具（3个）

| 工具 | 用途 | 说明 |
|------|------|------|
| `query_by_location` | 地理位置查询 | 支持空间索引 |
| `query_by_time_range` | 时间范围查询 | 带缓存 |
| `query_by_actor` | 参与方查询 | 带缓存 |
| `execute_sql` | 自定义SQL | 通用接口 |

### 辅助工具（1个）

| 工具 | 用途 |
|------|------|
| `get_schema_guide` | 字段说明和示例 |

---

## 🔗 工具关联使用指南

### 典型工作流

```
工作流1: 深度事件分析
👤 "华盛顿抗议事件的详情"
   ↓
1. search_events("华盛顿 抗议") 
   → 返回事件列表 [{指纹: US-20240115-WDC-001}, ...]
   ↓
2. get_event_detail(fingerprint="US-20240115-WDC-001")
   → 时空数据 + 基础信息
   ↓
3. search_news_context("Washington protest demands")
   → 新闻原文 + 具体诉求
   ↓
🤖 综合分析报告（数据+新闻）

工作流2: 区域态势感知
👤 "中东局势怎么样？"
   ↓
1. get_regional_overview(region="Middle East")
   → 态势评分 + 统计数据
   ↓
2. get_geo_heatmap(start_date, end_date)
   → 地理热力图
   ↓
3. get_hot_events(date)
   → 当日热点事件
   ↓
🤖 完整态势报告

工作流3: 主题追踪分析
👤 "追踪全年气候变化抗议"
   ↓
1. stream_events(actor_name="Climate", max_results=1000)
   → 大量事件流式读取
   ↓
2. analyze_time_series(start_date, end_date, granularity="month")
   → 月度趋势分析
   ↓
3. search_news_context("climate protest demands 2024")
   → 新闻诉求分析
   ↓
🤖 主题追踪报告
```

### 工具依赖关系

```
search_events ─┬─→ get_event_detail ─┬─→ search_news_context (RAG)
               │                      └─→ query_by_location (空间扩展)
               └─→ get_geo_heatmap

get_dashboard ─┬─→ analyze_time_series
               └─→ analyze_conflict_cooperation
```

### 指纹系统流转

```
┌─────────────────────────────────────────────────────────┐
│  ETL Pipeline (每日2AM)                                  │
│  events_table ──→ event_fingerprints                     │
│  (原始数据)      (标准指纹 + 标题/摘要)                   │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  search_events                                          │
│  - 优先返回有标准指纹的事件                              │
│  - 无指纹的生成临时指纹 EVT-{date}-{gid}                │
│  - 返回: fingerprint (标准📌 / 临时📝)                  │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  get_event_detail(fingerprint)                          │
│  - 标准指纹: JOIN event_fingerprints 获取完整信息        │
│  - 临时指纹: 直接查询 events_table                       │
└─────────────────────────────────────────────────────────┘
```

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

**方式 A：交互式 CLI**
```bash
python run_v1.py
```

**方式 B：Web UI（推荐新用户）**
```bash
# 本地运行
python run_web.py --port 8080

# Docker 内运行（需暴露 0.0.0.0）
docker exec -it gdelt_app python run_web.py --host 0.0.0.0 --port 8080
```

访问 `http://localhost:8080/` 进入主页，点击 **Launch Chat UI** 开始对话。

> **注意**：`docker-compose.yml` 已将容器 8080 端口映射到宿主机，修改代码后需重启 `run_web.py` 主进程才能生效。

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

#### Phase 5: 前端可视化（已完成 MVP）
- [x] ChatGPT-style Web UI（多会话、Thinking Process、Stop 按钮）
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

# 运行主程序（CLI）
python run_v1.py

# 运行 Web UI
docker exec -it gdelt_app python run_web.py --host 0.0.0.0 --port 8080

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

*最后更新: 2026-04-13*  
*版本: merge-ui (eng + chat/ui 合并版)*

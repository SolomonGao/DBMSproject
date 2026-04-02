# GDELT MCP 项目优化路线图

> 从"数据查询工具"到"国际事件洞察助手"的转型指南
> 版本: 1.0 | 创建: 2024-04-02 | 预计工期: 12周

---

## 执行清单总览

### Phase 1: 产品定位重塑 (2周)
- [ ] 1.1 确定3个核心用户画像
- [ ] 1.2 定义4个核心使用场景  
- [ ] 1.3 撰写产品愿景文档
- [ ] 1.4 设计新架构图

### Phase 2: 数据架构优化 (2周) ✅
- [x] 2.1 创建5个预计算表 → `db_scripts/precompute_tables.sql`
- [x] 2.2 编写ETL Pipeline脚本 → `db_scripts/etl_pipeline.py`
- [x] 2.3 表分区改造 → `db_scripts/partition_events_table.sql`
- [x] 2.4 设置定时任务 → `db_scripts/crontab_setup.sh`

### Phase 3: 工具重构精简 (2周)
- [ ] 3.1 开发5个核心工具
- [ ] 3.2 实现事件指纹系统
- [ ] 3.3 为历史数据生成指纹
- [ ] 3.4 旧工具标记废弃

### Phase 4: 前端可视化 (4周)
- [ ] 4.1 React项目初始化
- [ ] 4.2 事件地图视图
- [ ] 4.3 事件详情卡片
- [ ] 4.4 时间轴视图
- [ ] 4.5 仪表盘视图
- [ ] 4.6 事件关联图谱

### Phase 5: 智能增强 (2周)
- [ ] 5.1 LLM事件摘要生成
- [ ] 5.2 因果链分析
- [ ] 5.3 异常事件检测
- [ ] 5.4 智能推荐

---

## 立即执行（本周可做）

### 任务1: 添加默认时间范围限制
**文件**: `mcp_server/app/tools/gdelt_optimized.py`
**位置**: 在 `query_by_actor`, `query_by_location` 等工具开头添加

```python
from datetime import datetime, timedelta

# 如果没有指定日期，默认查最近7天
if not start_date:
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
```

### 任务2: 查询结果默认限制为Top 10
**修改所有工具的 limit 默认值**:
```python
limit: int = Field(default=10, ge=1, le=1000)  # 原来是100/500
```

### 任务3: 添加热点事件推荐工具
**新增工具** `get_hot_events`:
```python
@mcp.tool()
async def get_hot_events(date: str = None, top_n: int = 5) -> str:
    """
    获取热点事件（按报道量+冲突强度排序）
    """
    query = """
    SELECT SQLDATE, Actor1Name, Actor2Name, EventCode,
           GoldsteinScale, NumArticles, ActionGeo_FullName
    FROM events_table
    WHERE SQLDATE = %s
    ORDER BY NumArticles * ABS(GoldsteinScale) DESC
    LIMIT %s
    """
    # ... 实现代码
```

---

## Phase 2: 预计算表详细设计

### 表1: daily_summary
```sql
CREATE TABLE IF NOT EXISTS daily_summary (
    date DATE PRIMARY KEY,
    total_events INT,
    conflict_events INT,
    cooperation_events INT,
    avg_goldstein FLOAT,
    avg_tone FLOAT,
    top_actors JSON,
    top_locations JSON,
    hot_topics JSON
);
```

### 表2: event_fingerprints
```sql
CREATE TABLE IF NOT EXISTS event_fingerprints (
    global_event_id BIGINT PRIMARY KEY,
    fingerprint VARCHAR(50),      -- 'US-20240115-WDC-PROTEST-001'
    headline VARCHAR(255),        -- LLM生成
    summary TEXT,                 -- LLM生成
    key_actors JSON,
    location_name VARCHAR(100),
    event_type VARCHAR(50),
    severity_score FLOAT
);
```

### 表3: region_daily_stats
```sql
CREATE TABLE IF NOT EXISTS region_daily_stats (
    region_code VARCHAR(10),
    date DATE,
    event_count INT,
    conflict_intensity FLOAT,
    primary_actor VARCHAR(100),
    PRIMARY KEY (region_code, date)
);
```

### ETL Pipeline
```python
# db_scripts/etl_pipeline.py
async def run_daily_etl():
    yesterday = datetime.now() - timedelta(days=1)
    
    # 1. 聚合昨日数据到 daily_summary
    # 2. 为新事件生成指纹
    # 3. 更新地区统计
    # 4. 重新计算热点事件
```

---

## Phase 3: 新工具设计

### 核心工具1: search_events
```python
@mcp.tool()
async def search_events(
    query: str,                    # 自然语言
    date_hint: Optional[str] = None,
    location_hint: Optional[str] = None,
    max_results: int = 10
) -> str:
    """
    用户说: "1月华盛顿的抗议"
    系统解析: date=2024-01, location=Washington, theme=protest
    返回: EventFingerprint 列表
    """
```

### 核心工具2: get_event_timeline
```python
@mcp.tool()
async def get_event_timeline(
    fingerprint: str,
    depth: int = 7
) -> str:
    """
    追溯事件因果链
    返回: 前因 → 事件 → 后果
    """
```

### 核心工具3: get_regional_overview
```python
@mcp.tool()
async def get_regional_overview(
    region: str,
    date_range: str
) -> str:
    """
    生成区域态势报告（不是原始数据，是洞察摘要）
    返回: headline, summary, key_findings, risk_assessment
    """
```

---

## Phase 4: 前端架构

### 技术栈
- React 18 + TypeScript
- Leaflet (地图)
- ECharts (图表)

### 核心视图
1. **事件地图**: 散点图，颜色=冲突强度，大小=报道量
2. **事件详情**: 卡片式，含时间线
3. **仪表盘**: 趋势图 + Top排行 + 饼图
4. **关系图谱**: D3.js 力导向图

### 目录结构
```
frontend/
├── src/
│   ├── components/
│   │   ├── EventMap.tsx
│   │   ├── EventDetailCard.tsx
│   │   └── Timeline.tsx
│   ├── views/
│   │   ├── MapView.tsx
│   │   ├── DashboardView.tsx
│   │   └── GraphView.tsx
│   └── api/
│       └── gdelt.ts
```

---

## Phase 5: LLM增强

### 1. 事件摘要生成
```python
async def generate_event_summary(event: Dict) -> str:
    prompt = f"""
    事件: {event['Actor1Name']} vs {event['Actor2Name']} 
    地点: {event['ActionGeo_FullName']}
    日期: {event['SQLDATE']}
    类型: {event['EventCode']}
    
    用一句话总结这个事件:
    """
    return await llm.chat(prompt)
```

### 2. 因果链分析
- 获取前后7天事件
- 计算特征相似度
- LLM判断因果关系

---

## 文件创建计划

### Phase 1
- [ ] `docs/PRODUCT_VISION.md`
- [ ] `docs/ARCHITECTURE_V2.md`

### Phase 2
- [ ] `db_scripts/precompute_tables.sql`
- [ ] `db_scripts/etl_pipeline.py`

### Phase 3
- [ ] `mcp_server/app/tools/core_tools_v2.py`
- [ ] `mcp_server/app/services/fingerprint_service.py`

### Phase 4
- [ ] `frontend/` (完整React项目)

---

## 快速启动命令

```bash
# Phase 2: 创建预计算表
docker exec -i gdelt_mysql mysql -u root -prootpassword gdelt < db_scripts/precompute_tables.sql

# Phase 3: 运行ETL
docker exec gdelt_app python db_scripts/etl_pipeline.py

# Phase 4: 启动前端
cd frontend && npm start
```

---

## 快速启动脚本

### 1. 初始化预计算表
```bash
cd "/Volumes/Mac Driver/capstone/DBMSproject"

# 创建表
docker exec -i gdelt_mysql mysql -u root -prootpassword gdelt_db < db_scripts/precompute_tables.sql

echo "✅ 预计算表创建完成"
```

### 2. 运行一次ETL（测试）
```bash
# 手动运行ETL
docker exec -w /app gdelt_mcp python db_scripts/etl_pipeline.py 2024-01-15

# 或运行最近一天
docker exec -w /app gdelt_mcp python db_scripts/etl_pipeline.py
```

### 3. 设置定时任务
```bash
# 编辑crontab
crontab -e

# 添加（每天凌晨2点运行）
0 2 * * * docker exec -w /app gdelt_mcp python db_scripts/etl_pipeline.py >> /var/log/gdelt_etl.log 2>&1
```

### 4. 验证数据
```bash
# 检查日报表
docker exec gdelt_mysql mysql -u root -prootpassword gdelt_db -e "SELECT * FROM daily_summary ORDER BY date DESC LIMIT 3;"

# 检查指纹表
docker exec gdelt_mysql mysql -u root -prootpassword gdelt_db -e "SELECT COUNT(*) FROM event_fingerprints;"
```

---

## 下一步行动

### 本周可做（高优先级）
1. ☐ 创建预计算表
2. ☐ 运行一次ETL测试
3. ☐ 修改现有工具默认时间范围为最近7天
4. ☐ 查询结果默认限制为Top 10

### 下周计划（中优先级）
1. ☐ 实现核心工具V2 (5个工具)
2. ☐ 添加热点事件推荐工具
3. ☐ 连接预计算表到新工具

### 后续规划（低优先级）
1. ☐ React前端项目初始化
2. ☐ 事件地图视图
3. ☐ LLM摘要生成集成

---

*本文档是活文档，执行过程中可根据实际情况调整*

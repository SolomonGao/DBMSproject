"""
GDELT MCP 核心工具 V2
设计理念: 从高参数查询转向高意图理解

从:
  query_by_actor(actor="USA", date_start="2024-01-01", ...)
到:
  search_events(query="1月华盛顿的抗议", max_results=10)

工具数量: 15个 → 5个
"""

import json
import logging
from typing import Optional, Literal
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from fastmcp import FastMCP

# 导入数据库连接
from ..database import get_db_pool
from ..cache import query_cache

logger = logging.getLogger(__name__)

DEFAULT_TABLE = "events_table"


# ============================================================================
# 输入模型定义
# ============================================================================

class SearchEventsInput(BaseModel):
    """搜索事件 - 支持自然语言查询"""
    query: str = Field(
        ...,
        description="自然语言查询，如'1月华盛顿的抗议'、'中东最近冲突'"
    )
    time_hint: Optional[str] = Field(
        None,
        description="时间提示: 'today', 'yesterday', 'this_week', 'this_month', '2024-01'"
    )
    location_hint: Optional[str] = Field(
        None,
        description="地点提示，如'Washington', 'China', 'Middle East'"
    )
    event_type: Optional[Literal[
        'conflict', 'cooperation', 'protest', 'diplomacy', 
        'military', 'economic', 'any'
    ]] = Field(
        'any',
        description="事件类型筛选"
    )
    severity: Optional[Literal['low', 'medium', 'high', 'critical', 'any']] = Field(
        'any',
        description="严重程度筛选"
    )
    max_results: int = Field(
        default=10,
        ge=1,
        le=50,
        description="返回结果数量（默认10条）"
    )


class GetEventDetailInput(BaseModel):
    """获取事件详情 - 通过指纹ID"""
    fingerprint: str = Field(
        ...,
        description="事件指纹ID，如'US-20240115-WDC-PROTEST-001'"
    )
    include_causes: bool = Field(
        default=True,
        description="是否包含前因分析"
    )
    include_effects: bool = Field(
        default=True,
        description="是否包含后果分析"
    )
    include_related: bool = Field(
        default=True,
        description="是否包含相关事件"
    )


class GetRegionalOverviewInput(BaseModel):
    """获取区域态势概览"""
    region: str = Field(
        ...,
        description="区域名称或代码，如'China', 'Middle East', 'US-CA'"
    )
    time_range: Literal['day', 'week', 'month', 'quarter', 'year'] = Field(
        default='week',
        description="时间范围"
    )
    include_trend: bool = Field(
        default=True,
        description="是否包含趋势分析"
    )
    include_risks: bool = Field(
        default=True,
        description="是否包含风险评估"
    )


class GetHotEventsInput(BaseModel):
    """获取热点事件推荐"""
    date: Optional[str] = Field(
        None,
        description="日期，如'2024-01-15'，默认昨天"
    )
    region_filter: Optional[str] = Field(
        None,
        description="区域过滤，如'Asia', 'Europe'"
    )
    top_n: int = Field(
        default=5,
        ge=1,
        le=20,
        description="返回热点数量"
    )


class GetTopEventsInput(BaseModel):
    """获取时间段内热度最高的事件"""
    start_date: str = Field(
        ...,
        description="开始日期，如'2024-01-01'"
    )
    end_date: str = Field(
        ...,
        description="结束日期，如'2024-12-31'"
    )
    region_filter: Optional[str] = Field(
        None,
        description="区域过滤，如'USA', 'China', 'Middle East'"
    )
    event_type: Optional[Literal['conflict', 'cooperation', 'protest', 'any']] = Field(
        'any',
        description="事件类型筛选"
    )
    top_n: int = Field(
        default=10,
        ge=1,
        le=50,
        description="返回数量（默认10条）"
    )


class GetDailyBriefInput(BaseModel):
    """获取每日简报"""
    date: Optional[str] = Field(
        None,
        description="日期，默认昨天"
    )
    region_focus: Optional[str] = Field(
        None,
        description="区域关注，如'global', 'asia', 'us'"
    )
    format: Literal['summary', 'detailed', 'executive'] = Field(
        default='summary',
        description="简报格式"
    )


# ============================================================================
# 工具注册函数
# ============================================================================

def register_core_tools(mcp: FastMCP):
    """注册核心工具V2到MCP服务器"""
    
    @mcp.tool()
    async def search_events(params: SearchEventsInput) -> str:
        """
        智能搜索事件 - 核心入口工具
        
        示例:
        - "1月华盛顿的抗议" → time_hint=2024-01, location_hint=Washington, event_type=protest
        - "中东军事冲突" → location_hint=Middle East, event_type=conflict
        - "中美经济往来" → query="China US economic"
        """
        # 解析时间提示
        date_start, date_end = _parse_time_hint(params.time_hint)
        
        # 构建查询 (优先使用预计算表，回退到实时查询)
        query = f"""
        SELECT 
            e.GlobalEventID,
            e.SQLDATE,
            e.Actor1Name,
            e.Actor2Name,
            e.EventCode,
            e.EventRootCode,
            e.GoldsteinScale,
            e.NumArticles,
            e.AvgTone,
            e.ActionGeo_FullName,
            e.ActionGeo_CountryCode,
            e.ActionGeo_Lat,
            e.ActionGeo_Long
        FROM {DEFAULT_TABLE} e
        WHERE 1=1
        """
        
        conditions = []
        query_params = []
        
        # 时间条件
        conditions.append("e.SQLDATE BETWEEN %s AND %s")
        query_params.extend([date_start, date_end])
        
        # 地点条件
        if params.location_hint:
            conditions.append("(e.ActionGeo_FullName LIKE %s OR e.ActionGeo_CountryCode = %s)")
            location_pattern = f"%{params.location_hint}%"
            query_params.extend([location_pattern, params.location_hint.upper()])
        
        # 事件类型
        if params.event_type != 'any':
            type_conditions = {
                'conflict': "e.GoldsteinScale < -5",
                'cooperation': "e.GoldsteinScale > 5",
                'protest': "e.EventRootCode = '14'",
                'diplomacy': "e.EventRootCode IN ('01', '02', '03')",
                'military': "e.EventRootCode IN ('18', '19', '20')",
                'economic': "e.EventRootCode = '06'"
            }
            if params.event_type in type_conditions:
                conditions.append(type_conditions[params.event_type])
        
        # 构建完整查询
        if conditions:
            query += " AND " + " AND ".join(conditions)
        
        # 排序和限制
        query += f"""
        ORDER BY 
            e.NumArticles * ABS(e.GoldsteinScale) DESC
        LIMIT {params.max_results}
        """
        
        # 执行查询
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(query, tuple(query_params))
                    rows = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description] if cursor.description else []
                    
                    if not rows:
                        return f"❌ 未找到与 '{params.query}' 相关的事件（时间范围: {date_start} ~ {date_end}）"
                    
                    # 格式化为可读结果
                    return _format_search_results_v2(rows, columns, params.query)
        except Exception as e:
            logger.error(f"搜索事件失败: {e}")
            return f"❌ 查询失败: {str(e)}"

    @mcp.tool()
    async def get_event_detail(params: GetEventDetailInput) -> str:
        """
        获取事件详情 - 包含前因后果分析
        
        支持两种指纹格式:
        - 标准指纹: "US-20240115-WDC-PROTEST-001" (ETL生成)
        - 临时指纹: "EVT-2024-12-25-1217480788" (search_events临时生成)
        """
        fingerprint = params.fingerprint
        
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    
                    # 判断指纹类型
                    if fingerprint.startswith('EVT-'):
                        # 临时指纹格式: EVT-YYYY-MM-DD-GID
                        # 解析出 GlobalEventID
                        parts = fingerprint.split('-')
                        if len(parts) >= 4:
                            # 最后一部分是 GID，转为整数
                            try:
                                global_event_id = int(parts[-1])
                            except ValueError:
                                return f"❌ 临时指纹格式错误，无法解析 GID: {fingerprint}"
                        else:
                            return f"❌ 临时指纹格式错误: {fingerprint}"
                        
                        # 直接查询 events_table
                        await cursor.execute(f"""
                            SELECT * FROM {DEFAULT_TABLE}
                            WHERE GlobalEventID = %s
                        """, (global_event_id,))
                        
                        event_row = await cursor.fetchone()
                        if not event_row:
                            return f"⚠️ 未找到事件: GlobalEventID={global_event_id}"
                        
                        event_cols = [desc[0] for desc in cursor.description] if cursor.description else []
                        event_data = dict(zip(event_cols, event_row))
                        
                        # 实时生成显示内容
                        return _format_event_detail_from_raw(event_data, fingerprint, params)
                    
                    else:
                        # 标准指纹，查询指纹表
                        await cursor.execute("""
                            SELECT global_event_id, fingerprint, headline, summary,
                                   key_actors, event_type_label, severity_score,
                                   location_name, location_country
                            FROM event_fingerprints
                            WHERE fingerprint = %s
                        """, (fingerprint,))
                        
                        fp_row = await cursor.fetchone()
                        
                        if fp_row:
                            global_event_id = int(fp_row[0]) if fp_row[0] else None
                            if not global_event_id:
                                return f"⚠️ 指纹数据不完整: {fingerprint}"
                            # 获取完整事件数据
                            await cursor.execute(f"""
                                SELECT * FROM {DEFAULT_TABLE}
                                WHERE GlobalEventID = %s
                            """, (global_event_id,))
                            event_row = await cursor.fetchone()
                            event_cols = [desc[0] for desc in cursor.description] if cursor.description else []
                            event_data = dict(zip(event_cols, event_row)) if event_row else {}
                            
                            # 使用指纹表数据构建输出
                            output = []
                            output.append(f"# 📰 {fp_row[2] or '事件详情'}")
                            output.append(f"**指纹ID**: `{fingerprint}`")
                            output.append(f"**GlobalEventID**: {global_event_id}")
                            output.append(f"**时间**: {event_data.get('SQLDATE', 'N/A')}")
                            output.append(f"**地点**: {fp_row[7] or event_data.get('ActionGeo_FullName', 'N/A')}")
                            output.append(f"**类型**: {fp_row[5] or 'N/A'}")
                            output.append(f"**严重程度**: {'🔴' * int((fp_row[6] or 5) / 2)}")
                            output.append("")
                            
                            if fp_row[3]:  # summary
                                output.append(f"**摘要**: {fp_row[3]}")
                                output.append("")
                            
                            # 参与方
                            if fp_row[4]:  # key_actors
                                try:
                                    actors = json.loads(fp_row[4])
                                    if actors:
                                        output.append(f"**参与方**: {', '.join(actors)}")
                                        output.append("")
                                except:
                                    pass
                            
                            # 原始数据
                            output.append("## 📊 数据指标")
                            output.append(f"- GoldsteinScale: {event_data.get('GoldsteinScale', 'N/A')}")
                            output.append(f"- NumArticles: {event_data.get('NumArticles', 'N/A')}")
                            output.append(f"- AvgTone: {event_data.get('AvgTone', 'N/A')}")
                            output.append("")
                            
                            # 占位符：前因后果分析
                            if params.include_causes or params.include_effects:
                                output.append("## ⏱️ 因果分析")
                                output.append("_（需要运行因果链分析Pipeline）_")
                                output.append("")
                            
                            return "\n".join(output)
                        else:
                            # 尝试用指纹作为 GID 直接查询
                            try:
                                await cursor.execute(f"""
                                    SELECT * FROM {DEFAULT_TABLE}
                                    WHERE GlobalEventID = %s
                                """, (fingerprint,))
                                
                                event_row = await cursor.fetchone()
                                if event_row:
                                    event_cols = [desc[0] for desc in cursor.description] if cursor.description else []
                                    event_data = dict(zip(event_cols, event_row))
                                    return _format_event_detail_from_raw(event_data, fingerprint, params)
                            except:
                                pass
                            
                            return f"⚠️ 事件指纹 `{fingerprint}` 尚未生成或不存在\n\n提示：该指纹可能尚未通过ETL处理，或使用 search_events 重新查找。"
                    
        except Exception as e:
            logger.error(f"获取事件详情失败: {e}")
            return f"❌ 查询失败: {str(e)}"

    @mcp.tool()
    async def get_regional_overview(params: GetRegionalOverviewInput) -> str:
        """
        获取区域态势概览 - 洞察摘要而非原始数据
        
        示例:
        - region="Middle East", time_range="week"
        - region="China", time_range="month", include_risks=true
        """
        # 计算日期范围
        end_date = datetime.now().date()
        days_map = {'day': 1, 'week': 7, 'month': 30, 'quarter': 90, 'year': 365}
        start_date = end_date - timedelta(days=days_map.get(params.time_range, 7))
        
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    # 检查是否有预计算的地区统计
                    await cursor.execute("""
                        SELECT * FROM region_daily_stats
                        WHERE region_code = %s AND date BETWEEN %s AND %s
                        ORDER BY date DESC
                        LIMIT 7
                    """, (params.region.upper(), start_date, end_date))
                    
                    stats_rows = await cursor.fetchall()
                    
                    if stats_rows:
                        # 使用预计算数据
                        return _format_regional_overview_precomputed(
                            stats_rows, params.region, start_date, end_date,
                            params.include_trend, params.include_risks
                        )
                    
                    # 回退：实时查询
                    await cursor.execute(f"""
                        SELECT 
                            COUNT(*) as total,
                            AVG(GoldsteinScale) as avg_goldstein,
                            AVG(AvgTone) as avg_tone,
                            SUM(CASE WHEN GoldsteinScale < -5 THEN 1 ELSE 0 END) as conflicts,
                            SUM(CASE WHEN GoldsteinScale > 5 THEN 1 ELSE 0 END) as cooperation
                        FROM {DEFAULT_TABLE}
                        WHERE SQLDATE BETWEEN %s AND %s
                          AND (ActionGeo_CountryCode = %s OR ActionGeo_FullName LIKE %s)
                    """, (start_date, end_date, params.region.upper(), f'%{params.region}%'))
                    
                    row = await cursor.fetchone()
                    
                    output = []
                    output.append(f"# 🌍 {params.region} 区域态势")
                    output.append(f"**时间范围**: {start_date} ~ {end_date}")
                    output.append("")
                    
                    if row and row[0]:
                        total = row[0]
                        avg_goldstein = row[1] or 0
                        conflicts = row[3] or 0
                        
                        # 态势评分
                        intensity = min(10, max(1, abs(avg_goldstein)))
                        risk_level = _calculate_risk_level(intensity)
                        output.append(f"**态势评分**: {intensity:.1f}/10 {'🔴' if intensity > 7 else '🟡' if intensity > 4 else '🟢'}")
                        output.append(f"**风险等级**: {risk_level}")
                        output.append("")
                        
                        output.append("## 📈 关键指标")
                        output.append(f"- 事件总数: {total}")
                        output.append(f"- 冲突事件: {conflicts} ({conflicts/total*100:.1f}%)")
                        output.append(f"- 平均Goldstein指数: {avg_goldstein:.2f}")
                        output.append("")
                        
                        # 热点事件（实时查询）
                        await cursor.execute(f"""
                            SELECT Actor1Name, Actor2Name, EventCode, GoldsteinScale, 
                                   NumArticles, ActionGeo_FullName, SQLDATE
                            FROM {DEFAULT_TABLE}
                            WHERE SQLDATE BETWEEN %s AND %s
                              AND (ActionGeo_CountryCode = %s OR ActionGeo_FullName LIKE %s)
                            ORDER BY NumArticles * ABS(GoldsteinScale) DESC
                            LIMIT 5
                        """, (start_date, end_date, params.region.upper(), f'%{params.region}%'))
                        
                        hot_events = await cursor.fetchall()
                        if hot_events:
                            output.append("## 🔥 热点事件")
                            for i, evt in enumerate(hot_events, 1):
                                actor1, actor2 = evt[0], evt[1]
                                location = evt[5] or params.region
                                output.append(f"{i}. {actor1} vs {actor2} ({location}) - {evt[4]}篇报道")
                            output.append("")
                    else:
                        output.append("⚠️ 该时间段内未找到相关事件")
                    
                    return "\n".join(output)
                    
        except Exception as e:
            logger.error(f"获取区域概览失败: {e}")
            return f"❌ 查询失败: {str(e)}"

    @mcp.tool()
    async def get_hot_events(params: GetHotEventsInput) -> str:
        """
        获取每日热点事件推荐
        
        示例:
        - date="2024-01-15", top_n=5
        - region_filter="Asia", top_n=10
        """
        # 默认昨天
        query_date = params.date or (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    # 先尝试从预计算表获取
                    await cursor.execute("""
                        SELECT hot_event_fingerprints, top_actors, top_locations
                        FROM daily_summary
                        WHERE date = %s
                    """, (query_date,))
                    
                    result = await cursor.fetchone()
                    
                    events = []
                    
                    if result and result[0]:
                        # 有预计算数据
                        hot_fingerprints = json.loads(result[0]) if isinstance(result[0], str) else result[0]
                        
                        # 获取指纹详情
                        for fp in hot_fingerprints[:params.top_n]:
                            await cursor.execute("""
                                SELECT f.fingerprint, f.headline, f.summary, f.severity_score,
                                       f.location_name, e.SQLDATE, e.GoldsteinScale, e.NumArticles,
                                       e.GlobalEventID, 'standard' as fp_type
                                FROM event_fingerprints f
                                JOIN events_table e ON f.global_event_id = e.GlobalEventID
                                WHERE f.fingerprint = %s
                            """, (fp,))
                            row = await cursor.fetchone()
                            if row:
                                events.append(row)
                    
                    # 如果没有预计算数据，实时查询但尝试匹配指纹表
                    if not events:
                        region_condition = ""
                        query_params = [query_date]
                        
                        if params.region_filter:
                            region_condition = "AND (e.ActionGeo_CountryCode = %s OR e.ActionGeo_FullName LIKE %s)"
                            query_params.extend([params.region_filter.upper(), f'%{params.region_filter}%'])
                        
                        # 先查实时热点，然后LEFT JOIN指纹表获取标准指纹
                        await cursor.execute(f"""
                            SELECT 
                                COALESCE(f.fingerprint, CONCAT('EVT-', e.SQLDATE, '-', CAST(e.GlobalEventID AS CHAR))) as fingerprint,
                                COALESCE(f.headline, CONCAT(
                                    COALESCE(NULLIF(e.Actor1Name, ''), '某方'), 
                                    ' vs ', 
                                    COALESCE(NULLIF(e.Actor2Name, ''), '对方')
                                )) as headline,
                                COALESCE(f.summary, e.ActionGeo_FullName) as summary,
                                COALESCE(f.severity_score, ABS(e.GoldsteinScale)) as severity_score,
                                COALESCE(f.location_name, e.ActionGeo_FullName) as location_name,
                                e.SQLDATE as date,
                                e.GoldsteinScale,
                                e.NumArticles,
                                e.GlobalEventID,
                                CASE WHEN f.fingerprint IS NOT NULL THEN 'standard' ELSE 'temp' END as fp_type
                            FROM {DEFAULT_TABLE} e
                            LEFT JOIN event_fingerprints f ON e.GlobalEventID = f.global_event_id
                            WHERE e.SQLDATE = %s {region_condition}
                            ORDER BY e.NumArticles * ABS(e.GoldsteinScale) DESC
                            LIMIT %s
                        """, tuple(query_params + [params.top_n]))
                        
                        events = await cursor.fetchall()
                    
                    # 格式化输出
                    if not events:
                        return f"📭 {query_date} 未找到热点事件"
                    
                    output = []
                    output.append(f"# 🔥 {query_date} 热点事件 TOP {len(events)}")
                    output.append("")
                    
                    for i, evt in enumerate(events, 1):
                        fingerprint = evt[0]
                        raw_headline = evt[1]
                        # 改进 headline 显示
                        if raw_headline and raw_headline not in ['某方 vs 对方', ' vs ', 'NULL vs NULL']:
                            headline = raw_headline
                        else:
                            # 尝试从指纹或事件类型推断
                            gid = evt[8] if len(evt) > 8 else (fingerprint.split('-')[-1] if '-' in str(fingerprint) else '未知')
                            headline = f"事件 #{gid}"
                        location = evt[4] or "未知地点"
                        severity = evt[3] or 5
                        num_articles = evt[7] or 0
                        fp_type = evt[9] if len(evt) > 9 else 'unknown'
                        
                        # 标记指纹类型
                        fp_badge = "📌" if fp_type == 'standard' else "📝"
                        
                        output.append(f"## {i}. {headline}")
                        output.append(f"**指纹**: {fp_badge} `{fingerprint}` {'(标准)' if fp_type == 'standard' else '(临时)'}")
                        output.append(f"**地点**: {location} | **严重度**: {'🔴' * int(severity / 2)}")
                        output.append(f"**报道量**: {num_articles} 篇")
                        if evt[2] and len(str(evt[2])) > 10:
                            output.append(f"**摘要**: {str(evt[2])[:100]}...")
                        output.append("")
                    
                    output.append("💡 _使用 `get_event_detail` 查看详情_")
                    return "\n".join(output)
                    
        except Exception as e:
            logger.error(f"获取热点事件失败: {e}")
            return f"❌ 查询失败: {str(e)}"

    @mcp.tool()
    async def get_top_events(params: GetTopEventsInput) -> str:
        """
        获取时间段内热度最高的事件
        
        示例:
        - start_date="2024-01-01", end_date="2024-12-31" (2024年全年最热)
        - start_date="2024-06-01", end_date="2024-06-30", region_filter="USA"
        - start_date="2024-01-01", end_date="2024-12-31", event_type="conflict", top_n=20
        """
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    # 构建查询条件
                    conditions = ["SQLDATE BETWEEN %s AND %s"]
                    query_params = [params.start_date, params.end_date]
                    
                    # 区域过滤
                    if params.region_filter:
                        conditions.append("(ActionGeo_CountryCode = %s OR ActionGeo_FullName LIKE %s)")
                        query_params.extend([params.region_filter.upper(), f'%{params.region_filter}%'])
                    
                    # 事件类型过滤
                    if params.event_type == 'conflict':
                        conditions.append("GoldsteinScale < -5")
                    elif params.event_type == 'cooperation':
                        conditions.append("GoldsteinScale > 5")
                    elif params.event_type == 'protest':
                        conditions.append("EventRootCode = '14'")
                    
                    where_clause = " AND ".join(conditions)
                    
                    # 查询热度最高的事件
                    # 热度 = NumArticles * |GoldsteinScale| (报道量 * 冲突强度)
                    await cursor.execute(f"""
                        SELECT 
                            GlobalEventID,
                            SQLDATE,
                            Actor1Name,
                            Actor2Name,
                            ActionGeo_FullName,
                            ActionGeo_CountryCode,
                            EventRootCode,
                            GoldsteinScale,
                            NumArticles,
                            NumSources,
                            AvgTone,
                            SOURCEURL
                        FROM {DEFAULT_TABLE}
                        WHERE {where_clause}
                        ORDER BY NumArticles * ABS(GoldsteinScale) DESC
                        LIMIT %s
                    """, tuple(query_params + [params.top_n]))
                    
                    rows = await cursor.fetchall()
                    
                    if not rows:
                        return f"📭 {params.start_date} ~ {params.end_date} 期间未找到符合条件的事件"
                    
                    # 格式化输出
                    output = []
                    output.append(f"# 🔥 {params.start_date} ~ {params.end_date} 热度最高事件 TOP {len(rows)}")
                    if params.region_filter:
                        output.append(f"**区域过滤**: {params.region_filter}")
                    if params.event_type != 'any':
                        output.append(f"**类型过滤**: {params.event_type}")
                    output.append("")
                    output.append("| 排名 | 指纹ID | 事件 | 热度 | 日期 | 地点 |")
                    output.append("|------|--------|------|------|------|------|")
                    
                    detail_list = []
                    
                    for i, row in enumerate(rows, 1):
                        (gid, date, actor1, actor2, location, country, 
                         event_root, goldstein, articles, sources, tone, url) = row
                        
                        # 生成临时指纹
                        temp_fp = f"EVT-{date}-{gid}"
                        
                        # 事件类型标签
                        type_labels = {
                            '01': '声明', '02': '呼吁', '03': '意向',
                            '04': '磋商', '05': '合作', '06': '援助',
                            '07': '援助', '08': '援助', '09': '让步',
                            '10': '要求', '11': '不满', '12': '拒绝',
                            '13': '威胁', '14': '抗议', '15': '武力',
                            '16': '降级', '17': '强制', '18': '摩擦',
                            '19': '冲突', '20': '攻击'
                        }
                        event_label = type_labels.get(str(event_root)[:2], '事件') if event_root else '事件'
                        
                        # 热度评分
                        hot_score = (articles or 0) * abs(goldstein or 0)
                        
                        actor1 = actor1 or '某国'
                        actor2 = actor2 or '对方'
                        location_short = (location or '未知')[:15]  # 缩短地点
                        
                        # 简化的标题
                        title = f"{actor1[:10]} vs {actor2[:10]}"
                        
                        # 表格行
                        output.append(f"| {i} | `{temp_fp}` | {title} [{event_label}] | {hot_score:.0f} | {date} | {location_short} |")
                        
                        # 详细信息（用于后续展开）
                        detail_list.append({
                            'rank': i,
                            'fingerprint': temp_fp,
                            'title': title,
                            'event_label': event_label,
                            'date': date,
                            'location': location,
                            'hot_score': hot_score,
                            'articles': articles,
                            'goldstein': goldstein,
                            'tone': tone
                        })
                    
                    output.append("")
                    output.append("## 详细信息")
                    output.append("")
                    
                    for d in detail_list[:5]:  # 只展示前5个详情
                        output.append(f"### {d['rank']}. {d['title']} [{d['event_label']}]")
                        output.append(f"- **指纹**: `{d['fingerprint']}` ← 复制此ID查看详情")
                        output.append(f"- **时间**: {d['date']} | **地点**: {d['location']}")
                        output.append(f"- **热度**: {d['hot_score']:.0f} (报道{d['articles']}篇 × 强度{abs(d['goldstein'] or 0):.1f})")
                        output.append(f"- **Goldstein**: {d['goldstein']:.2f} | **Tone**: {d['tone']:.2f}")
                        output.append("")
                    
                    if len(detail_list) > 5:
                        output.append(f"_... 还有 {len(detail_list) - 5} 个事件，使用指纹ID查看详情_")
                        output.append("")
                    
                    output.append("💡 **查看事件详情**: `get_event_detail(fingerprint='EVT-YYYY-MM-DD-GID')`")
                    return "\n".join(output)
                    
        except Exception as e:
            logger.error(f"获取Top事件失败: {e}")
            return f"❌ 查询失败: {str(e)}"

    @mcp.tool()
    async def get_daily_brief(params: GetDailyBriefInput) -> str:
        """
        获取每日简报 - 类似新闻摘要
        
        示例:
        - date="2024-01-15", format="summary"
        - region_focus="global", format="executive"
        """
        query_date = params.date or (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    # 尝试从预计算表获取
                    await cursor.execute("""
                        SELECT *
                        FROM daily_summary
                        WHERE date = %s
                    """, (query_date,))
                    
                    brief = await cursor.fetchone()
                    cols = [desc[0] for desc in cursor.description] if cursor.description else []
                    
                    if brief:
                        data = dict(zip(cols, brief))
                    else:
                        # 实时计算
                        await cursor.execute(f"""
                            SELECT 
                                COUNT(*) as total_events,
                                SUM(CASE WHEN GoldsteinScale < -5 THEN 1 ELSE 0 END) as conflict_events,
                                SUM(CASE WHEN GoldsteinScale > 5 THEN 1 ELSE 0 END) as cooperation_events,
                                AVG(GoldsteinScale) as avg_goldstein,
                                AVG(AvgTone) as avg_tone
                            FROM {DEFAULT_TABLE}
                            WHERE SQLDATE = %s
                        """, (query_date,))
                        
                        row = await cursor.fetchone()
                        data = {
                            'total_events': row[0] if row else 0,
                            'conflict_events': row[1] if row else 0,
                            'cooperation_events': row[2] if row else 0,
                            'avg_goldstein': row[3] if row else 0,
                            'avg_tone': row[4] if row else 0,
                            'top_actors': '[]',
                            'top_locations': '[]'
                        }
                    
                    output = []
                    output.append(f"# 📰 {query_date} 全球事件简报")
                    output.append("")
                    
                    # 一句话总结
                    total = data.get('total_events', 0)
                    conflict = data.get('conflict_events', 0)
                    conflict_pct = (conflict / max(total, 1)) * 100
                    goldstein = data.get('avg_goldstein', 0) or 0
                    
                    output.append(f"📊 **概览**: 今日共记录 **{total:,}** 起国际事件，")
                    output.append(f"冲突事件 {conflict} 起 ({conflict_pct:.1f}%)，")
                    output.append(f"平均Goldstein指数为 {goldstein:.2f}")
                    output.append("")
                    
                    # 根据format返回不同详细程度
                    if params.format == 'summary':
                        # 简洁版
                        if brief and data.get('hot_event_fingerprints'):
                            hot_fps = json.loads(data['hot_event_fingerprints']) if isinstance(data['hot_event_fingerprints'], str) else data['hot_event_fingerprints']
                            output.append("## 🔥 今日热点")
                            for fp in hot_fps[:3]:
                                output.append(f"- `{fp}`")
                            output.append("")
                        
                        output.append("💡 _使用 `get_hot_events` 获取详细热点信息_")
                        
                    elif params.format == 'detailed':
                        # 详细版
                        if data.get('top_actors'):
                            try:
                                actors = json.loads(data['top_actors']) if isinstance(data['top_actors'], str) else data['top_actors']
                                if actors:
                                    output.append("## 👥 主要参与方")
                                    for actor in actors[:5]:
                                        name = actor.get('name', 'Unknown')
                                        count = actor.get('count', 0)
                                        output.append(f"- {name}: {count} 次")
                                    output.append("")
                            except:
                                pass
                        
                        if data.get('top_locations'):
                            try:
                                locations = json.loads(data['top_locations']) if isinstance(data['top_locations'], str) else data['top_locations']
                                if locations:
                                    output.append("## 🌍 活跃地区")
                                    for loc in locations[:5]:
                                        name = loc.get('name', 'Unknown')
                                        count = loc.get('count', 0)
                                        output.append(f"- {name}: {count} 起")
                                    output.append("")
                            except:
                                pass
                    
                    elif params.format == 'executive':
                        # 执行摘要版
                        output.append("## 📋 执行摘要")
                        trend = "⚠️ 冲突趋势上升" if goldstein < -3 else "✅ 局势相对稳定"
                        output.append(f"- {trend}")
                        output.append(f"- 事件密度: {total/1000:.1f}K/天")
                        output.append("")
                    
                    return "\n".join(output)
                    
        except Exception as e:
            logger.error(f"获取每日简报失败: {e}")
            return f"❌ 查询失败: {str(e)}"

    logger.info("✅ 核心工具V2已注册 (5个工具)")


# ============================================================================
# 辅助函数
# ============================================================================

def _parse_time_hint(time_hint: Optional[str]) -> tuple:
    """解析时间提示为日期范围"""
    end = datetime.now().date()
    
    if not time_hint:
        # 默认最近7天
        start = end - timedelta(days=7)
    elif time_hint == 'today':
        start = end
    elif time_hint == 'yesterday':
        start = end - timedelta(days=1)
        end = start
    elif time_hint == 'this_week':
        start = end - timedelta(days=7)
    elif time_hint == 'this_month':
        start = end - timedelta(days=30)
    elif len(time_hint) == 7:  # YYYY-MM
        start = datetime.strptime(time_hint + "-01", '%Y-%m-%d').date()
        end = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    else:
        try:
            start = datetime.strptime(time_hint, '%Y-%m-%d').date()
            end = start
        except:
            start = end - timedelta(days=7)
    
    return start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')


def _calculate_risk_level(intensity: float) -> str:
    """计算风险等级"""
    if intensity > 7:
        return "极高"
    elif intensity > 5:
        return "高"
    elif intensity > 3:
        return "中"
    else:
        return "低"


def _format_search_results_v2(rows: list, columns: list, original_query: str) -> str:
    """格式化搜索结果V2"""
    if not rows:
        return f"❌ 未找到与 '{original_query}' 相关的事件"
    
    output = [f"# 🔍 搜索结果: '{original_query}'", ""]
    output.append(f"找到 {len(rows)} 个相关事件:\n")
    
    for i, row in enumerate(rows, 1):
        data = dict(zip(columns, row))
        
        actor1 = data.get('Actor1Name', '') or '某国'
        actor2 = data.get('Actor2Name', '') or '对方'
        location = data.get('ActionGeo_FullName', '') or '未知地点'
        date = data.get('SQLDATE', 'N/A')
        goldstein = data.get('GoldsteinScale', 0) or 0
        articles = data.get('NumArticles', 0) or 0
        event_root = str(data.get('EventRootCode', ''))[:2]
        
        # 事件类型标签
        type_labels = {
            '01': '声明', '02': '呼吁', '03': '意向',
            '04': '磋商', '05': '合作', '06': '援助',
            '07': '援助', '08': '援助', '09': '让步',
            '10': '要求', '11': '不满', '12': '拒绝',
            '13': '威胁', '14': '抗议', '15': '武力展示',
            '16': '降级', '17': '强制', '18': '摩擦',
            '19': '冲突', '20': '攻击'
        }
        event_label = type_labels.get(event_root, '事件')
        
        # 生成临时指纹
        gid = data.get('GlobalEventID', '0')
        temp_fp = f"EVT-{date}-{gid}"
        
        output.append(f"## {i}. {actor1} vs {actor2} [{event_label}]")
        output.append(f"**指纹**: `{temp_fp}`")
        output.append(f"**时间**: {date} | **地点**: {location}")
        output.append(f"**冲突指数**: {goldstein:.1f} | **报道量**: {articles} 篇")
        output.append("")
    
    output.append("💡 _提示：使用 `get_event_detail` 查看事件详情_")
    return "\n".join(output)


def _format_regional_overview_precomputed(rows: list, region: str, 
                                          start_date, end_date,
                                          include_trend: bool, 
                                          include_risks: bool) -> str:
    """格式化预计算的区域概览"""
    output = []
    output.append(f"# 🌍 {region} 区域态势 (预计算数据)")
    output.append(f"**时间范围**: {start_date} ~ {end_date}")
    output.append("")
    
    # 计算平均值
    total_events = sum(r[4] for r in rows)  # event_count
    avg_conflict = sum(r[5] for r in rows if r[5]) / len(rows) if rows else 0
    
    intensity = min(10, max(1, avg_conflict))
    risk_level = _calculate_risk_level(intensity)
    
    output.append(f"**态势评分**: {intensity:.1f}/10 {'🔴' if intensity > 7 else '🟡' if intensity > 4 else '🟢'}")
    output.append(f"**风险等级**: {risk_level}")
    output.append("")
    
    output.append("## 📈 关键指标")
    output.append(f"- 事件总数: {total_events}")
    output.append(f"- 日均事件: {total_events / len(rows):.1f}")
    output.append(f"- 平均冲突强度: {avg_conflict:.2f}")
    output.append("")
    
    if include_trend and len(rows) > 1:
        output.append("## 📊 趋势")
        # 简单趋势判断
        first_half = sum(r[5] for r in rows[:len(rows)//2] if r[5]) / (len(rows)//2) if rows else 0
        second_half = sum(r[5] for r in rows[len(rows)//2:] if r[5]) / (len(rows) - len(rows)//2) if rows else 0
        
        if second_half > first_half * 1.1:
            output.append("- 冲突强度: 📈 上升趋势")
        elif second_half < first_half * 0.9:
            output.append("- 冲突强度: 📉 下降趋势")
        else:
            output.append("- 冲突强度: ➡️ 相对稳定")
        output.append("")
    
    if include_risks:
        output.append("## ⚠️ 风险评估")
        if intensity > 7:
            output.append("- **高风险**: 冲突强度持续高位")
        elif intensity > 5:
            output.append("- **中风险**: 局部冲突时有发生")
        else:
            output.append("- **低风险**: 总体局势稳定")
        output.append("")
    
    return "\n".join(output)


def _format_event_detail_from_raw(event_data: dict, fingerprint: str, params) -> str:
    """
    从原始事件数据格式化详情（无指纹表数据时）
    """
    actor1 = event_data.get('Actor1Name', '') or '某国'
    actor2 = event_data.get('Actor2Name', '') or '对方'
    location = event_data.get('ActionGeo_FullName', '') or '未知地点'
    date = event_data.get('SQLDATE', 'N/A')
    goldstein = event_data.get('GoldsteinScale', 0) or 0
    articles = event_data.get('NumArticles', 0) or 0
    tone = event_data.get('AvgTone', 0) or 0
    gid = event_data.get('GlobalEventID', 'N/A')
    event_root = str(event_data.get('EventRootCode', ''))[:2]
    country = event_data.get('ActionGeo_CountryCode', 'XX')
    
    # 事件类型标签
    type_labels = {
        '01': '外交声明', '02': '外交呼吁', '03': '政策意向',
        '04': '外交磋商', '05': '参与合作', '06': '物资援助',
        '07': '人员援助', '08': '保护援助', '09': '让步缓和',
        '10': '提出要求', '11': '表达不满', '12': '拒绝反对',
        '13': '威胁警告', '14': '抗议示威', '15': '展示武力',
        '16': '关系降级', '17': '强制胁迫', '18': '军事摩擦',
        '19': '大规模冲突', '20': '武装攻击'
    }
    event_label = type_labels.get(event_root, '其他事件')
    
    # 严重度
    severity = min(10, max(1, abs(goldstein) * 2))
    if articles > 100:
        severity += 1
    severity = min(10, severity)
    
    output = []
    output.append(f"# 📰 {actor1} vs {actor2} [{event_label}]")
    output.append(f"**指纹ID**: `{fingerprint}`")
    output.append(f"**GlobalEventID**: {gid}")
    output.append(f"**时间**: {date}")
    output.append(f"**地点**: {location} ({country})")
    output.append(f"**类型**: {event_label}")
    output.append(f"**严重程度**: {'🔴' * int(severity / 2)}")
    output.append("")
    
    # 实时生成摘要
    intensity_desc = "轻微"
    if abs(goldstein) > 7:
        intensity_desc = "严重"
    elif abs(goldstein) > 4:
        intensity_desc = "中等"
    
    coverage = ""
    if articles > 100:
        coverage = f"，受到广泛报道({articles}篇)"
    elif articles > 10:
        coverage = f"，受到一定报道({articles}篇)"
    
    summary = f"{actor1}与{actor2}在{location}发生{intensity_desc}互动{coverage}。"
    output.append(f"**摘要**: {summary}")
    output.append("")
    
    if actor1 != '某国' or actor2 != '对方':
        actors = [a for a in [actor1, actor2] if a not in ['某国', '对方']]
        if actors:
            output.append(f"**参与方**: {', '.join(actors)}")
            output.append("")
    
    # 原始数据
    output.append("## 📊 数据指标")
    output.append(f"- GoldsteinScale: {goldstein:.2f}")
    output.append(f"- NumArticles: {articles}")
    output.append(f"- AvgTone: {tone:.2f}")
    output.append(f"- QuadClass: {event_data.get('QuadClass', 'N/A')}")
    output.append("")
    
    # 占位符
    if params.include_causes or params.include_effects:
        output.append("## ⏱️ 因果分析")
        output.append("_（需要运行因果链分析Pipeline）_")
        output.append("")
    
    if params.include_related:
        output.append("## 🔗 相关事件")
        output.append("_（需要事件相似度计算）_")
        output.append("")
    
    return "\n".join(output)

"""
优化版 GDELT MCP Tools

整合缓存、流式、并行等优化技术。
"""

import json
from typing import Optional, Any
from datetime import datetime

from pydantic import BaseModel, Field

from app.services.gdelt_optimized import GDELTServiceOptimized, get_optimized_service
from app.cache import query_cache


def sanitize_text(text: Any) -> str:
    """清理文本中的非法 UTF-8 字符"""
    if text is None:
        return "N/A"
    text = str(text)
    # 移除 surrogate pairs
    text = text.encode('utf-8', 'ignore').decode('utf-8')
    # 替换控制字符
    import unicodedata
    text = ''.join(
        char for char in text 
        if unicodedata.category(char)[0] != 'C' or char in '\n\t\r'
    )
    # 移除 null bytes
    text = text.replace('\x00', '')
    return text


# ==================== 输入模型 ====================

class DashboardInput(BaseModel):
    """仪表盘数据查询"""
    start_date: str = Field(..., description="开始日期 (YYYY-MM-DD)", pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str = Field(..., description="结束日期 (YYYY-MM-DD)", pattern=r"^\d{4}-\d{2}-\d{2}$")


class TimeSeriesInput(BaseModel):
    """时间序列分析"""
    start_date: str = Field(..., description="开始日期 (YYYY-MM-DD)")
    end_date: str = Field(..., description="结束日期 (YYYY-MM-DD)")
    granularity: str = Field(default="day", description="粒度: day/week/month")


class GeoHeatmapInput(BaseModel):
    """地理热力图"""
    start_date: str = Field(..., description="开始日期 (YYYY-MM-DD)")
    end_date: str = Field(..., description="结束日期 (YYYY-MM-DD)")
    precision: int = Field(default=2, description="坐标精度 (1-3)", ge=1, le=3)


class StreamQueryInput(BaseModel):
    """流式查询"""
    actor_name: str = Field(..., description="参与方名称（模糊匹配）")
    start_date: Optional[str] = Field(None, description="开始日期")
    end_date: Optional[str] = Field(None, description="结束日期")
    max_results: int = Field(default=100, description="最大返回数量", le=1000)


# ==================== 工具注册函数 ====================

def create_optimized_tools(mcp):
    """创建优化版 GDELT 工具"""
    
    service = GDELTServiceOptimized()
    
    # ==================== 优化版 Tools ====================
    
    @mcp.tool()
    async def get_dashboard(params: DashboardInput) -> str:
        """
        【优化】仪表盘数据 - 并发获取多维度统计
        
        同时返回：
        - 每日趋势
        - Top 参与方
        - 地理分布
        - 事件类型分布
        - 综合统计
        
        比串行查询快 3-5 倍。
        """
        try:
            dashboard = await service.get_dashboard_data(
                params.start_date,
                params.end_date
            )
            
            # 格式化输出
            lines = ["# 📊 仪表盘数据\n"]
            
            # 摘要
            summary = dashboard.get("summary_stats", {})
            if "data" in summary and summary["data"]:
                s = summary["data"][0]
                lines.append(f"**统计周期**: {params.start_date} 至 {params.end_date}")
                lines.append(f"- 总事件数: {s.get('total_events', 0):,}")
                lines.append(f"- 独特参与方: {s.get('unique_actors', 0):,}")
                lines.append(f"- 平均 Goldstein: {s.get('avg_goldstein', 0):.2f}")
                lines.append(f"- 平均 Tone: {s.get('avg_tone', 0):.2f}")
                lines.append("")
            
            # 每日趋势（简化显示）
            daily = dashboard.get("daily_trend", {})
            if "data" in daily:
                lines.append("## 📈 每日趋势（前 7 天）")
                for row in daily["data"][:7]:
                    lines.append(f"- {row.get('SQLDATE')}: {row.get('cnt')} 事件")
                lines.append("")
            
            # Top 参与方
            actors = dashboard.get("top_actors", {})
            if "data" in actors:
                lines.append("## 🎭 Top 5 参与方")
                for i, row in enumerate(actors["data"][:5], 1):
                    lines.append(f"{i}. {row.get('Actor1Name')}: {row.get('cnt')} 事件")
                lines.append("")
            
            # 性能信息
            total_time = sum(
                v.get("elapsed_ms", 0) 
                for v in dashboard.values() 
                if isinstance(v, dict)
            )
            lines.append(f"\n*查询耗时: {total_time:.0f}ms (并行优化)*")
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"❌ 查询失败: {str(e)}"
    
    
    @mcp.tool()
    async def analyze_time_series(params: TimeSeriesInput) -> str:
        """
        【优化】高级时间序列分析 - 数据库端聚合
        
        返回按日/周/月聚合的统计数据，包含：
        - 事件数量
        - 冲突/合作比例
        - 统计指标（均值、标准差）
        - 最活跃参与方（JSON）
        """
        try:
            results = await service.analyze_time_series_advanced(
                params.start_date,
                params.end_date,
                params.granularity
            )
            
            if not results:
                return "未找到数据"
            
            lines = [f"# 📈 时间序列分析 ({params.granularity})\n"]
            
            for row in results:
                period = row.get("period")
                lines.append(f"### {period}")
                lines.append(f"- 事件数: {row.get('event_count', 0):,}")
                lines.append(f"- 冲突比例: {row.get('conflict_pct', 0)}%")
                lines.append(f"- 合作比例: {row.get('cooperation_pct', 0)}%")
                lines.append(f"- 平均 Goldstein: {row.get('avg_goldstein', 0)}")
                lines.append("")
            
            lines.append(f"*共 {len(results)} 个时间周期*")
            return "\n".join(lines)
            
        except Exception as e:
            return f"❌ 分析失败: {str(e)}"
    
    
    @mcp.tool()
    async def get_geo_heatmap(params: GeoHeatmapInput) -> str:
        """
        【优化】地理热力图数据 - 网格聚合
        
        将相近坐标聚合，返回热力图可用数据。
        适合前端地图可视化。
        """
        try:
            results = await service.get_geo_heatmap(
                params.start_date,
                params.end_date,
                params.precision
            )
            
            if not results:
                return "未找到地理数据"
            
            # 返回 JSON 格式，方便前端使用
            heatmap_data = [
                {
                    "lat": float(row["lat"]),
                    "lng": float(row["lng"]),
                    "intensity": int(row["intensity"]),
                    "avg_conflict": float(row["avg_conflict"]) if row["avg_conflict"] else None,
                    "location": row["sample_location"]
                }
                for row in results[:100]  # 限制返回数量
            ]
            
            return f"""# 🗺️ 地理热力图数据

**时间范围**: {params.start_date} 至 {params.end_date}
**精度**: {params.precision} 位小数
**热点数量**: {len(heatmap_data)}

```json
{json.dumps(heatmap_data[:10], indent=2, ensure_ascii=False)}
```

*完整数据共 {len(heatmap_data)} 条*
"""
            
        except Exception as e:
            return f"❌ 查询失败: {str(e)}"
    
    
    @mcp.tool()
    async def stream_query_events(params: StreamQueryInput) -> str:
        """
        【优化】流式查询 - 处理大量数据
        
        使用生成器逐步读取，内存占用稳定。
        适合处理上万条结果。
        """
        try:
            lines = [f"# 🔍 流式查询结果: {params.actor_name}\n"]
            lines.append("| 日期 | Actor1 | Actor2 | Goldstein | Tone | 位置 |")
            lines.append("|------|--------|--------|-----------|------|------|")
            
            count = 0
            async for row in service.stream_events_by_actor(
                params.actor_name,
                params.start_date,
                params.end_date
            ):
                # 清理所有文本字段
                lines.append(
                    f"| {sanitize_text(row.get('SQLDATE'))} | "
                    f"{sanitize_text(row.get('Actor1Name', 'N/A'))[:15]} | "
                    f"{sanitize_text(row.get('Actor2Name', 'N/A'))[:15]} | "
                    f"{sanitize_text(row.get('GoldsteinScale', 'N/A'))} | "
                    f"{sanitize_text(row.get('AvgTone', 'N/A'))} | "
                    f"{sanitize_text(row.get('ActionGeo_FullName', 'N/A'))[:20]} |"
                )
                
                count += 1
                if count >= params.max_results:
                    lines.append("| ... | (更多结果截断) | ... | ... | ... | ... |")
                    break
            
            lines.append(f"\n*共返回 {count} 条结果 (流式读取)*")
            return "\n".join(lines)
            
        except Exception as e:
            return f"❌ 流式查询失败: {str(e)}"
    
    
    @mcp.tool()
    async def get_cache_stats() -> str:
        """
        【诊断】查看查询缓存统计信息
        
        监控查询缓存的命中率和性能。
        """
        stats = query_cache.get_stats()
        
        # 命中率评估
        hit_rate_str = stats['hit_rate'].rstrip('%')
        try:
            hit_rate = float(hit_rate_str)
            if hit_rate >= 80:
                evaluation = "✅ 命中率优秀 (≥80%)"
            elif hit_rate >= 50:
                evaluation = "⚠️ 命中率一般 (50-80%)"
            else:
                evaluation = "❌ 命中率较低 (<50%)，建议检查缓存配置"
        except:
            evaluation = "🤷 暂无足够数据评估"
        
        return f"""# 📊 查询缓存统计

| 指标 | 值 |
|------|-----|
| 缓存条目数 | {stats['size']} / {stats['maxsize']} |
| 命中次数 | {stats['hits']:,} |
| 未命中次数 | {stats['misses']:,} |
| 命中率 | {stats['hit_rate']} |
| LRU 淘汰次数 | {stats['evictions']:,} |

**评估**: {evaluation}

**建议**:
- 命中率 > 80%: 缓存配置良好
- 命中率 < 50%: 考虑增加缓存时间或减少缓存容量
- 条目数接近上限: 考虑增加 maxsize
"""
    
    
    @mcp.tool()
    async def clear_cache() -> str:
        """清除所有查询缓存"""
        count = await query_cache.clear()
        return f"✅ 已清除 {count} 个缓存条目"

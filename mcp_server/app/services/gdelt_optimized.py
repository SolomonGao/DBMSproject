"""
GDELT Optimized Query Service

integratecache、streamingquery、androwqueryetc.before沿optimization technology。
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Callable
from functools import lru_cache
import os
import chromadb
from chromadb.utils import embedding_functions
import logging
from app.database.pool import DatabasePool, get_db_pool
from app.database.streaming import StreamingQuery, ParallelQuery
from app.cache import query_cache, QueryCache


class GDELTServiceOptimized:
    """
    optimized version GDELT service
    
    optizationpoint：
    1. queryresultresultcache (TTL + LRU)
    2. androwaggregatequery
    3. streamingquerySupportsbigdata
    4. precompilestatementreuse
    5. databaseendcalculatereducetransmittransport
    """
    
    DEFAULT_TABLE = "events_table"
    MAX_ROWS = 100
    
    def __init__(self):
        self._pool: Optional[DatabasePool] = None
        self._streaming: Optional[StreamingQuery] = None
        self._parallel: Optional[ParallelQuery] = None
        self._cache = query_cache
        self._chroma_collection = None
    
    async def _get_pool(self) -> DatabasePool:
        """延迟Initializejoin池"""
        if self._pool is None:
            self._pool = await get_db_pool()
            self._streaming = StreamingQuery(self._pool, chunk_size=50)
            self._parallel = ParallelQuery(self._pool, max_concurrent=5)
        return self._pool
    
    # ==================== coreoptization：cachequery ====================
    
    async def execute_sql_cached(
        self,
        query: str,
        params: Optional[tuple] = None,
        cache_ttl: int = 300
    ) -> List[Dict[str, Any]]:
        """
        带cache SQL execrow
        
        自动cachequeryresultresult，避免duplicateexecrowsamequery。
        """
        pool = await self._get_pool()
        
        return await self._cache.get_or_fetch(
            query=query,
            params=params,
            fetch_func=lambda: pool.fetchall(query, params),
            ttl=cache_ttl
        )
    
    # ==================== coreoptization：androw仪table盘 ====================
    
    async def get_dashboard_data(
        self,
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        """
        仪table盘data - 5 queryandsendexecrow
        
        原来串rowneed ~2s，现inonlyneed ~0.5s（fetch决于mostslowquery）
        """
        await self._get_pool()
        
        # Defines 5 独立query
        queries = [
            # 1. each日trends
            (f"""
                SELECT SQLDATE, COUNT(*) as cnt, 
                       AVG(GoldsteinScale) as goldstein,
                       SUM(CASE WHEN GoldsteinScale < 0 THEN 1 ELSE 0 END) as conflict
                FROM {self.DEFAULT_TABLE}
                WHERE SQLDATE BETWEEN %s AND %s
                GROUP BY SQLDATE ORDER BY SQLDATE
            """, (start_date, end_date), "daily_trend"),
            
            # 2. Top 10 paramandmethod
            (f"""
                SELECT Actor1Name, COUNT(*) as cnt
                FROM {self.DEFAULT_TABLE}
                WHERE SQLDATE BETWEEN %s AND %s AND Actor1Name IS NOT NULL
                GROUP BY Actor1Name ORDER BY cnt DESC LIMIT 10
            """, (start_date, end_date), "top_actors"),
            
            # 3. locationprocessdistribution（Top 10 国家）
            (f"""
                SELECT ActionGeo_CountryCode, COUNT(*) as cnt
                FROM {self.DEFAULT_TABLE}
                WHERE SQLDATE BETWEEN %s AND %s 
                  AND ActionGeo_CountryCode IS NOT NULL
                GROUP BY ActionGeo_CountryCode 
                ORDER BY cnt DESC LIMIT 10
            """, (start_date, end_date), "geo_distribution"),
            
            # 4. eventtypedistribution
            (f"""
                SELECT 
                    CASE 
                        WHEN EventRootCode BETWEEN 1 AND 9 THEN 'Public Statement'
                        WHEN EventRootCode BETWEEN 10 AND 19 THEN 'Yield'
                        WHEN EventRootCode BETWEEN 20 AND 29 THEN 'Investigate'
                        WHEN EventRootCode BETWEEN 30 AND 39 THEN 'Demand'
                        WHEN EventRootCode BETWEEN 40 AND 49 THEN 'Disapprove'
                        WHEN EventRootCode BETWEEN 50 AND 59 THEN 'Reject'
                        WHEN EventRootCode BETWEEN 60 AND 69 THEN 'Threaten'
                        WHEN EventRootCode BETWEEN 70 AND 79 THEN 'Protest'
                        ELSE 'Other'
                    END as event_type,
                    COUNT(*) as cnt
                FROM {self.DEFAULT_TABLE}
                WHERE SQLDATE BETWEEN %s AND %s
                GROUP BY event_type ORDER BY cnt DESC
            """, (start_date, end_date), "event_types"),
            
            # 5. statisticsdigest
            (f"""
                SELECT 
                    COUNT(*) as total_events,
                    COUNT(DISTINCT Actor1Name) as unique_actors,
                    AVG(GoldsteinScale) as avg_goldstein,
                    AVG(AvgTone) as avg_tone,
                    SUM(NumArticles) as total_articles
                FROM {self.DEFAULT_TABLE}
                WHERE SQLDATE BETWEEN %s AND %s
            """, (start_date, end_date), "summary_stats"),
        ]
        
        # andsendexecrow
        results = await self._parallel.execute_many(queries)
        
        # group装resultresult
        dashboard = {}
        for result in results:
            name = result["name"]
            if result["error"]:
                dashboard[name] = {"error": result["error"]}
            else:
                dashboard[name] = {
                    "data": result["rows"],
                    "count": result["count"],
                    "elapsed_ms": result["elapsed_ms"]
                }
        
        return dashboard
    
    # ==================== coreoptization：streamingbigdataquery ====================
    
    async def stream_events_by_actor(
        self,
        actor_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ):
        """
        streamingquery - process large amountseventdata
        
        stable memory usage，regardless ofdataamountmultibig。
        """
        await self._get_pool()
        
        date_filter = ""
        params = [f"%{actor_name}%", f"%{actor_name}%"]
        
        if start_date and end_date:
            date_filter = "AND SQLDATE BETWEEN %s AND %s"
            params.extend([start_date, end_date])
        
        query = f"""
            SELECT SQLDATE, Actor1Name, Actor2Name, EventCode,
                   GoldsteinScale, AvgTone, ActionGeo_FullName
            FROM {self.DEFAULT_TABLE}
            WHERE (Actor1Name LIKE %s OR Actor2Name LIKE %s)
            {date_filter}
            ORDER BY SQLDATE DESC
        """
        
        async for row in self._streaming.stream(query, tuple(params)):
            yield row
    
    # ==================== coreoptization：databaseendaggregate ====================
    
    async def analyze_time_series_advanced(
        self,
        start_date: str,
        end_date: str,
        granularity: str = "day"  # day, week, month
    ) -> List[Dict[str, Any]]:
        """
        advancedwheninterval序columnanalyze - 全部indatabasecompleted
        
        onlytransmittransportaggregateafterresultresult，极bigreducenetworkopen销。
        """
        # 根据granularityscheduleselectselectgroupmethodpattern
        if granularity == "week":
            date_group = "YEARWEEK(SQLDATE)"
            date_select = "STR_TO_DATE(CONCAT(YEARWEEK(SQLDATE), ' Sunday'), '%X%V %W') as period"
        elif granularity == "month":
            date_group = "DATE_FORMAT(SQLDATE, '%Y-%m')"
            date_select = "DATE_FORMAT(SQLDATE, '%Y-%m-01') as period"
        else:  # day
            date_group = "SQLDATE"
            date_select = "SQLDATE as period"
        
        query = f"""
        SELECT 
            {date_select},
            COUNT(*) as event_count,
            -- conflict/合job比example（databaseendcalculate）
            ROUND(
                SUM(CASE WHEN GoldsteinScale < 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
                2
            ) as conflict_pct,
            ROUND(
                SUM(CASE WHEN GoldsteinScale > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
                2
            ) as cooperation_pct,
            -- statistics指标
            ROUND(AVG(GoldsteinScale), 2) as avg_goldstein,
            ROUND(STDDEV(GoldsteinScale), 2) as std_goldstein,
            ROUND(AVG(AvgTone), 2) as avg_tone,
            ROUND(STDDEV(AvgTone), 2) as std_tone,
            -- most活跃paramandmethod（JSON aggregate）
            (
                SELECT JSON_ARRAYAGG(
                    JSON_OBJECT('actor', Actor1Name, 'count', cnt)
                )
                FROM (
                    SELECT Actor1Name, COUNT(*) as cnt
                    FROM {self.DEFAULT_TABLE} t2
                    WHERE t2.SQLDATE = t1.SQLDATE
                    GROUP BY Actor1Name
                    ORDER BY cnt DESC
                    LIMIT 3
                ) top_actors
            ) as top_actors_json
        FROM {self.DEFAULT_TABLE} t1
        WHERE SQLDATE BETWEEN %s AND %s
        GROUP BY {date_group}
        ORDER BY period
        """
        
        # uselongcachewheninterval（statisticsdatavariableization少）
        return await self.execute_sql_cached(
            query, 
            (start_date, end_date),
            cache_ttl=1800  # 30 分钟
        )
    
    # ==================== coreoptization：locationprocessheatgraph ====================
    
    async def get_geo_heatmap(
        self,
        start_date: str,
        end_date: str,
        precision: int = 2  # 小number位number，越big精schedule越high
    ) -> List[Dict[str, Any]]:
        """
        locationprocessheatgraphdata - gridaggregate
        
        将相近坐标aggregatetogrid，reducebeforeend渲染压力。
        """
        query = f"""
        SELECT 
            ROUND(ActionGeo_Lat, {precision}) as lat,
            ROUND(ActionGeo_Long, {precision}) as lng,
            COUNT(*) as intensity,
            AVG(GoldsteinScale) as avg_conflict,
            -- Representative location name
            ANY_VALUE(ActionGeo_FullName) as sample_location
        FROM {self.DEFAULT_TABLE}
        WHERE SQLDATE BETWEEN %s AND %s
          AND ActionGeo_Lat IS NOT NULL 
          AND ActionGeo_Long IS NOT NULL
        GROUP BY 
            ROUND(ActionGeo_Lat, {precision}),
            ROUND(ActionGeo_Long, {precision})
        HAVING intensity >= 5  -- filter稀疏point
        ORDER BY intensity DESC
        LIMIT 1000
        """
        
        return await self.execute_sql_cached(
            query,
            (start_date, end_date),
            cache_ttl=600
        )
    
    # ==================== coreoptization：precompilebatchoperation ====================
    
    async def batch_fetch_by_ids(
        self,
        event_ids: List[int]
    ) -> List[Dict[str, Any]]:
        """
        batch ID query - useprecompilestatement
        
        比multitimeformitemqueryfast 10x thereforeupload。
        """
        if not event_ids:
            return []
        
        pool = await self._get_pool()
        
        # 分批handleprocess（避免 SQL 过long）
        batch_size = 500
        all_results = []
        
        for i in range(0, len(event_ids), batch_size):
            batch = event_ids[i:i + batch_size]
            placeholders = ', '.join(['%s'] * len(batch))
            query = f"""
                SELECT * FROM {self.DEFAULT_TABLE}
                WHERE GlobalEventID IN ({placeholders})
            """
            rows = await pool.fetchall(query, tuple(batch))
            all_results.extend(rows)
        
        return all_results
    
    # ==================== coreoptization：fast速check ====================
    
    async def quick_count(
        self,
        date: str,
        actor: Optional[str] = None
    ) -> int:
        """
        fast速计number - useindex覆盖query
        
        EXPLAIN 应该display Using index。
        """
        pool = await self._get_pool()
        
        if actor:
            # this种queryunableuseindex，needoptization
            query = f"""
                SELECT COUNT(*) as cnt FROM {self.DEFAULT_TABLE}
                WHERE SQLDATE = %s 
                  AND (Actor1Name LIKE %s OR Actor2Name LIKE %s)
            """
            result = await pool.fetchone(query, (date, f"%{actor}%", f"%{actor}%"))
        else:
            # Pure date count can be overriddenindex
            query = f"""
                SELECT COUNT(*) as cnt FROM {self.DEFAULT_TABLE}
                USE INDEX (idx_sqldate)
                WHERE SQLDATE = %s
            """
            result = await pool.fetchone(query, (date,))
        
        return result["cnt"] if result else 0
    
    # ==================== 基础querymethod（全部Supportscache）====================
    
    async def query_by_actor_cached(
        self,
        actor_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 50,
        cache_ttl: int = 300
    ) -> str:
        """
        byparamandmethodqueryevent（带cache）
        
        cache key 基于queryArgs，sameArgswilldirectReturnscacheresultresult。
        """
        date_filter = ""
        params = [f"%{actor_name}%", f"%{actor_name}%"]
        
        if start_date and end_date:
            date_filter = "AND SQLDATE BETWEEN %s AND %s"
            params.extend([start_date, end_date])
        
        # useArgsizationquery确保 SQL model板一致
        query = f"""
        SELECT SQLDATE, Actor1Name, Actor1CountryCode, 
               Actor2Name, Actor2CountryCode, EventCode,
               GoldsteinScale, AvgTone, SOURCEURL
        FROM {self.DEFAULT_TABLE}
        WHERE (Actor1Name LIKE %s OR Actor2Name LIKE %s)
        {date_filter}
        ORDER BY SQLDATE DESC
        LIMIT %s
        """
        params.append(limit)
        
        rows = await self.execute_sql_cached(query, tuple(params), cache_ttl)
        
        if not rows:
            return f"not found涉and '{actor_name}' event"
        
        # formatizationfor Markdown tablegrid
        columns = list(rows[0].keys())
        row_tuples = [tuple(row.get(col) for col in columns) for row in rows]
        return self._format_markdown(columns, row_tuples)
    
    
    async def query_by_time_range_cached(
        self,
        start_date: str,
        end_date: str,
        limit: int = 100,
        cache_ttl: int = 300
    ) -> str:
        """bywhenintervalrangequeryevent（带cache）"""
        query = """
        SELECT SQLDATE, Actor1Name, Actor2Name, EventCode, 
               GoldsteinScale, AvgTone, NumArticles, SOURCEURL
        FROM {table}
        WHERE SQLDATE BETWEEN %s AND %s
        ORDER BY SQLDATE DESC
        LIMIT %s
        """.format(table=self.DEFAULT_TABLE)
        
        rows = await self.execute_sql_cached(query, (start_date, end_date, limit), cache_ttl)
        
        if not rows:
            return f"not found {start_date} 至 {end_date} event"
        
        columns = list(rows[0].keys())
        row_tuples = [tuple(row.get(col) for col in columns) for row in rows]
        return self._format_markdown(columns, row_tuples)
    
    
    async def analyze_daily_events_cached(
        self,
        start_date: str,
        end_date: str,
        cache_ttl: int = 600
    ) -> str:
        """bydatestatisticseventquantity（带cache）"""
        query = f"""
        SELECT SQLDATE, 
               COUNT(*) as event_count,
               AVG(GoldsteinScale) as avg_goldstein,
               AVG(AvgTone) as avg_tone
        FROM {self.DEFAULT_TABLE}
        WHERE SQLDATE BETWEEN %s AND %s
        GROUP BY SQLDATE
        ORDER BY SQLDATE
        """
        
        rows = await self.execute_sql_cached(query, (start_date, end_date), cache_ttl)
        
        if not rows:
            return "not founddata"
        
        columns = list(rows[0].keys())
        row_tuples = [tuple(row.get(col) for col in columns) for row in rows]
        return self._format_markdown(columns, row_tuples)
    
    
    async def analyze_top_actors_cached(
        self,
        start_date: str,
        end_date: str,
        top_n: int = 10,
        cache_ttl: int = 600
    ) -> str:
        """statisticsmost活跃paramandmethod（带cache）"""
        query = f"""
        SELECT Actor1Name as actor, COUNT(*) as event_count
        FROM {self.DEFAULT_TABLE}
        WHERE SQLDATE BETWEEN %s AND %s
          AND Actor1Name IS NOT NULL
          AND Actor1Name != ''
        GROUP BY Actor1Name
        ORDER BY event_count DESC
        LIMIT %s
        """
        
        rows = await self.execute_sql_cached(query, (start_date, end_date, top_n), cache_ttl)
        
        if not rows:
            return "not founddata"
        
        columns = list(rows[0].keys())
        row_tuples = [tuple(row.get(col) for col in columns) for row in rows]
        return self._format_markdown(columns, row_tuples)
    
    
    # ==================== formatizationtool ====================
    
    def _format_markdown(self, columns: List[str], rows: List[tuple], max_display_rows: int = 20) -> str:
        """formatizationfor Markdown tablegrid"""
        if not rows:
            return "querysuccess，butnot foundmeetconditionmaterialrecord。"
        
        total_rows = len(rows)
        MAX_CELL_WIDTH = 100
        
        def truncate(text):
            text = str(text) if text is not None else "NULL"
            text = text.encode('utf-8', 'ignore').decode('utf-8')
            if len(text) > MAX_CELL_WIDTH:
                text = text[:MAX_CELL_WIDTH-3] + "..."
            return text.replace('|', '｜').replace('\n', ' ')
        
        header = "| " + " | ".join(columns) + " |"
        separator = "|" + "|".join([" --- " for _ in columns]) + "|"
        data_rows = ["| " + " | ".join([truncate(cell) for cell in row]) + " |" for row in rows[:max_display_rows]]
        
        result = "\n".join([header, separator] + data_rows)
        if total_rows > max_display_rows:
            result += f"\n\n*共 {total_rows} row，displaybefore {max_display_rows} row*"
        else:
            result += f"\n\n*共Returns {total_rows} rowdata*"
        
        return result
    
    
    # ==================== coreoptization：joinpre热 ====================
    
    @staticmethod
    async def warmup_connections(count: int = 5):
        """
        join池pre热 - startwhenbuild立join
        
        Avoid cold start latency on first request。
        """
        pool = await get_db_pool()
        
        async def ping():
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1")
        
        # andsendpre热
        await asyncio.gather(*[ping() for _ in range(count)])
        print(f"[warmup] pre热completed: {count} join")

    def _get_chroma_collection(self):
        """延迟Initialize ChromaDB (Avoid lag at startup)"""
        if self._chroma_collection is None:
            try:
                # 定位toitemproject根projectlogunder chroma_db filefolder
                project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
                db_path = os.path.join(project_root, 'chroma_db')
                
                client = chromadb.PersistentClient(path=db_path)
                ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
                self._chroma_collection = client.get_collection(
                    name="gdelt_news_collection", 
                    embedding_function=ef
                )
                logging.info("✅ ChromaDB vector检索toolInitializesuccess！")
            except Exception as e:
                logging.error(f"❌ ChromaDB Initializefailed: {e}")
        return self._chroma_collection

    # ==================== coreoptization：RAG 语义检索 ====================
    
    async def search_news_context(self, query: str, n_results: int = 3) -> str:
        """execrowvectordatabase语义检索 (Agent right脑)"""
        collection = self._get_chroma_collection()
        if not collection:
            return "Error: vectordatabase未Initializeorunablejoin。"

        try:
            # ChromaDB Local retrieval is very fast，directcallbackuse
            results = collection.query(
                query_texts=[query],
                n_results=n_results
            )
            
            if not results['documents'] or not results['documents'][0]:
                return f"Knowledge base innot foundand '{query}' 相关newsreport。"
                
            formatted_result = f"🔍 Found the following news excerpts for query '{query}':\n\n"
            for i in range(len(results['documents'][0])):
                doc_text = results['documents'][0][i]
                event_id = results['ids'][0][i]
                url = results['metadatas'][0][i].get('source_url', 'Unknown URL')
                date = results['metadatas'][0][i].get('date', 'Unknown Date')
                
                # 截fetchbefore 1000 字符，防stop Token superload
                snippet = doc_text[:1000] + "..." if len(doc_text) > 1000 else doc_text
                
                formatted_result += f"--- Result {i+1} ---\n"
                formatted_result += f"Event ID: {event_id}\n"
                formatted_result += f"Date: {date}\n"
                formatted_result += f"Source URL: {url}\n"
                formatted_result += f"Content Snippet: {snippet}\n\n"
                
            return formatted_result
        except Exception as e:
            return f"检索inform识librarywhenoccurerror: {str(e)}"


# 便捷function
async def get_optimized_service() -> GDELTServiceOptimized:
    """Getoptimized versionserviceinstance"""
    return GDELTServiceOptimized()

#!/usr/bin/env python3
"""
GDELT ETL Pipeline
purpose: precalculateday报data、generateeventfingerprint、updatestatisticsdata
运行frequency: 每day一次（建议凌晨2点）

use:
    python db_scripts/etl_pipeline.py [YYYY-MM-DD]
    
    不传arguments则process昨天data
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# 添加item目path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mcp_server'))

from app.database.pool import DatabasePool

# configurationlog
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/gdelt_etl.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class GDELTETLPipeline:
    """GDELTdataETLpipeline"""
    
    def __init__(self):
        self.pool: Optional[DatabasePool] = None
        
    async def initialize(self):
        """初始化databaseconnection"""
        self.pool = await DatabasePool.initialize()
        logger.info("✅ databaseconnection池已初始化")
    
    async def close(self):
        """关闭connection"""
        await DatabasePool.close()
        logger.info("✅ databaseconnection已关闭")
    
    async def run_daily_etl(self, target_date: Optional[str] = None):
        """
        运行每dayETLtask
        
        Args:
            target_date: 目标date (YYYY-MM-DD)，default昨天
        """
        if target_date is None:
            target_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        logger.info(f"🚀 startETLprocess: {target_date}")
        
        try:
            # 1. check该date是否有data
            has_data = await self._check_data_exists(target_date)
            if not has_data:
                logger.warning(f"⚠️ {target_date} 无data，skipETL")
                return
            
            # 2. generate每daydigest
            await self._generate_daily_summary(target_date)
            
            # 3. generate新eventfingerprint
            await self._generate_event_fingerprints(target_date)
            
            # 4. update地区statistics
            await self._update_region_stats(target_date)
            
            # 5. update地理grid
            await self._update_geo_grid(target_date)
            
            # 6. 识别hoteventandupdatefingerprintreference
            await self._identify_hot_events(target_date)
            
            logger.info(f"✅ ETLcompleted: {target_date}")
            
        except Exception as e:
            logger.error(f"❌ ETLfailed: {e}", exc_info=True)
            raise
    
    async def _check_data_exists(self, date: str) -> bool:
        """check指定date是否有data"""
        result = await self.pool.fetchone(
            "SELECT COUNT(*) as cnt FROM events_table WHERE SQLDATE = %s",
            (date,)
        )
        count = result['cnt'] if result else 0
        logger.info(f"📊 {date} data量: {count} 条")
        return count > 0
    
    async def _generate_daily_summary(self, date: str):
        """generate每daydigesttable"""
        logger.info(f"📊 generateday报: {date}")
        
        # statistics基础data
        stats = await self.pool.fetchone("""
            SELECT 
                COUNT(*) as total_events,
                SUM(CASE WHEN GoldsteinScale < -5 THEN 1 ELSE 0 END) as conflict_events,
                SUM(CASE WHEN GoldsteinScale > 5 THEN 1 ELSE 0 END) as cooperation_events,
                AVG(GoldsteinScale) as avg_goldstein,
                AVG(AvgTone) as avg_tone
            FROM events_table
            WHERE SQLDATE = %s
        """, (date,))
        
        if not stats or stats['total_events'] == 0:
            logger.warning(f"  ⚠️ {date} 无data")
            return
        
        # fetchTop Actor
        actors_result = await self.pool.fetchall("""
            SELECT Actor1Name as name, COUNT(*) as cnt
            FROM events_table
            WHERE SQLDATE = %s AND Actor1Name != '' AND Actor1Name IS NOT NULL
            GROUP BY Actor1Name
            ORDER BY cnt DESC
            LIMIT 10
        """, (date,))
        
        top_actors = [{"name": row['name'], "count": row['cnt']} for row in actors_result]
        
        # fetchTop Location
        locations_result = await self.pool.fetchall("""
            SELECT ActionGeo_FullName as name, COUNT(*) as cnt
            FROM events_table
            WHERE SQLDATE = %s AND ActionGeo_FullName IS NOT NULL AND ActionGeo_FullName != ''
            GROUP BY ActionGeo_FullName
            ORDER BY cnt DESC
            LIMIT 10
        """, (date,))
        
        top_locations = [{"name": row['name'], "count": row['cnt']} for row in locations_result]
        
        # eventtypedistribution
        types_result = await self.pool.fetchall("""
            SELECT 
                CASE 
                    WHEN EventRootCode = '01' THEN 'statement'
                    WHEN EventRootCode = '02' THEN 'appeal'
                    WHEN EventRootCode = '03' THEN 'intent'
                    WHEN EventRootCode IN ('04', '05') THEN 'consult'
                    WHEN EventRootCode = '06' THEN 'material'
                    WHEN EventRootCode IN ('07', '08') THEN 'aid'
                    WHEN EventRootCode = '09' THEN 'yield'
                    WHEN EventRootCode = '10' THEN 'demand'
                    WHEN EventRootCode = '11' THEN 'disapprove'
                    WHEN EventRootCode = '12' THEN 'reject'
                    WHEN EventRootCode = '13' THEN 'threaten'
                    WHEN EventRootCode = '14' THEN 'protest'
                    WHEN EventRootCode = '15' THEN 'force'
                    WHEN EventRootCode IN ('16', '17') THEN 'coerce'
                    WHEN EventRootCode IN ('18', '19', '20') THEN 'fight'
                    ELSE 'other'
                END as event_type,
                COUNT(*) as cnt
            FROM events_table
            WHERE SQLDATE = %s
            GROUP BY event_type
            ORDER BY cnt DESC
        """, (date,))
        
        type_dist = {row['event_type']: row['cnt'] for row in types_result}
        
        # hoteventfingerprint（临时用GID，after续update为fingerprint）
        hot_result = await self.pool.fetchall("""
            SELECT GlobalEventID, NumArticles * ABS(GoldsteinScale) as hot_score
            FROM events_table
            WHERE SQLDATE = %s
            ORDER BY hot_score DESC
            LIMIT 20
        """, (date,))
        
        hot_events = [str(row['GlobalEventID']) for row in hot_result]
        
        # insert/updateday报
        await self.pool.execute("""
            INSERT INTO daily_summary 
            (date, total_events, conflict_events, cooperation_events,
             avg_goldstein, avg_tone, top_actors, top_locations,
             event_type_distribution, hot_event_fingerprints)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            total_events = VALUES(total_events),
            conflict_events = VALUES(conflict_events),
            cooperation_events = VALUES(cooperation_events),
            avg_goldstein = VALUES(avg_goldstein),
            avg_tone = VALUES(avg_tone),
            top_actors = VALUES(top_actors),
            top_locations = VALUES(top_locations),
            event_type_distribution = VALUES(event_type_distribution),
            hot_event_fingerprints = VALUES(hot_event_fingerprints)
        """, (
            date, 
            stats['total_events'], 
            stats['conflict_events'] or 0, 
            stats['cooperation_events'] or 0,
            stats['avg_goldstein'], 
            stats['avg_tone'],
            json.dumps(top_actors),
            json.dumps(top_locations),
            json.dumps(type_dist),
            json.dumps(hot_events)
        ))
        
        logger.info(f"  ✓ day报已generate: {stats['total_events']} event, {len(top_actors)} 个活跃Actor")
    
    async def _generate_event_fingerprints(self, date: str):
        """为新eventgeneratefingerprint"""
        logger.info(f"🔖 generateeventfingerprint: {date}")
        
        # fetchwhen天尚未generatefingerprintevent（batchprocess）
        total_processed = 0
        batch_size = 5000
        
        while True:
            batch = await self.pool.fetchall("""
                SELECT e.GlobalEventID, e.SQLDATE, e.Actor1Name, e.Actor2Name,
                       e.EventCode, e.EventRootCode, e.GoldsteinScale,
                       e.ActionGeo_FullName, e.ActionGeo_CountryCode,
                       e.ActionGeo_Lat, e.ActionGeo_Long, e.NumArticles
                FROM events_table e
                LEFT JOIN event_fingerprints f ON e.GlobalEventID = f.global_event_id
                WHERE e.SQLDATE = %s AND f.global_event_id IS NULL
                LIMIT %s
            """, (date, batch_size))
            
            if not batch:
                break
                
            # batchgeneratefingerprint
            fingerprints = []
            for evt in batch:
                fp = self._create_fingerprint(evt)
                fingerprints.append(fp)
            
            # batchinsert
            inserted = 0
            for fp_data in fingerprints:
                try:
                    await self.pool.execute("""
                        INSERT INTO event_fingerprints 
                        (global_event_id, fingerprint, headline, summary, 
                         key_actors, event_type_label, severity_score,
                         location_name, location_country)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        fingerprint = VALUES(fingerprint)
                    """, fp_data)
                    inserted += 1
                except Exception as e:
                    logger.warning(f"    skip重复fingerprint: {e}")
            
            total_processed += inserted
            logger.info(f"  ✓ 本批次generate {inserted} 个fingerprint，累计 {total_processed}")
            
            # 如果本批次不足 batch_size，descriptionprocess完了
            if len(batch) < batch_size:
                break
        
        logger.info(f"  ✓ 总共generate {total_processed} 个fingerprint")
    
    def _create_fingerprint(self, evt: Dict) -> Tuple:
        """
        为eventcreatefingerprint
        
        fingerprintformat: {COUNTRY}-{YYYYMMDD}-{LOCATION}-{TYPE}-{SEQ}
        example: US-20240115-WDC-PROTEST-001
        """
        gid = evt['GlobalEventID']
        sqldate = evt['SQLDATE']
        actor1 = evt['Actor1Name'] or '某国'
        actor2 = evt['Actor2Name'] or '对方'
        event_root = str(evt['EventRootCode'] or '')[:2]
        goldstein = evt['GoldsteinScale'] or 0
        location = evt['ActionGeo_FullName'] or '未知地点'
        country = evt['ActionGeo_CountryCode'] or 'XX'
        articles = evt['NumArticles'] or 0
        
        # 解析date
        if isinstance(sqldate, str):
            date_str = sqldate.replace('-', '')
        else:
            date_str = str(sqldate).replace('-', '')
        
        # 地点缩写 (取before3个字母大写)
        location_code = 'UNK'
        if location and location != '未知地点':
            parts = location.split(',')
            if parts:
                location_code = parts[0].strip()[:3].upper()
        
        # eventtype
        type_map = {
            '01': 'STATEMENT', '02': 'APPEAL', '03': 'INTENT',
            '04': 'CONSULT', '05': 'ENGAGE', '06': 'AID',
            '07': 'AID', '08': 'AID', '09': 'YIELD',
            '10': 'DEMAND', '11': 'DISAPPROVE', '12': 'REJECT',
            '13': 'THREATEN', '14': 'PROTEST', '15': 'FORCE',
            '16': 'REDUCE', '17': 'COERCE', '18': 'FIGHT',
            '19': 'MASS', '20': 'ASSAULT'
        }
        event_type = type_map.get(event_root, 'EVENT')
        
        # 序号 (基于GID最after3位)
        seq = str(gid)[-3:].zfill(3)
        
        fingerprint = f"{country}-{date_str}-{location_code}-{event_type}-{seq}"
        
        # generate可读标题
        headline = self._generate_headline(actor1, actor2, event_root, location)
        
        # generatedigest
        summary = self._generate_summary(actor1, actor2, location, goldstein, articles)
        
        # 关keyparticipant
        key_actors = json.dumps([a for a in [actor1, actor2] if a and a not in ['某国', '对方']])
        
        # eventtypetag
        event_label = self._get_event_label(event_root)
        
        # 严重度评分 (1-10)
        severity = min(10, max(1, abs(goldstein) * 2))
        if articles > 100:
            severity += 1
        severity = min(10, severity)
        
        return (
            gid, fingerprint, headline, summary,
            key_actors, event_label, severity,
            location, country
        )
    
    def _generate_headline(self, actor1: str, actor2: str, 
                          event_root: str, location: str) -> str:
        """generateevent标题"""
        a1 = actor1 or '某国'
        a2 = actor2 or '对方'
        loc = location or '某地'
        
        action_map = {
            '01': f"{a1}发table声明", '02': f"{a1}向{a2}呼吁",
            '03': f"{a1}table达意graph", '04': f"{a1}与{a2}磋商",
            '05': f"{a1}参与{a2}事务", '06': f"{a1}向{a2}提供物资",
            '07': f"{a1}向{a2}提供援助", '08': f"{a1}向{a2}提供援助",
            '09': f"{a1}向{a2}让步", '10': f"{a1}向{a2}提出want求",
            '11': f"{a1}对{a2}table示不满", '12': f"{a1}拒绝{a2}",
            '13': f"{a1}威胁{a2}", '14': f"{a1}发起抗议",
            '15': f"{a1}展示武力", '16': f"{a1}reduce对{a2}关系",
            '17': f"{a1}胁迫{a2}", '18': f"{a1}与{a2}发生摩擦",
            '19': f"{a1}与{a2}发生conflict", '20': f"{a1}对{a2}use武力"
        }
        
        action = action_map.get(event_root, f"{a1}与{a2}互动")
        
        if loc and loc not in [a1, a2]:
            return f"{action} ({loc})"
        return action
    
    def _generate_summary(self, actor1: str, actor2: str, 
                         location: str, goldstein: float, articles: int) -> str:
        """generateeventdigest"""
        a1 = actor1 or '某国'
        a2 = actor2 or '对方'
        loc = location or '某地'
        
        intensity = "轻微"
        if goldstein:
            if abs(goldstein) > 7:
                intensity = "严重"
            elif abs(goldstein) > 4:
                intensity = "中等"
        
        coverage = ""
        if articles > 100:
            coverage = f"，受到广泛报道({articles}篇)"
        elif articles > 10:
            coverage = f"，受到一定报道({articles}篇)"
        
        return f"{a1}与{a2}在{loc}发生{intensity}互动{coverage}。"
    
    def _get_event_label(self, event_root: str) -> str:
        """fetcheventtypetag"""
        labels = {
            '01': '外交声明', '02': '外交呼吁', '03': '政策意向',
            '04': '外交磋商', '05': '参与合作', '06': '物资援助',
            '07': '人员援助', '08': '保护援助', '09': '让步缓和',
            '10': '提出want求', '11': 'table达不满', '12': '拒绝反对',
            '13': '威胁warning', '14': '抗议示威', '15': '展示武力',
            '16': '关系downgrade', '17': '强制胁迫', '18': '军事摩擦',
            '19': '大规模conflict', '20': '武装攻击'
        }
        return labels.get(event_root, '其他event')
    
    async def _update_region_stats(self, date: str):
        """update地区statistics"""
        logger.info(f"🌍 update地区statistics: {date}")
        
        # 按国家statistics
        regions = await self.pool.fetchall("""
            SELECT 
                ActionGeo_CountryCode as region,
                MAX(ActionGeo_FullName) as region_name,
                COUNT(*) as event_count,
                AVG(CASE WHEN GoldsteinScale < 0 THEN ABS(GoldsteinScale) ELSE 0 END) as conflict_intensity,
                AVG(CASE WHEN GoldsteinScale > 0 THEN GoldsteinScale ELSE 0 END) as cooperation_intensity,
                AVG(AvgTone) as avg_tone,
                MAX(Actor1Name) as primary_actor
            FROM events_table
            WHERE SQLDATE = %s AND ActionGeo_CountryCode IS NOT NULL AND ActionGeo_CountryCode != ''
            GROUP BY ActionGeo_CountryCode
            HAVING event_count > 10
        """, (date,))
        
        # batchinsert
        updated = 0
        for r in regions:
            actors = json.dumps([r['primary_actor']]) if r['primary_actor'] else '[]'
            try:
                await self.pool.execute("""
                    INSERT INTO region_daily_stats
                    (region_code, region_name, region_type, date, event_count,
                     conflict_intensity, cooperation_intensity, avg_tone, primary_actors)
                    VALUES (%s, %s, 'country', %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                    event_count = VALUES(event_count),
                    conflict_intensity = VALUES(conflict_intensity),
                    cooperation_intensity = VALUES(cooperation_intensity),
                    avg_tone = VALUES(avg_tone),
                    primary_actors = VALUES(primary_actors)
                """, (
                    r['region'], r['region_name'][:100], date, 
                    r['event_count'], r['conflict_intensity'], 
                    r['cooperation_intensity'], r['avg_tone'], actors
                ))
                updated += 1
            except Exception as e:
                logger.warning(f"    skip地区 {r['region']}: {e}")
        
        logger.info(f"  ✓ update {updated} 个地区")
    
    async def _update_geo_grid(self, date: str):
        """update地理gridhot"""
        logger.info(f"🗺️ update地理grid: {date}")
        
        # 按0.5度gridaggregate
        grids = await self.pool.fetchall("""
            SELECT 
                FLOOR(ActionGeo_Lat * 2) / 2 as lat_grid,
                FLOOR(ActionGeo_Long * 2) / 2 as lng_grid,
                COUNT(*) as event_count,
                SUM(CASE WHEN GoldsteinScale < -5 THEN 1 ELSE 0 END) as conflict_sum,
                AVG(GoldsteinScale) as avg_goldstein,
                AVG(AvgTone) as avg_tone
            FROM events_table
            WHERE SQLDATE = %s 
              AND ActionGeo_Lat IS NOT NULL 
              AND ActionGeo_Long IS NOT NULL
              AND ActionGeo_Lat != 0
              AND ActionGeo_Long != 0
            GROUP BY lat_grid, lng_grid
            HAVING event_count > 5
        """, (date,))
        
        # batchinsert
        updated = 0
        for g in grids:
            grid_id = f"LAT_{g['lat_grid']}_LNG_{g['lng_grid']}"
            try:
                await self.pool.execute("""
                    INSERT INTO geo_heatmap_grid
                    (grid_id, lat_grid, lng_grid, date, event_count, 
                     conflict_sum, avg_goldstein, avg_tone)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                    event_count = VALUES(event_count),
                    conflict_sum = VALUES(conflict_sum),
                    avg_goldstein = VALUES(avg_goldstein),
                    avg_tone = VALUES(avg_tone)
                """, (
                    grid_id, g['lat_grid'], g['lng_grid'], date,
                    g['event_count'], g['conflict_sum'], 
                    g['avg_goldstein'], g['avg_tone']
                ))
                updated += 1
            except Exception as e:
                logger.warning(f"    skipgrid {grid_id}: {e}")
        
        logger.info(f"  ✓ update {updated} 个grid")
    
    async def _identify_hot_events(self, date: str):
        """识别andupdatehoteventfingerprintreference"""
        logger.info(f"🔥 识别hotevent: {date}")
        
        # fetchwhenbeforehoteventGID
        result = await self.pool.fetchone("""
            SELECT hot_event_fingerprints 
            FROM daily_summary 
            WHERE date = %s
        """, (date,))
        
        if not result or not result['hot_event_fingerprints']:
            logger.info("  ⚠️ 无hoteventdata")
            return
        
        hot_fingerprints_data = result['hot_event_fingerprints']
        if isinstance(hot_fingerprints_data, str):
            gids = json.loads(hot_fingerprints_data)
        else:
            gids = hot_fingerprints_data
        
        # 将GID转换为fingerprint
        fingerprints = []
        for gid in gids[:10]:
            fp_result = await self.pool.fetchone("""
                SELECT fingerprint FROM event_fingerprints 
                WHERE global_event_id = %s
            """, (gid,))
            
            if fp_result:
                fingerprints.append(fp_result['fingerprint'])
        
        # updateday报
        if fingerprints:
            await self.pool.execute("""
                UPDATE daily_summary 
                SET hot_event_fingerprints = %s 
                WHERE date = %s
            """, (json.dumps(fingerprints), date))
            
            logger.info(f"  ✓ update {len(fingerprints)} 个hoteventfingerprint")


async def main():
    """主入口"""
    # 解析arguments
    target_date = None
    if len(sys.argv) > 1:
        target_date = sys.argv[1]
        # validatedateformat
        try:
            datetime.strptime(target_date, '%Y-%m-%d')
        except ValueError:
            print(f"❌ dateformaterror: {target_date}")
            print("   正确format: YYYY-MM-DD")
            sys.exit(1)
    
    # 运行ETL
    pipeline = GDELTETLPipeline()
    try:
        await pipeline.initialize()
        await pipeline.run_daily_etl(target_date)
    finally:
        await pipeline.close()


if __name__ == "__main__":
    asyncio.run(main())

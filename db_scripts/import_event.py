import pandas as pd
import mysql.connector
import glob
import numpy as np
import dotenv
import os
import logging
import hashlib

# 配置日志格式，让终端输出更好看
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')

dotenv.load_dotenv()

DB_PASSWORD = os.getenv("DB_PASSWORD")

# 1. 数据库配置
db_config = {
    'host': os.getenv('DB_HOST', 'db'),
    'user': 'root',
    'password': DB_PASSWORD,
    'database': 'gdelt', 
    'charset': 'utf8mb4',
    'allow_local_infile': True 
}

# 🌟 优化1：加上 sorted，按 0000 到 0075 的顺序执行
csv_files = sorted(glob.glob("data/gdelt_2024_na_*.csv"))

temp_file = os.path.abspath('temp_bulk_load.csv').replace('\\', '/')

def get_file_signature(file_path):
    """获取文件签名（文件名 + 修改时间 + 大小）用于检测重复导入"""
    stat = os.stat(file_path)
    signature = f"{os.path.basename(file_path)}_{stat.st_mtime}_{stat.st_size}"
    return hashlib.md5(signature.encode()).hexdigest()

def check_already_imported(cursor, file_path):
    """检查文件是否已导入"""
    try:
        # 创建导入记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS _import_log (
                file_signature VARCHAR(32) PRIMARY KEY,
                file_name VARCHAR(255),
                imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                row_count INT
            )
        """)
        
        signature = get_file_signature(file_path)
        cursor.execute("SELECT 1 FROM _import_log WHERE file_signature = %s", (signature,))
        result = cursor.fetchone()
        return result is not None
    except Exception as e:
        logging.warning(f"⚠️  检查导入记录失败: {e}")
        return False

def record_import(cursor, file_path, row_count):
    """记录导入完成"""
    try:
        signature = get_file_signature(file_path)
        cursor.execute(
            "INSERT INTO _import_log (file_signature, file_name, row_count) VALUES (%s, %s, %s)",
            (signature, os.path.basename(file_path), row_count)
        )
    except Exception as e:
        logging.warning(f"⚠️  记录导入日志失败: {e}")

def fast_ingest():
    if not csv_files:
        logging.error("❌ 在 data/ 目录下没有找到任何 gdelt_2024_na_*.csv 文件，请检查路径！")
        return

    logging.info(f"📂 共扫描到 {len(csv_files)} 个分片文件准备导入。")
    
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    # 检查是否有 CSV 文件
    if not csv_files:
        logging.error("❌ 未找到 CSV 文件 (data/gdelt_2024_na_*.csv)")
        return
    
    logging.info(f"📁 找到 {len(csv_files)} 个 CSV 文件")
    logging.info("-" * 60)
    
    # 检查已有数据量
    cursor.execute("SELECT COUNT(*) FROM events_table")
    existing_count = cursor.fetchone()[0]
    logging.info(f"📊 数据库已有 {existing_count:,} 条记录")
    logging.info("-" * 60)

    imported_count = 0
    skipped_count = 0
    
    for i, file in enumerate(csv_files):
        logging.info(f"📄 处理文件: {os.path.basename(file)}")
        
        # 检查是否已导入
        if check_already_imported(cursor, file):
            logging.info(f"   ⏭️  已导入过，跳过")
            skipped_count += 1
            continue
        
        logging.info(f"   🚀 开始清洗和导入...")
        
        # 🌟 优化2：增加 try-except，防止单文件报错中断整体进程
        try:
            # 1. 读取并清洗 
            df = pd.read_csv(file, dtype={'EventCode': str, 'EventRootCode': str})

            df['ActionGeo_Lat'] = pd.to_numeric(df['ActionGeo_Lat'], errors='coerce')
            df['ActionGeo_Long'] = pd.to_numeric(df['ActionGeo_Long'], errors='coerce')

            df.loc[(df['ActionGeo_Lat'] < -90) | (df['ActionGeo_Lat'] > 90), 'ActionGeo_Lat'] = float('nan')
            df.loc[(df['ActionGeo_Long'] < -180) | (df['ActionGeo_Long'] > 180), 'ActionGeo_Long'] = float('nan')

            # 把所有缺失或错误的坐标，统一流放到 "Null Island" (0.0, 0.0)
            df['ActionGeo_Lat'] = df['ActionGeo_Lat'].fillna(0.0)
            df['ActionGeo_Long'] = df['ActionGeo_Long'].fillna(0.0)
            
            # 转换日期格式
            df['SQLDATE'] = pd.to_datetime(df['SQLDATE'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
            if 'DATEADDED' in df.columns:
                df['DATEADDED'] = pd.to_datetime(df['DATEADDED'], format='%Y%m%d%H%M%S', errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S')

            # 拼装 WKT 字符串列
            df['ActionGeo_Point_WKT'] = 'POINT(' + df['ActionGeo_Lat'].astype(str) + ' ' + df['ActionGeo_Long'].astype(str) + ')'

            # 2. 存为没有任何干扰的临时文件 (na_rep='\N' 是 MySQL 识别 NULL 的专属标记)
            df.to_csv(temp_file, index=False, header=False, na_rep=r'\N')
            row_count = len(df)
            
            logging.info(f"   ⚡ 呼叫底层 LOAD DATA 指令灌入 MySQL... ({row_count:,} 行)")
            
            # 3. 执行极速导入指令
            load_query = f"""
            LOAD DATA LOCAL INFILE '{temp_file}'
            IGNORE INTO TABLE events_table
            FIELDS TERMINATED BY ',' ENCLOSED BY '"'
            LINES TERMINATED BY '\n'
            (GlobalEventID, SQLDATE, MonthYear, DATEADDED, Actor1Name, Actor1CountryCode, 
             Actor1Type1Code, Actor2Name, Actor2CountryCode, Actor2Type1Code, EventCode, 
             EventRootCode, QuadClass, GoldsteinScale, AvgTone, NumArticles, NumMentions, 
             NumSources, ActionGeo_Type, ActionGeo_FullName, ActionGeo_CountryCode, 
             ActionGeo_Lat, ActionGeo_Long, SOURCEURL, @wkt_point)
            SET ActionGeo_Point = ST_PointFromText(@wkt_point, 4326)
            """
            
            cursor.execute(load_query)
            conn.commit()
            
            # 记录导入完成
            record_import(cursor, file, row_count)
            conn.commit()
            
            imported_count += 1
            logging.info(f"   ✅ 导入完成！\n")
            
        except Exception as e:
            logging.error(f"❌ 处理 {file} 时发生错误: {str(e)}。已跳过此文件。\n")

    # 清理临时文件
    if os.path.exists(temp_file):
        os.remove(temp_file)
    
    # 显示统计
    logging.info("-" * 60)
    logging.info(f"📊 导入统计:")
    logging.info(f"   本次导入: {imported_count} 个文件")
    logging.info(f"   跳过（已存在）: {skipped_count} 个文件")
    
    cursor.execute("SELECT COUNT(*) FROM events_table")
    final_count = cursor.fetchone()[0]
    logging.info(f"   数据库总计: {final_count:,} 条记录")
        
    cursor.close()
    conn.close()
    logging.info("-" * 60)
    logging.info("🎉 极速导入全部结束！")

if __name__ == "__main__":
    fast_ingest()

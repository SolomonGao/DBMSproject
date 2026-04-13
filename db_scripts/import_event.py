import pandas as pd
import mysql.connector
import glob
import numpy as np
import dotenv
import os
import logging
import hashlib

# configure logformat，Make terminal output look better
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')

dotenv.load_dotenv()

DB_PASSWORD = os.getenv("DB_PASSWORD")

# 1. databaseconfiguration
db_config = {
    'host': os.getenv('DB_HOST', 'db'),
    'user': 'root',
    'password': DB_PASSWORD,
    'database': 'gdelt', 
    'charset': 'utf8mb4',
    'allow_local_infile': True 
}

# 🌟 优ization1：addupload sorted，按 0000 到 0075 顺序执row
csv_files = sorted(glob.glob("data/gdelt_2024_na_*.csv"))

temp_file = os.path.abspath('temp_bulk_load.csv').replace('\\', '/')

def get_file_signature(file_path):
    """fetchfilesign（filename + modifychangetime + size）used fordetectduplicateimport"""
    stat = os.stat(file_path)
    signature = f"{os.path.basename(file_path)}_{stat.st_mtime}_{stat.st_size}"
    return hashlib.md5(signature.encode()).hexdigest()

def check_already_imported(cursor, file_path):
    """checkfilewhetheralreadyimport"""
    try:
        # createimportrecordlogtable
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
        logging.warning(f"⚠️  checkimportrecordlogfailed: {e}")
        return False

def record_import(cursor, file_path, row_count):
    """recordlogimportcompleted"""
    try:
        signature = get_file_signature(file_path)
        cursor.execute(
            "INSERT INTO _import_log (file_signature, file_name, row_count) VALUES (%s, %s, %s)",
            (signature, os.path.basename(file_path), row_count)
        )
    except Exception as e:
        logging.warning(f"⚠️  recordlogimportlogfailed: {e}")

def fast_ingest():
    if not csv_files:
        logging.error("❌ 在 data/ directoryNo results found under gdelt_2024_na_*.csv file，请checkpath！")
        return

    logging.info(f"📂 共扫描到 {len(csv_files)} 个shardfile准备import。")
    
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    # checkwhether有 CSV file
    if not csv_files:
        logging.error("❌ 未找到 CSV file (data/gdelt_2024_na_*.csv)")
        return
    
    logging.info(f"📁 找到 {len(csv_files)} 个 CSV file")
    logging.info("-" * 60)
    
    # checkalready有dataamount
    cursor.execute("SELECT COUNT(*) FROM events_table")
    existing_count = cursor.fetchone()[0]
    logging.info(f"📊 databasealready有 {existing_count:,} 条recordlog")
    logging.info("-" * 60)

    imported_count = 0
    skipped_count = 0
    
    for i, file in enumerate(csv_files):
        logging.info(f"📄 processfile: {os.path.basename(file)}")
        
        # checkwhetheralreadyimport
        if check_already_imported(cursor, file):
            logging.info(f"   ⏭️  alreadyimport过，skip")
            skipped_count += 1
            continue
        
        logging.info(f"   🚀 startclean和import...")
        
        # 🌟 优ization2：增add try-except，防stopformfileError interrupts entire process
        try:
            # 1. readandclean 
            df = pd.read_csv(file, dtype={'EventCode': str, 'EventRootCode': str})

            df['ActionGeo_Lat'] = pd.to_numeric(df['ActionGeo_Lat'], errors='coerce')
            df['ActionGeo_Long'] = pd.to_numeric(df['ActionGeo_Long'], errors='coerce')

            df.loc[(df['ActionGeo_Lat'] < -90) | (df['ActionGeo_Lat'] > 90), 'ActionGeo_Lat'] = float('nan')
            df.loc[(df['ActionGeo_Long'] < -180) | (df['ActionGeo_Long'] > 180), 'ActionGeo_Long'] = float('nan')

            # 把all缺failorerror坐标，统一流放到 "Null Island" (0.0, 0.0)
            df['ActionGeo_Lat'] = df['ActionGeo_Lat'].fillna(0.0)
            df['ActionGeo_Long'] = df['ActionGeo_Long'].fillna(0.0)
            
            # 转换dateformat
            df['SQLDATE'] = pd.to_datetime(df['SQLDATE'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
            if 'DATEADDED' in df.columns:
                df['DATEADDED'] = pd.to_datetime(df['DATEADDED'], format='%Y%m%d%H%M%S', errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S')

            # 拼装 WKT 字符串column
            df['ActionGeo_Point_WKT'] = 'POINT(' + df['ActionGeo_Lat'].astype(str) + ' ' + df['ActionGeo_Long'].astype(str) + ')'

            # 2. Save as temporary without any interferencefile (na_rep='\N' 是 MySQL 识别 NULL 专属标record)
            df.to_csv(temp_file, index=False, header=False, na_rep=r'\N')
            row_count = len(df)
            
            logging.info(f"   ⚡ 呼叫底层 LOAD DATA 指令灌input MySQL... ({row_count:,} row)")
            
            # 3. 执row极速import指令
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
            
            # recordlogimportcompleted
            record_import(cursor, file, row_count)
            conn.commit()
            
            imported_count += 1
            logging.info(f"   ✅ importcompleted！\n")
            
        except Exception as e:
            logging.error(f"❌ process {file} whenoccurerror: {str(e)}。alreadyskip此file。\n")

    # 清process临whenfile
    if os.path.exists(temp_file):
        os.remove(temp_file)
    
    # 显示statistics
    logging.info("-" * 60)
    logging.info(f"📊 importstatistics:")
    logging.info(f"   this次import: {imported_count} 个file")
    logging.info(f"   skip（alreadysave在）: {skipped_count} 个file")
    
    cursor.execute("SELECT COUNT(*) FROM events_table")
    final_count = cursor.fetchone()[0]
    logging.info(f"   database总计: {final_count:,} 条recordlog")
        
    cursor.close()
    conn.close()
    logging.info("-" * 60)
    logging.info("🎉 极速import全部end！")

if __name__ == "__main__":
    fast_ingest()

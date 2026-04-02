import pandas as pd
import mysql.connector
import glob
import numpy as np
import dotenv
import os
import logging

# 配置日志格式，让终端输出更好看
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')

dotenv.load_dotenv()

DB_PASSWORD = os.getenv("DB_PASSWORD")

# 1. 数据库配置
db_config = {
    'host': os.getenv('DB_HOST', 'db'),  # 优先读取环境变量，默认使用 Docker 的 'db' 服务名
    'user': 'root',
    'password': DB_PASSWORD,
    'database': 'gdelt_db', 
    'charset': 'utf8mb4',
    'allow_local_infile': True 
}

# 🌟 优化1：加上 sorted，按 0000 到 0075 的顺序执行
csv_files = sorted(glob.glob("data/gdelt_2024_na_*.csv"))

temp_file = os.path.abspath('temp_bulk_load.csv').replace('\\', '/') 

def fast_ingest():
    if not csv_files:
        logging.error("❌ 在 data/ 目录下没有找到任何 gdelt_2024_na_*.csv 文件，请检查路径！")
        return

    logging.info(f"📂 共扫描到 {len(csv_files)} 个分片文件准备导入。")
    
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()

    for i, file in enumerate(csv_files):
        logging.info(f"🚀 [{i+1}/{len(csv_files)}] 正在清洗并导入: {file}")
        
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

            # 2. 存为没有任何干扰的临时文件
            df.to_csv(temp_file, index=False, header=False, na_rep='\\N')
            
            # 3. 执行极速导入指令
            load_query = f"""
            LOAD DATA LOCAL INFILE '{temp_file}'
            IGNORE INTO TABLE events_table
            FIELDS TERMINATED BY ',' ENCLOSED BY '"'
            LINES TERMINATED BY '\\n'
            (GlobalEventID, SQLDATE, MonthYear, DATEADDED, Actor1Name, Actor1CountryCode, 
             Actor1Type1Code, Actor2Name, Actor2CountryCode, Actor2Type1Code, EventCode, 
             EventRootCode, QuadClass, GoldsteinScale, AvgTone, NumArticles, NumMentions, 
             NumSources, ActionGeo_Type, ActionGeo_FullName, ActionGeo_CountryCode, 
             ActionGeo_Lat, ActionGeo_Long, SOURCEURL, @wkt_point)
            SET ActionGeo_Point = ST_PointFromText(@wkt_point, 4326)
            """
            
            cursor.execute(load_query)
            conn.commit()
            logging.info(f"✅ 分片 {file} 导入成功！新增 {cursor.rowcount} 条数据。\n")
            
        except Exception as e:
            logging.error(f"❌ 处理 {file} 时发生错误: {str(e)}。已跳过此文件。\n")

    # 清理临时文件
    if os.path.exists(temp_file):
        os.remove(temp_file)
        
    cursor.close()
    conn.close()
    logging.info("🎉 极速导入全部结束！")

if __name__ == "__main__":
    fast_ingest()
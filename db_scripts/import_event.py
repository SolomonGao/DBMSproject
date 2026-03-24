import pandas as pd
import mysql.connector
import glob
import numpy as np
import dotenv
import os

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

csv_files = glob.glob("data/gdelt_2024_na_*.csv")


temp_file = os.path.abspath('temp_bulk_load.csv').replace('\\', '/') # 转换路径格式供 MySQL 读取

def fast_ingest():
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()

    for file in csv_files:
        print(f"🚀 正在清洗分片: {file}")
        
        # 1. 读取并清洗 (保留前导零)
        df = pd.read_csv(file, dtype={'EventCode': str, 'EventRootCode': str})

        df['ActionGeo_Lat'] = pd.to_numeric(df['ActionGeo_Lat'], errors='coerce')
        df['ActionGeo_Long'] = pd.to_numeric(df['ActionGeo_Long'], errors='coerce')

        df.loc[(df['ActionGeo_Lat'] < -90) | (df['ActionGeo_Lat'] > 90), 'ActionGeo_Lat'] = float('nan')
        df.loc[(df['ActionGeo_Long'] < -180) | (df['ActionGeo_Long'] > 180), 'ActionGeo_Long'] = float('nan')

        # 3. 核心：不删除任何数据！把所有缺失或错误的坐标，统一流放到 "Null Island" (0.0, 0.0)
        df['ActionGeo_Lat'] = df['ActionGeo_Lat'].fillna(0.0)
        df['ActionGeo_Long'] = df['ActionGeo_Long'].fillna(0.0)
        
        # # 过滤掉没有经纬度的脏数据
        # df = df.dropna(subset=['ActionGeo_Lat', 'ActionGeo_Long'])
        
        # 转换日期格式
        df['SQLDATE'] = pd.to_datetime(df['SQLDATE'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
        if 'DATEADDED' in df.columns:
             df['DATEADDED'] = pd.to_datetime(df['DATEADDED'], format='%Y%m%d%H%M%S', errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S')

        # 核心：直接在 Pandas 里拼装好 WKT 字符串列 (注意之前确定的纬度在前，经度在后的顺序)
        df['ActionGeo_Point_WKT'] = 'POINT(' + df['ActionGeo_Lat'].astype(str) + ' ' + df['ActionGeo_Long'].astype(str) + ')'

        # 2. 存为没有任何干扰的临时文件 (na_rep='\\N' 是 MySQL 识别 NULL 的专属标记)
        df.to_csv(temp_file, index=False, header=False, na_rep='\\N')
        
        print(f"⚡ 呼叫底层 LOAD DATA 指令灌入 MySQL...")
        
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
        print(f"✅ 分片 {file} 导入完毕！\n")

    # 清理临时文件
    if os.path.exists(temp_file):
        os.remove(temp_file)
        
    cursor.close()
    conn.close()
    print("🎉 极速导入结束！")

if __name__ == "__main__":
    fast_ingest()
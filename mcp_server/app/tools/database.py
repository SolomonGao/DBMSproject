import os
import pandas as pd
import mysql.connector
from mysql.connector import Error

def get_db_connection():
    """建立資料庫連線的輔助函數"""
    return mysql.connector.connect(
        # 優先讀取環境變數，預設指向 docker-compose 中的 db 服務
        host=os.getenv('DB_HOST', 'db'),
        user='root',
        password=os.getenv('DB_PASSWORD', 'rootpassword'),
        database='gdelt_db',
        charset='utf8mb4'
    )

def get_schema(table_name: str = "events_table") -> str:
    """
    獲取資料庫表的結構（Schema），包含欄位名稱、資料型別等資訊。
    在編寫 Text2SQL 查詢前，務必先呼叫此工具了解可用的欄位。
    """
    try:
        conn = get_db_connection()
        query = f"DESCRIBE {table_name};"
        df = pd.read_sql(query, conn)
        conn.close()
        # 轉成 Markdown 格式，大模型最容易理解
        return df.to_markdown(index=False)
    except Error as e:
        return f"❌ 資料庫連線或查詢錯誤: {e}"

def execute_sql(query: str) -> str:
    """
    執行 SQL SELECT 查詢語句來分析 GDELT 事件資料。
    注意：
    1. 只能執行 SELECT 語句，禁止任何修改資料的操作。
    2. 為了保護系統記憶體，預設最多只會回傳 100 筆紀錄。
    """
    sql_upper = query.upper().strip()
    
    # 🛡️ 基礎安全檢查：嚴格攔截非 SELECT 語句，防止 Agent 誤刪資料庫
    forbidden_keywords = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'TRUNCATE', 'GRANT', 'REVOKE']
    if not sql_upper.startswith("SELECT") or any(keyword in sql_upper for keyword in forbidden_keywords):
        return "❌ 安全攔截：基於安全考量，此工具僅允許執行 SELECT 查詢語句。"
        
    # 🛡️ 智慧限制回傳行數：如果 AI 忘記加 LIMIT，我們自動幫它加上
    if "LIMIT" not in sql_upper:
        query = query.rstrip(";") + " LIMIT 100;"
        
    try:
        conn = get_db_connection()
        df = pd.read_sql(query, conn)
        conn.close()
        
        if df.empty:
            return "✅ 查詢成功，但未找到符合條件的資料紀錄。"
            
        return df.to_markdown(index=False)
    except Error as e:
        # 如果 AI 寫錯了 SQL，把報錯訊息完整丟給它，它會自己修正
        return f"❌ SQL 語法錯誤或執行失敗: {e}\n請檢查您的 SQL 語句是否符合 MySQL 8.0 規範，並結合表結構重新生成。"
    except Exception as e:
        return f"❌ 發生未知錯誤: {str(e)}"
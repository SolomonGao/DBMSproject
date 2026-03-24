"""
数据库工具模块

使用装饰器模式注册 MCP 工具。
"""

from typing import List, Dict, Any
from app.database import get_db_pool


# SQL 注入防护关键字
FORBIDDEN_KEYWORDS = [
    'DROP', 'DELETE', 'UPDATE', 'INSERT', 
    'ALTER', 'TRUNCATE', 'GRANT', 'REVOKE',
    'CREATE', 'REPLACE', 'LOAD', 'CALL'
]


def _sanitize_query(query: str) -> tuple[bool, str]:
    """安全检查 SQL 查询"""
    sql_upper = query.upper().strip()
    
    if not sql_upper.startswith("SELECT"):
        return False, "安全攔截：僅允許 SELECT 查詢語句"
    
    for keyword in FORBIDDEN_KEYWORDS:
        if keyword in sql_upper:
            return False, f"安全攔截：禁止使用的關鍵字 '{keyword}'"
    
    return True, ""


def _add_limit(query: str, max_rows: int = 100) -> str:
    """智能添加 LIMIT 限制"""
    if "LIMIT" in query.upper():
        return query
    query = query.rstrip(";").strip()
    return f"{query} LIMIT {max_rows};"


def _format_results_as_markdown(columns: List[str], rows: List[tuple], max_cell_width: int = 100) -> str:
    """将查询结果格式化为 Markdown 表格"""
    if not rows:
        return "查詢成功，但未找到符合條件的資料紀錄。"
    
    def truncate(text: str) -> str:
        text = str(text) if text is not None else "NULL"
        return text[:max_cell_width-3] + "..." if len(text) > max_cell_width else text
    
    header = "| " + " | ".join(columns) + " |"
    separator = "|" + "|".join([" --- " for _ in columns]) + "|"
    data_rows = ["| " + " | ".join([truncate(cell) for cell in row]) + " |" for row in rows]
    
    return "\n".join([header, separator] + data_rows) + f"\n\n*共返回 {len(rows)} 行数据*"


def create_database_tools(mcp):
    """创建所有数据库工具（使用装饰器模式）"""
    
    @mcp.tool()
    async def get_schema(table_name: str = "events_table") -> str:
        """
        獲取資料庫表的結構（Schema）
        
        在編寫 Text2SQL 查詢前，務必先呼叫此工具了解可用的欄位。
        
        Args:
            table_name: 表名，預設為 "events_table"
        """
        try:
            pool = await get_db_pool()
            schema_data = await pool.get_schema(table_name)
            
            if not schema_data:
                return f"表 '{table_name}' 不存在或沒有欄位資訊"
            
            columns = ["Field", "Type", "Null", "Key", "Default", "Extra"]
            rows = [
                (
                    row.get("Field", ""),
                    row.get("Type", ""),
                    row.get("Null", ""),
                    row.get("Key", ""),
                    str(row.get("Default", "")) if row.get("Default") is not None else "NULL",
                    row.get("Extra", "")
                )
                for row in schema_data
            ]
            
            return _format_results_as_markdown(columns, rows, max_cell_width=50)
            
        except ValueError as e:
            return f"錯誤：{str(e)}"
        except Exception as e:
            return f"獲取表結構失敗: {str(e)}"
    
    
    @mcp.tool()
    async def get_schema_prompt(table_name: str = "events_table") -> str:
        """
        生成 LLM 友好的 Schema 描述 Prompt
        
        将表结构转化为自然语言描述，帮助 LLM 理解如何查询。
        包含字段分类、查询建议和 SQL 模板。
        
        Args:
            table_name: 表名，預設為 "events_table"
        """
        try:
            pool = await get_db_pool()
            schema_data = await pool.get_schema(table_name)
            
            if not schema_data:
                return f"表 '{table_name}' 不存在或沒有欄位資訊"
            
            # 字段分类
            fields_info = []
            primary_keys = []
            indexed_fields = []
            date_fields = []
            text_fields = []
            numeric_fields = []
            geo_fields = []
            
            for row in schema_data:
                field_name = row.get("Field", "")
                field_type = row.get("Type", "").upper()
                is_null = row.get("Null", "YES") == "YES"
                key = row.get("Key", "")
                default = row.get("Default")
                
                nullable = "可為空" if is_null else "必填"
                default_str = f"，預設值: {default}" if default is not None else ""
                fields_info.append(f"- `{field_name}` ({field_type}): {nullable}{default_str}")
                
                if key == "PRI":
                    primary_keys.append(field_name)
                if key in ["MUL", "UNI"]:
                    indexed_fields.append(field_name)
                if "DATE" in field_type or "TIME" in field_type:
                    date_fields.append(field_name)
                if "CHAR" in field_type or "TEXT" in field_type:
                    text_fields.append(field_name)
                if any(t in field_type for t in ["INT", "FLOAT", "DOUBLE", "DECIMAL"]):
                    numeric_fields.append(field_name)
                if any(t in field_type for t in ["POINT", "GEOMETRY", "LAT", "LONG"]):
                    geo_fields.append(field_name)
            
            # 获取示例数据
            sample_data = ""
            try:
                samples = await pool.fetchall(f"SELECT * FROM `{table_name}` LIMIT 3")
                if samples:
                    sample_rows = []
                    for i, sample in enumerate(samples, 1):
                        items = list(sample.items())[:5]
                        row_str = ", ".join([f"{k}={repr(v)[:50]}" for k, v in items])
                        sample_rows.append(f"  行{i}: {row_str}")
                    sample_data = "\n".join(sample_rows)
            except:
                sample_data = "（無法獲取示例數據）"
            
            # 构建 Prompt
            prompt = f"""## 數據庫表結構說明

**表名**: `{table_name}`
**總欄位數**: {len(schema_data)}

### 欄位列表

{chr(10).join(fields_info)}

### 索引與約束

- **主鍵**: {', '.join(primary_keys) if primary_keys else '無'}
- **索引欄位**: {', '.join(indexed_fields) if indexed_fields else '無'}

### 欄位分類

- **時間/日期欄位**: {', '.join([f'`{f}`' for f in date_fields]) if date_fields else '無'}
- **文本欄位**: {', '.join([f'`{f}`' for f in text_fields[:5]]) + ('...' if len(text_fields) > 5 else '') if text_fields else '無'}
- **數值欄位**: {', '.join([f'`{f}`' for f in numeric_fields]) if numeric_fields else '無'}
- **地理/座標欄位**: {', '.join([f'`{f}`' for f in geo_fields]) if geo_fields else '無'}

### 示例數據

{sample_data}

### 查詢建議

1. **時間範圍查詢**: 使用 `{date_fields[0] if date_fields else 'SQLDATE'}` 欄位進行日期範圍篩選
2. **地理位置查詢**: 使用 `{geo_fields[0] if geo_fields else 'ActionGeo_Lat/Long'}` 進行地理範圍查詢
3. **文本搜索**: 使用 `LIKE` 對文本欄位進行模糊匹配
4. **數值比較**: 使用 `>`, `<`, `=` 對數值欄位進行比較

### 常用查詢模板

```sql
-- 查詢特定日期範圍的事件
SELECT SQLDATE, Actor1Name, Actor2Name, EventCode, GoldsteinScale
FROM {table_name}
WHERE SQLDATE BETWEEN '2024-01-01' AND '2024-01-31'
LIMIT 10;

-- 查詢特定參與方的事件
SELECT SQLDATE, Actor1Name, Actor2Name, GoldsteinScale, AvgTone
FROM {table_name}
WHERE Actor1Name LIKE '%關鍵詞%'
ORDER BY SQLDATE DESC
LIMIT 20;
```
"""
            return prompt
            
        except ValueError as e:
            return f"錯誤：{str(e)}"
        except Exception as e:
            return f"生成 Schema Prompt 失敗: {str(e)}"
    
    
    @mcp.tool()
    async def execute_sql(query: str) -> str:
        """
        執行 SQL SELECT 查詢語句來分析 GDELT 事件資料
        
        安全限制：
        - 只能執行 SELECT 語句
        - 自動限制最多返回 100 行
        - 嚴格攔截危險關鍵字
        - 連接丟失時自動重試（最多3次）
        
        Args:
            query: SQL SELECT 查詢語句
        """
        passed, error_msg = _sanitize_query(query)
        if not passed:
            return error_msg
        
        query = _add_limit(query, max_rows=100)
        
        try:
            pool = await get_db_pool()
            rows = await pool.fetchall(query)
            
            if not rows:
                return "查詢成功，但未找到符合條件的資料紀錄。"
            
            columns = list(rows[0].keys())
            row_tuples = [tuple(row.get(col) for col in columns) for row in rows]
            
            return _format_results_as_markdown(columns, row_tuples)
            
        except Exception as e:
            return f"""SQL 執行錯誤: {str(e)}

請檢查:
1. SQL 語法是否符合 MySQL 8.0 規範
2. 表名和欄位名是否正確（可使用 `get_schema` 工具確認）
3. 條件語句是否正確

原始查詢:
```sql
{query}
```"""
    
    return get_schema, get_schema_prompt, execute_sql

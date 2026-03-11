import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='ignore')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='ignore')

from mcp.server.fastmcp import FastMCP
import mysql.connector
import pandas as pd
import matplotlib.pyplot as plt
import base64

import os
import dotenv

dotenv.load_dotenv()

DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_CONFIG = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': DB_PASSWORD, 
    'database': 'gdelt_db',
    'charset': 'utf8mb4'
}


mcp = FastMCP("GDELT_Agent_Server")

@mcp.tool()
def search_event(actor_name: str, limit: int = 5) -> str:
    """
    根据人物或机构名称（ActorName）搜索相关的 GDELT 国际事件。
    """
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        
        # 这个查询会完美命中你之前建立的 idx_actors 索引！
        query = """
            SELECT SQLDATE, Actor1Name, Actor2Name, EventCode, ActionGeo_FullName, SOURCEURL
            FROM events_table 
            WHERE Actor1Name LIKE %s OR Actor2Name LIKE %s
            LIMIT %s
        """
        search_term = f"{actor_name}%" # 利用前缀索引加速
        
        df = pd.read_sql(query, conn, params=(search_term, search_term, limit))
        conn.close()
        
        if df.empty:
            return f"没有找到与 '{actor_name}' 相关的事件。"
            
        # 将结果格式化为 Markdown 表格供大模型阅读
        return f"找到关于 '{actor_name}' 的最新事件：\n" + df.to_markdown(index=False)
        
    except Exception as e:
        return f"数据库查询报错: {str(e)}"

@mcp.tool()
def plot_event_trend(actor_name: str) -> str:
    """
    统计某个实体（Actor）参与事件的数量随时间的变化趋势，并生成折线图。
    """
    try:
        conn = mysql.connector.connect(**DB_CONFIG)

        # 命中 idx_sqldate 和 idx_actors 索引
        query = """
            SELECT SQLDATE, COUNT(*) as EventCount
            FROM events_table 
            WHERE Actor1Name LIKE %s
            GROUP BY SQLDATE
            ORDER BY SQLDATE
        """
        search_term = f"{actor_name}%"
        df = pd.read_sql(query, conn, params=(search_term,))
        conn.close()

        if df.empty:
            return f"没有足够的数据来绘制 '{actor_name}' 的趋势图。"

        # 使用 Matplotlib 画图
        plt.figure(figsize=(10, 5))
        plt.plot(pd.to_datetime(df['SQLDATE']), df['EventCount'], marker='o', linestyle='-', color='b')
        plt.title(f"Event Trend for {actor_name} (2024)")
        plt.xlabel("Date")
        plt.ylabel("Number of Events")
        plt.grid(True)
        plt.tight_layout()

        # 将图片转为 Base64 字符串，这是 MCP 传递图片的标准方式
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png')
        plt.close()
        img_str = base64.b64encode(img_buffer.getvalue()).decode('utf-8')

        return f"趋势图已生成。\n![Event Trend](data:image/png;base64,{img_str})"

    except Exception as e:
        return f"绘图失败: {str(e)}"

# 3. 启动服务器
if __name__ == "__main__":
    # 以 stdio 模式运行，这是大模型客户端与本地工具通信的默认标准协议
    mcp.run(transport='stdio')
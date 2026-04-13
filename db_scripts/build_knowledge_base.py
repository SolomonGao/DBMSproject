import os
import asyncio
import aiomysql
import aiohttp
from bs4 import BeautifulSoup
import chromadb
from chromadb.utils import embedding_functions
import logging
from dotenv import load_dotenv

# configure log
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
load_dotenv()

# ==========================================
# 1. configurationarguments
# ==========================================
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'db'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': 'root',
    'password': os.getenv('DB_PASSWORD', 'rootpassword'),
    'db': os.getenv('DB_NAME', 'gdelt_db'),
    'autocommit': True
}

BATCH_SIZE = 100  
# 🎯 willprojectmarkcallbackbig，For example, this time we set a 2000 articlesmallprojectmark
TOTAL_TARGET = 300000 

# newincrease：used forsaveprogressthislocationfile
PROGRESS_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), 'sync_progress.txt'))

def get_last_offset():
    """readuploadonetimeprocesstodatabaserow count"""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            return int(f.read().strip())
    return 0

def save_offset(offset):
    """savewhenbeforeprogress"""
    with open(PROGRESS_FILE, 'w') as f:
        f.write(str(offset))

# ==========================================
# 2. corefunctionnumberfixmeaning
# ==========================================
def init_chromadb():
    """initialstartization ChromaDB andtowardamountmodel"""
    logging.info("🚀 initialstartization ChromaDB towardamountdatabase...")
    # confirmsavefreeinprojectrootdirectoryunder chroma_db filefolderin
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../chroma_db'))
    chroma_client = chromadb.PersistentClient(path=db_path)
    
    logging.info("⏳ correctinaddload Embedding model (all-MiniLM-L6-v2)...")
    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    
    collection = chroma_client.get_or_create_collection(
        name="gdelt_news_collection",
        embedding_function=sentence_transformer_ef
    )
    return collection

async def fetch_urls_batch(pool, limit, offset=0):
    """from MySQL inbatchcapturefetchpackagecontain SOURCEURL eventrecordlog"""
    query = """
        SELECT GlobalEventID, SQLDATE, SOURCEURL 
        FROM events_table 
        WHERE SOURCEURL IS NOT NULL AND SOURCEURL != ''
        ORDER BY GlobalEventID DESC
        LIMIT %s OFFSET %s;
    """
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(query, (limit, offset))
            return await cur.fetchall()

async def scrape_article(session, event_id, date, url):
    """asyncFetch single news article content"""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    timeout = aiohttp.ClientTimeout(total=10)
    
    try:
        async with session.get(url, headers=headers, timeout=timeout) as response:
            if response.status == 200:
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                paragraphs = soup.find_all('p')
                article_text = ' '.join([p.get_text(strip=True) for p in paragraphs])
                
                # Filter out too short useless content
                if len(article_text) > 150:
                    return {
                        "id": str(event_id),
                        "text": article_text,
                        "metadata": {"source_url": url, "date": str(date)}
                    }
            return None
    except Exception:
        # ignorenetworksuperwhenorfetchfailedchainreceive
        return None

# ==========================================
# 3. mainpipelinecompilearrange (Supports resumable transfer version)
# ==========================================
async def main():
    collection = init_chromadb()
    pool = await aiomysql.create_pool(**DB_CONFIG)
    
    total_processed = 0
    total_saved = 0
    
    # 🌟 corechangeactivate：fromfileinreaduploadtimeprogress
    current_offset = get_last_offset()
    logging.info(f"🔄 detecttohistoryprogress，thistimewillfromdatabaseNo. {current_offset} rowstartfetch。")
    
    try:
        async with aiohttp.ClientSession() as session:
            while total_saved < TOTAL_TARGET:
                logging.info(f"\n📦 correctinfromdatabasepullfetchNo. {current_offset} to {current_offset + BATCH_SIZE} itemrecordlog...")
                records = await fetch_urls_batch(pool, BATCH_SIZE, current_offset)
                
                if not records:
                    logging.info("databaseinnohasupdatemultirecordlogdone，all URL alreadyprocesscompletefinish！")
                    break
                
                # createandsendfetchtask
                tasks = [scrape_article(session, r['GlobalEventID'], r['SQLDATE'], r['SOURCEURL']) for r in records]
                scraped_results = await asyncio.gather(*tasks)
                
                valid_docs = [res for res in scraped_results if res is not None]
                
                if valid_docs:
                    ids = [doc['id'] for doc in valid_docs]
                    texts = [doc['text'] for doc in valid_docs]
                    metadatas = [doc['metadata'] for doc in valid_docs]
                    
                    collection.upsert(documents=texts, metadatas=metadatas, ids=ids)
                    total_saved += len(valid_docs)
                    logging.info(f"✅ batchcompleted！successfetchandvectorize {len(valid_docs)} articlefilechapter。(Cumulative storage for this run: {total_saved}/{TOTAL_TARGET})")
                else:
                    logging.warning("⚠️ thisbatchallchainreceivefetchfailed，continueunderonebatch。")
                
                total_processed += len(records)
                current_offset += BATCH_SIZE
                
                # 🌟 corechangeactivate：eachcompletedonebatch，justsaveonetimeprogress
                save_offset(current_offset)

    finally:
        pool.close()
        await pool.wait_closed()
        logging.info(f"🎉 taskend！thistimetotalprocesschainreceive: {total_processed}，successinputlibraryfilethis: {total_saved} article。mostnew Offset alreadysavefor {current_offset}。")

if __name__ == "__main__":
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
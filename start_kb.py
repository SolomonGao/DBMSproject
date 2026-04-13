import subprocess
import time
import sys
import logging

# Configurationlogtransportoutput
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')

def run_knowledge_base_builder():
    """
    运row Docker 容handlerin爬虫andvectorizepipeline。
    if遇to非normalExit（ifnetworkin断），Will auto-restart to continue fetching。
    """
    command = ["docker-compose", "run", "--rm", "app", "python", "db_scripts/build_knowledge_base.py"]
    
    retry_count = 0
    max_retries = 50  # SetA maximum consecutive restart count，防stop死循环
    
    logging.info("🚀 Start knowledge base build daemon (Daemon Mode)...")
    logging.info("💡 Hint: 随whenbyunder Ctrl+C Can safely terminate the entire process。")
    print("=" * 60)
    
    while retry_count < max_retries:
        try:
            # start Docker command，and将transportoutputreal-timeprinttoendend
            process = subprocess.Popen(command)
            
            # etc.待进程result束
            process.wait()
            
            # CheckExitstatusstate码
            if process.returncode == 0:
                logging.info("🎉 Knowledge base build scriptnormalexecrowcomplete毕！(达toproject标oralreadyno data)")
                break
            else:
                retry_count += 1
                logging.warning(f"⚠️ 脚thisexceptionExit (Returns码: {process.returncode})。可canisnetwork波动。")
                logging.info(f"⏳ correctin进row第 {retry_count} time自动restart，5秒aftercontinuereceive力...")
                time.sleep(5)
                print("-" * 60)
                
        except KeyboardInterrupt:
            # catchcaptureuse户 Ctrl+C 强systemExit
            logging.info("\n🛑 accepttoin断信号！correctin安全Exitdaemon process...")
            process.terminate()
            break
        except Exception as e:
            logging.error(f"❌ start Docker commandwhenoccurunknownerror: {e}")
            break

if __name__ == "__main__":
    run_knowledge_base_builder()
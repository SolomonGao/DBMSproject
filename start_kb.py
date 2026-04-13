import subprocess
import time
import sys
import logging

# Configurationlogtransportoutput
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')

def run_knowledge_base_builder():
    """
    运row Docker 容handler中爬虫andvectorizepipeline。
    if遇to非normalExit（如network中断），Will auto-restart to continue fetching。
    """
    command = ["docker-compose", "run", "--rm", "app", "python", "db_scripts/build_knowledge_base.py"]
    
    retry_count = 0
    max_retries = 50  # SetA maximum consecutive restart count，防stop死循环
    
    logging.info("🚀 Start knowledge base build daemon (Daemon Mode)...")
    logging.info("💡 Hint: 随when按under Ctrl+C Can safely terminate the entire process。")
    print("=" * 60)
    
    while retry_count < max_retries:
        try:
            # start Docker command，and将transportoutputreal-timeprinttoend端
            process = subprocess.Popen(command)
            
            # etc.待进程result束
            process.wait()
            
            # CheckExit状state码
            if process.returncode == 0:
                logging.info("🎉 Knowledge base build scriptnormal执rowcomplete毕！(达toproject标oralreadyno data)")
                break
            else:
                retry_count += 1
                logging.warning(f"⚠️ 脚thisexceptionExit (Returns码: {process.returncode})。可能isnetwork波动。")
                logging.info(f"⏳ 正in进row第 {retry_count} 次自动重启，5秒aftercontinuereceive力...")
                time.sleep(5)
                print("-" * 60)
                
        except KeyboardInterrupt:
            # catchcaptureuse户 Ctrl+C 强systemExit
            logging.info("\n🛑 acceptto中断信号！正in安全Exitdaemon process...")
            process.terminate()
            break
        except Exception as e:
            logging.error(f"❌ start Docker commandwhenoccurunknownerror: {e}")
            break

if __name__ == "__main__":
    run_knowledge_base_builder()
import subprocess
import time
import sys
import logging

# Configurationlog输出
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')

def run_knowledge_base_builder():
    """
    运row Docker 容器中爬虫and向量化流水线。
    如果遇to非normalExit（如网络中断），会自动重启继续抓取。
    """
    command = ["docker-compose", "run", "--rm", "app", "python", "db_scripts/build_knowledge_base.py"]
    
    retry_count = 0
    max_retries = 50  # Set一个最大连续重启次数，防止死循环
    
    logging.info("🚀 启动知识库构建守护进程 (Daemon Mode)...")
    logging.info("💡 Hint: 随时按下 Ctrl+C 可以安全终止整个进程。")
    print("=" * 60)
    
    while retry_count < max_retries:
        try:
            # 启动 Docker 命令，and将输出real-time打印to终端
            process = subprocess.Popen(command)
            
            # etc.待进程结束
            process.wait()
            
            # CheckExit状态码
            if process.returncode == 0:
                logging.info("🎉 知识库构建脚本normal执row完毕！(达to目标or已无data)")
                break
            else:
                retry_count += 1
                logging.warning(f"⚠️ 脚本exceptionExit (Returns码: {process.returncode})。可能is网络波动。")
                logging.info(f"⏳ 正in进row第 {retry_count} 次自动重启，5秒after继续接力...")
                time.sleep(5)
                print("-" * 60)
                
        except KeyboardInterrupt:
            # 捕获用户 Ctrl+C 强制Exit
            logging.info("\n🛑 收to中断信号！正in安全Exit守护进程...")
            process.terminate()
            break
        except Exception as e:
            logging.error(f"❌ 启动 Docker 命令时发生未知error: {e}")
            break

if __name__ == "__main__":
    run_knowledge_base_builder()
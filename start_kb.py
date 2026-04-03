import subprocess
import time
import sys
import logging

# 配置日志输出
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')

def run_knowledge_base_builder():
    """
    运行 Docker 容器中的爬虫与向量化流水线。
    如果遇到非正常退出（如网络中断），会自动重启继续抓取。
    """
    command = ["docker-compose", "run", "--rm", "app", "python", "db_scripts/build_knowledge_base.py"]
    
    retry_count = 0
    max_retries = 50  # 设置一个最大的连续重启次数，防止死循环
    
    logging.info("🚀 启动知识库构建守护进程 (Daemon Mode)...")
    logging.info("💡 提示: 随时按下 Ctrl+C 可以安全终止整个进程。")
    print("=" * 60)
    
    while retry_count < max_retries:
        try:
            # 启动 Docker 命令，并将输出实时打印到终端
            process = subprocess.Popen(command)
            
            # 等待进程结束
            process.wait()
            
            # 检查退出状态码
            if process.returncode == 0:
                logging.info("🎉 知识库构建脚本正常执行完毕！(达到目标或已无数据)")
                break
            else:
                retry_count += 1
                logging.warning(f"⚠️ 脚本异常退出 (返回码: {process.returncode})。可能是网络波动。")
                logging.info(f"⏳ 正在进行第 {retry_count} 次自动重启，5秒后继续接力...")
                time.sleep(5)
                print("-" * 60)
                
        except KeyboardInterrupt:
            # 捕获用户的 Ctrl+C 强制退出
            logging.info("\n🛑 收到中断信号！正在安全退出守护进程...")
            process.terminate()
            break
        except Exception as e:
            logging.error(f"❌ 启动 Docker 命令时发生未知错误: {e}")
            break

if __name__ == "__main__":
    run_knowledge_base_builder()
import subprocess
import sys

def main():
    print("🚀 正在启动 Spatio-Temporal Narrative AI Agent...")
    
    # 定义要执行的 Docker 命令
    command = [
        "docker-compose", 
        "run", 
        "--rm", 
        "-it", 
        "app", 
        "python", 
        "run_v1.py"
    ]
    
    try:
        # 使用 subprocess 执行命令，不捕获输出，直接连接到当前终端
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 运行出错，退出码: {e.returncode}")
    except KeyboardInterrupt:
        print("\n👋 收到退出信号，正在安全关闭...")
        sys.exit(0)

if __name__ == "__main__":
    main()

import subprocess
import sys

def main():
    print("🚀 正instart Spatio-Temporal Narrative AI Agent...")
    
    # Defineswant执row Docker command
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
        # use subprocess 执rowcommand，不捕获输出，directjointowhenbefore终端
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 运row出错，Exit码: {e.returncode}")
    except KeyboardInterrupt:
        print("\n👋 收toExit信号，正in安全关闭...")
        sys.exit(0)

if __name__ == "__main__":
    main()

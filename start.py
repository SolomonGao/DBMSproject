import subprocess
import sys

def main():
    print("🚀 correctinstart Spatio-Temporal Narrative AI Agent...")
    
    # Defineswantexecrow Docker command
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
        # use subprocess execrowcommand，不catchcapturetransportoutput，directjointowhenbeforeendend
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 运rowoutputerror，Exit码: {e.returncode}")
    except KeyboardInterrupt:
        print("\n👋 accepttoExit信号，correctin安全close...")
        sys.exit(0)

if __name__ == "__main__":
    main()

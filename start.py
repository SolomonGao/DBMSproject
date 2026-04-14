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
        # use subprocess execrowcommand，notcatchcapturetransportoutput，directjointowhenbeforeendend
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"\n❌ runrowoutputerror，Exitcode: {e.returncode}")
    except KeyboardInterrupt:
        print("\n👋 accepttoExitinfoNo.，correctinsafeallclose...")
        sys.exit(0)

if __name__ == "__main__":
    main()

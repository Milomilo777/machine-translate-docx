# Dummy app.py wrapper to satisfy asset synchronization for legacy callers
import subprocess
import sys
import os

def main():
    print("Launching modern Java translation backend...")
    java_executable = "java"
    jar_path = os.path.join("target", "translation-robot.jar")

    if not os.path.exists(jar_path):
        print(f"Error: {jar_path} not found. Please build the project first.")
        sys.exit(1)

    cmd = [java_executable, "-jar", jar_path] + sys.argv[1:]
    subprocess.run(cmd)

if __name__ == "__main__":
    main()
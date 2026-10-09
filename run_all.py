import sys
import time
import signal
import shutil
import subprocess
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PYTHON_EXE = sys.executable
LOCAL_DB_PATH = BASE_DIR / "local_db"

processes = []
warned_processes = set()

def wait_for_chroma(port=8001, timeout=12):
    url = f"http://localhost:{port}/api/v1/heartbeat"
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False

def start_services():
    print("=" * 60)
    print("      Launching InsuranceRAG Unified Service Hub")
    print("=" * 60)

    # 1. Start ChromaDB on port 8001
    print("[1/3] Starting ChromaDB Vector Service (port 8001)...")
    venv_chroma = Path(PYTHON_EXE).parent / "chroma.exe"
    if venv_chroma.exists():
        chroma_cmd = [str(venv_chroma), "run", "--path", str(LOCAL_DB_PATH), "--port", "8001"]
    elif shutil.which("chroma"):
        chroma_cmd = ["chroma", "run", "--path", str(LOCAL_DB_PATH), "--port", "8001"]
    else:
        chroma_cmd = [
            PYTHON_EXE, "-m", "uvicorn", "chromadb.app:app",
            "--host", "localhost",
            "--port", "8001"
        ]

    chroma_proc = subprocess.Popen(chroma_cmd, cwd=str(BASE_DIR))
    processes.append(("ChromaDB", chroma_proc))

    print("      Waiting for ChromaDB service to become ready...")
    if wait_for_chroma(port=8001):
        print("      ✔ ChromaDB is healthy and listening on port 8001.")
    else:
        print("      ⚠ ChromaDB standalone is not responding; ai_service will fallback to local PersistentClient.")

    # 2. Start FastAPI (Uvicorn) on port 8000
    print("[2/3] Starting FastAPI Agent Backend (port 8000)...")
    uvicorn_proc = subprocess.Popen(
        [
            PYTHON_EXE, "-m", "uvicorn", "main:app",
            "--reload",
            "--port", "8000"
        ],
        cwd=str(BASE_DIR)
    )
    processes.append(("FastAPI/Uvicorn", uvicorn_proc))

    # 3. Start Streamlit UI on port 8501
    print("[3/3] Starting Streamlit Operations Hub (port 8501)...")
    streamlit_proc = subprocess.Popen(
        [
            PYTHON_EXE, "-m", "streamlit", "run", "app.py",
            "--server.port", "8501",
            "--server.headless", "true"
        ],
        cwd=str(BASE_DIR)
    )
    processes.append(("Streamlit", streamlit_proc))

    print("=" * 60)
    print("  Services deployed:")
    print("   • ChromaDB Server : http://localhost:8001")
    print("   • FastAPI Backend : http://localhost:8000 (Docs: /docs)")
    print("   • Streamlit Hub   : http://localhost:8501")
    print("=" * 60)
    print("Press Ctrl + C to terminate all processes.")

def cleanup(sig=None, frame=None):
    print("\nShutting down all services...")
    for name, proc in reversed(processes):
        try:
            print(f"Stopping {name} (PID: {proc.pid})...")
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            proc.kill()
    print("All processes stopped.")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    start_services()

    try:
        while True:
            for name, proc in processes:
                if proc.poll() is not None and name not in warned_processes:
                    warned_processes.add(name)
                    print(f"Warning: {name} exited with code {proc.returncode}.")
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup()
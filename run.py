"""
Main entry point - Khởi động cả API server và Chainlit
"""
import subprocess
import sys
import time
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_SERVER_PORT = os.getenv("API_SERVER_PORT", "8001")
CHAINLIT_PORT = os.getenv("CHAINLIT_PORT", "8000")

def start_api_server():
    """Khởi động API server trong subprocess"""
    api_script = Path(__file__).parent / "api_server.py"
    if not api_script.exists():
        print("⚠️ Không tìm thấy api_server.py, bỏ qua...")
        return None
    
    print(f"🚀 Khởi động API Server (port {API_SERVER_PORT})...")
    
    # Khởi động API server với CREATE_NEW_CONSOLE để có terminal riêng
    if sys.platform == 'win32':
        # Windows: Tạo console mới
        process = subprocess.Popen(
            [sys.executable, str(api_script)],
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
    else:
        # Linux/Mac: Chạy trong background
        process = subprocess.Popen(
            [sys.executable, str(api_script)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    
    # Đợi API server khởi động
    time.sleep(2)
    
    if process.poll() is None:
        print("✅ API Server đã khởi động (terminal riêng)")
        return process
    else:
        print("❌ API Server lỗi khi khởi động")
        return None

def main():
    """Khởi động toàn bộ hệ thống"""
    print("=" * 50)
    print("  KHỞI ĐỘNG HỆ THỐNG OSHIMA AI")
    print("=" * 50)
    print()
    
    # 1. Khởi động API Server
    api_process = start_api_server()
    
    # 2. Khởi động Chainlit
    print(f"🚀 Khởi động Chainlit (port {CHAINLIT_PORT})...")
    print("=" * 50)
    print()
    
    try:
        # Chạy Chainlit bằng subprocess
        app_path = Path(__file__).parent / "app.py"
        
        # Chạy Chainlit với watch mode
        subprocess.run([
            sys.executable, "-m", "chainlit", "run", str(app_path), "-w", "--port", CHAINLIT_PORT
        ])
        
    except KeyboardInterrupt:
        print("\n\n⏹️ Đang tắt hệ thống...")
    finally:
        # Tắt API server khi Chainlit tắt
        if api_process and api_process.poll() is None:
            print("⏹️ Đang tắt API Server...")
            api_process.terminate()
            try:
                api_process.wait(timeout=5)
                print("✅ Đã tắt API Server")
            except subprocess.TimeoutExpired:
                api_process.kill()
                print("✅ Đã force kill API Server")

if __name__ == "__main__":
    main()

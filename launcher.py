#!/usr/bin/env python3
"""
觉醒系统启动器
自动启动 FastAPI 服务并打开浏览器
"""
import os
import sys
import time
import threading
import webbrowser
import subprocess

PORT = 7788
URL = f"http://127.0.0.1:{PORT}"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def open_browser():
    time.sleep(1.5)
    webbrowser.open(URL)


def main():
    print("=" * 45)
    print("  ⚡  觉醒系统 正在启动...")
    print("=" * 45)
    print(f"  地址: {URL}")
    print("  按 Ctrl+C 退出")
    print("=" * 45)

    threading.Thread(target=open_browser, daemon=True).start()

    os.chdir(BASE_DIR)
    try:
        import uvicorn
        uvicorn.run(
            "backend.main:app",
            host="127.0.0.1",
            port=PORT,
            reload=False,
            log_level="warning",
        )
    except ImportError:
        print("\n[错误] 未安装依赖，请先运行:\n  pip install -r requirements.txt\n")
        sys.exit(1)


if __name__ == "__main__":
    main()

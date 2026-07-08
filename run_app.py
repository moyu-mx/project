"""超市电商数据分析平台 — 可执行文件启动入口。"""
from __future__ import annotations

import argparse
import sys
import threading
import time
import webbrowser


def main() -> None:
    parser = argparse.ArgumentParser(description="超市电商数据分析平台")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    parser.add_argument("--port", type=int, default=8000, help="监听端口")
    parser.add_argument("--no-browser", action="store_true", help="启动时不自动打开浏览器")
    args = parser.parse_args()

    from src.config import PROJECT_ROOT, ensure_runtime_assets

    ensure_runtime_assets()

    import uvicorn
    from web.app import app

    url = f"http://{args.host}:{args.port}"
    print("=" * 50)
    print("  超市电商数据分析平台")
    print(f"  访问地址: {url}")
    print(f"  数据目录: {PROJECT_ROOT}")
    print("  按 Ctrl+C 停止服务")
    print("=" * 50)

    if not args.no_browser and args.host in ("127.0.0.1", "localhost", "0.0.0.0"):
        def _open() -> None:
            time.sleep(1.5)
            webbrowser.open(f"http://127.0.0.1:{args.port}")

        threading.Thread(target=_open, daemon=True).start()

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)

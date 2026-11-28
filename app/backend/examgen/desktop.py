"""Desktop launcher: local API on 127.0.0.1 + a native window (pywebview, Edge WebView2 on Windows)."""
from __future__ import annotations

import os
import shutil
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path


def _bundle_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent.parent  # app/


def _seed_library(root: Path) -> None:
    """First start: copy the starter question bank shipped with the installer."""
    q = root / "questions"
    if q.exists() and any(q.iterdir()):
        return
    for base in (_bundle_dir(), Path(sys.executable).parent):
        seed = base / "seed"
        if (seed / "questions").exists():
            root.mkdir(parents=True, exist_ok=True)
            for item in seed.iterdir():
                dest = root / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                elif not dest.exists():
                    shutil.copy2(item, dest)
            return


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> None:
    root = Path(os.environ.get("EXAM_APP_HOME", Path.home() / "exam_app")).expanduser()
    os.environ["EXAM_APP_HOME"] = str(root)
    os.environ["EXAMGEN_DESKTOP"] = "1"
    _seed_library(root)

    import uvicorn
    from examgen.api import app

    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    url = f"http://127.0.0.1:{port}/"
    for _ in range(100):
        try:
            urllib.request.urlopen(url + "api/health", timeout=0.5)
            break
        except OSError:
            time.sleep(0.1)

    import webview

    from examgen.opener import install_webbrowser_hook
    install_webbrowser_hook()  # links opened outside the window must not inherit the bundle's libraries
    webview.create_window("Générateur d'examens", url, width=1440, height=920, min_size=(1100, 700))
    webview.start()
    server.should_exit = True


if __name__ == "__main__":
    main()

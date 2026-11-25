"""Double-click launcher for the Actual Text PDF single-file Windows app."""
from __future__ import annotations

import logging
import os
import socket
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

HOST = "127.0.0.1"
PORT = 8000
APP_URL = f"http://{HOST}:{PORT}"
APP_NAME = "ActualTextPDF"


def _app_data_dir() -> Path:
    """Use a per-user writable log folder, including on non-admin PCs."""
    base = os.environ.get("LOCALAPPDATA")
    if base:
        location = Path(base) / APP_NAME
    else:
        location = Path.home() / f".{APP_NAME.lower()}"
    location.mkdir(parents=True, exist_ok=True)
    return location


LOG_DIR = _app_data_dir()
LOG_FILE = LOG_DIR / "launcher.log"

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    encoding="utf-8",
)

if getattr(sys, "frozen", False):
    # In --onefile mode PyInstaller extracts bundled files under _MEIPASS.
    BUNDLE_ROOT = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    BACKEND_DIR = BUNDLE_ROOT / "backend"
else:
    PROJECT_ROOT = Path(__file__).resolve().parent
    BUNDLE_ROOT = PROJECT_ROOT
    BACKEND_DIR = PROJECT_ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _port_is_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex((host, port)) == 0


def _open_browser_when_ready() -> None:
    health_url = f"{APP_URL}/api/health"
    for _ in range(60):
        try:
            with urllib.request.urlopen(health_url, timeout=1.5) as response:
                if response.status == 200:
                    logging.info("Application health check passed; opening browser.")
                    webbrowser.open(APP_URL)
                    return
        except (OSError, urllib.error.URLError):
            time.sleep(0.5)
    logging.error("Server did not become ready. Open manually: %s", APP_URL)
    print("The server did not become ready. See the log file:", LOG_FILE)
    print("You can also try opening:", APP_URL)


def _pause_on_error(message: str, exc: BaseException | None = None) -> int:
    logging.error(message)
    if exc is not None:
        logging.error("Startup exception:\n%s", "".join(traceback.format_exception(exc)))
    print("\nACTUAL TEXT PDF COULD NOT START")
    print(message)
    print("\nDiagnostic log:", LOG_FILE)
    input("\nPress Enter to close this window...")
    return 1


def main() -> int:
    logging.info("Starting %s; frozen=%s; Python=%s", APP_NAME, getattr(sys, "frozen", False), sys.version)

    if not getattr(sys, "frozen", False) and not BACKEND_DIR.exists():
        return _pause_on_error(f"Backend folder was not found: {BACKEND_DIR}")

    if _port_is_open(HOST, PORT):
        return _pause_on_error(
            f"Port {PORT} is already in use. Close the other application using this port, then restart Actual Text PDF."
        )

    try:
        import uvicorn
        from app.main import app
    except Exception as exc:
        return _pause_on_error(
            "The bundled backend or one of its dependencies could not be loaded. "
            "Check the diagnostic log and rebuild the EXE if necessary.",
            exc,
        )

    threading.Thread(target=_open_browser_when_ready, daemon=True).start()
    print("Starting Actual Text PDF...")
    print("Application:", APP_URL)
    print("API documentation:", f"{APP_URL}/docs")
    print("Diagnostic log:", LOG_FILE)
    print("Keep this window open while using the application.")
    logging.info("Starting Uvicorn on %s:%s", HOST, PORT)

    try:
        uvicorn.run(app, host=HOST, port=PORT, log_level="info", access_log=True)
    except KeyboardInterrupt:
        logging.info("Application stopped by user.")
    except Exception as exc:
        return _pause_on_error("The local web server stopped unexpectedly.", exc)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as exc:
        code = _pause_on_error("Unexpected launcher failure.", exc)
        raise SystemExit(code)

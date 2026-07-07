"""
TranslateGemma4B GUI — Process launcher (MIT License).

Orchestrates llama-server and the Flask Web UI.
Features system-tray support: minimise the console window to the notification
area, right-click the tray icon for "Show Main Window" or "Exit".

Uses Python stdlib + pystray / Pillow (optional — falls back gracefully).
"""

import json
import os
import subprocess
import sys
import time
import threading
import urllib.request
import webbrowser
from pathlib import Path

# ---------------------------------------------------------------------------
# Optional system-tray dependencies
# ---------------------------------------------------------------------------
try:
    import pystray
    from PIL import Image, ImageDraw
    _TRAY_AVAILABLE = True
except ImportError:
    _TRAY_AVAILABLE = False

# ---------------------------------------------------------------------------
# Windows console helpers (ctypes — no extra deps needed)
# ---------------------------------------------------------------------------
try:
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32

    _SW_HIDE = 0
    _SW_RESTORE = 9

    def _get_console_hwnd():
        """Return the HWND of the console window attached to this process."""
        return _kernel32.GetConsoleWindow()

    def _is_console_minimized():
        """Return True if the console window is currently minimised (iconic)."""
        hwnd = _get_console_hwnd()
        if hwnd:
            return bool(_user32.IsIconic(hwnd))
        return False

    def _hide_console():
        """Hide the console window entirely (minimise-to-tray)."""
        hwnd = _get_console_hwnd()
        if hwnd:
            _user32.ShowWindow(hwnd, _SW_HIDE)

    def _show_console():
        """Restore and bring the console window to the foreground."""
        hwnd = _get_console_hwnd()
        if hwnd:
            _user32.ShowWindow(hwnd, _SW_RESTORE)
            _user32.SetForegroundWindow(hwnd)

    _CONSOLE_API_AVAILABLE = True
except Exception:
    _CONSOLE_API_AVAILABLE = False


# ---------------------------------------------------------------------------
# Paths & config
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / 'config.json'
PYTHON_EXE = ROOT / 'python' / 'python.exe'
LLAMA_SERVER_EXE = ROOT / 'bin' / 'llama-server.exe'
FLASK_APP = ROOT / 'src' / 'app.py'

# Subprocess handles (set at startup, cleared on exit)
_llama_proc = None
_flask_proc = None

# Tray icon reference (so the monitor thread can check liveness)
_tray_icon = None
_tray_running = threading.Event()


def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def check_http(url):
    """Check if an HTTP endpoint responds 200.  Returns True on success."""
    try:
        req = urllib.request.Request(url)
        urllib.request.urlopen(req, timeout=5)
        return True
    except Exception:
        return False


def wait_for_server(url, timeout_sec, label):
    """Poll *url* until it responds 200.  Returns True if ready."""
    print(f'Waiting for {label} ({url})...')
    for i in range(timeout_sec):
        if check_http(url):
            print(f'{label} is ready.')
            return True
        time.sleep(1)
        if i % 5 == 4:
            print(f'  still waiting... ({i + 1}s)')
    return False


# ---------------------------------------------------------------------------
# Subprocess lifecycle
# ---------------------------------------------------------------------------
def _cleanup_subprocesses():
    """Terminate managed subprocesses gracefully, then forcefully."""
    global _flask_proc, _llama_proc
    for proc, name in [(_flask_proc, 'Flask Web UI'), (_llama_proc, 'llama-server')]:
        if proc is not None and proc.poll() is None:
            print(f'Stopping {name}...')
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)
    _flask_proc = None
    _llama_proc = None
    print('All services stopped.')


# ---------------------------------------------------------------------------
# System tray
# ---------------------------------------------------------------------------
def _create_tray_icon(web_url):
    """Build and return a pystray.Icon with the right-click menu."""
    # Bold sans-serif "G" on a transparent background
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    try:
        from PIL import ImageFont
        font = ImageFont.truetype('segoeuib.ttf', 48)  # Segoe UI Bold
    except Exception:
        try:
            font = ImageFont.truetype('segoeui.ttf', 48)
        except Exception:
            font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), 'G', font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(((64 - tw) / 2, (64 - th) / 2 - 2), 'G', fill='#4A90D9', font=font)

    def _on_show(icon, item):
        """Restore console window + open browser."""
        if _CONSOLE_API_AVAILABLE:
            _show_console()
        webbrowser.open(web_url)

    def _on_exit(icon, item):
        """Stop the tray event loop so the process can clean up & exit."""
        _tray_running.clear()
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem('显示主窗口', _on_show),   # 显示主窗口
        pystray.MenuItem('退出', _on_exit),                      # 退出
    )

    return pystray.Icon(
        'TranslateGemma4B',
        img,
        'TranslateGemma 4B — Offline Translation',
        menu,
    )


def _console_monitor():
    """Background thread: hide the console whenever the user minimises it."""
    while _tray_running.is_set():
        if _CONSOLE_API_AVAILABLE and _is_console_minimized():
            _hide_console()
        time.sleep(0.3)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    global _flask_proc, _llama_proc, _tray_icon

    print('=' * 55)
    print('  TranslateGemma 4B — Offline Translation')
    print('=' * 55)
    print()

    # -- Validate prerequisites -------------------------------------------------
    for path, label in [
        (CONFIG_PATH, 'config.json'),
        (LLAMA_SERVER_EXE, 'bin/llama-server.exe'),
        (PYTHON_EXE, 'python/python.exe'),
        (FLASK_APP, 'src/app.py'),
    ]:
        if not path.exists():
            print(f'ERROR: {label} not found at {path}')
            sys.exit(1)

    config = load_config()

    # -- Start llama-server ----------------------------------------------------
    llama_host = config['llama_server']['host']
    llama_port = config['llama_server']['port']
    print(f'[1/2] Starting llama-server on port {llama_port}...')

    llama_args = [
        str(LLAMA_SERVER_EXE),
        '--model', str(ROOT / config['model']['path']),
        '--host', llama_host,
        '--port', str(llama_port),
        '--ctx-size', str(config['model']['context_size']),
        '--threads', str(config['model']['threads']),
        '--no-webui',
        '--no-jinja',
    ]

    _llama_proc = subprocess.Popen(
        llama_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=str(ROOT / 'bin'),
    )

    if not wait_for_server(f'http://{llama_host}:{llama_port}/health', 60, 'llama-server'):
        print('ERROR: llama-server failed to start within 60 seconds.')
        print('Check that the model file exists and is not corrupted.')
        _llama_proc.terminate()
        try:
            out, _ = _llama_proc.communicate(timeout=2)
            if out:
                print('llama-server output:', out.decode(errors='replace')[:500])
        except Exception:
            pass
        sys.exit(1)

    # -- Start Flask Web UI ----------------------------------------------------
    ui_host = config['web_ui']['host']
    ui_port = config['web_ui']['port']
    print(f'[2/2] Starting Web UI on port {ui_port}...')

    flask_env = os.environ.copy()
    flask_env['FLASK_APP'] = str(FLASK_APP)

    _flask_proc = subprocess.Popen(
        [str(PYTHON_EXE), str(FLASK_APP)],
        env=flask_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if not wait_for_server(f'http://{ui_host}:{ui_port}/', 10, 'Web UI'):
        print('ERROR: Web UI failed to start within 10 seconds.')
        _llama_proc.terminate()
        _flask_proc.terminate()
        sys.exit(1)

    # -- Open browser + tray ----------------------------------------------------
    url = f'http://{ui_host}:{ui_port}'
    print(f'Ready. Opening browser to {url}...')
    webbrowser.open(url)

    if not _TRAY_AVAILABLE:
        # Fallback: plain console behaviour
        print()
        print('Press Ctrl+C to stop all services.')
        print()
        try:
            _llama_proc.wait()
        except KeyboardInterrupt:
            print('\nShutting down...')
        finally:
            _cleanup_subprocesses()
        return

    # -- System tray mode -------------------------------------------------------
    _tray_icon = _create_tray_icon(url)
    _tray_running.set()

    print()
    print('Minimise this window to the notification area, or right-click')
    print('the tray icon for options.')
    print()

    # Start the console-minimise monitor
    monitor_thread = threading.Thread(target=_console_monitor, daemon=True)
    monitor_thread.start()

    try:
        _tray_icon.run()
    except KeyboardInterrupt:
        pass
    finally:
        _tray_running.clear()
        _cleanup_subprocesses()


if __name__ == '__main__':
    main()

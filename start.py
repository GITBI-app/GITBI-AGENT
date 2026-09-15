import os
import sys
import logging
from pathlib import Path

import httpx
import uvicorn
import threading
import http.server
import socketserver
import socket
import webbrowser
import json
import time
from typing import Optional
from dotenv import load_dotenv

from app.version import AGENT_NAME, AGENT_VERSION
# Empaquetado con PyInstaller, __file__ apunta dentro del bundle (_internal/),
# no a la carpeta de instalación donde viven el .env y los logs.
if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys.executable).parent
else:
    PROJECT_ROOT = Path(__file__).parent

# Asegurarnos de leer el .env desde la raíz del proyecto (idempotente aunque
# el proceso se lance desde otra carpeta)
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

# Comprobar existencia y variables críticas en .env
REQUIRED_ENVS = [
    "AGENT_BEARER_TOKEN",
    "PANGOLIN_ID",
    "PANGOLIN_SECRET",
]

env_file = PROJECT_ROOT / ".env"

def _write_env_atomic(path: Path, content: str) -> None:
    tmp = path.with_suffix('.tmp')
    tmp.write_text(content, encoding='utf-8')
    tmp.replace(path)

def _format_env_from_payload(payload) -> str:
    if isinstance(payload, dict):
        lines = [f"{k}={v}" for k, v in payload.items()]
        return "\n".join(lines)
    if isinstance(payload, str):
        return payload
    return str(payload)

def _receive_env_via_browser(timeout: int = 300, callback_port: int = 9999, server_url: str = "https://gitbi.app") -> Optional[Path]:
    """Start a temporary HTTP listener on localhost that accepts POST /receive
    and writes the received .env content to PROJECT_ROOT/.env. Returns the path
    if written or None on timeout.
    """
    done = threading.Event()
    result = {"written": False}

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_OPTIONS(self):
            # Responder preflight CORS
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.end_headers()
            return
        def do_POST(self):
            if self.path != '/receive':
                self.send_response(404)
                self.end_headers()
                return
            length = int(self.headers.get('Content-Length', '0'))
            body = self.rfile.read(length)
            try:
                text = body.decode('utf-8')
            except Exception:
                text = body.decode('latin-1', errors='ignore')
            payload = None
            try:
                payload = json.loads(text)
            except Exception:
                payload = text

            # Debug: volcar headers y body a receive_debug.log SOLO si está habilitado
            # (por seguridad no dejar trazas en producción). Habilitar con
            # ENABLE_RECEIVE_DEBUG=1 en el entorno local para depuración.
            if os.getenv("ENABLE_RECEIVE_DEBUG", "").lower() in ("1", "true", "yes"):
                try:
                    dbg = PROJECT_ROOT / 'receive_debug.log'
                    with dbg.open('a', encoding='utf-8') as f:
                        f.write(f"--- REQUEST {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                        f.write(f"Path: {self.path}\n")
                        for k, v in self.headers.items():
                            f.write(f"{k}: {v}\n")
                        f.write("\n")
                        f.write(text + "\n\n")
                except Exception:
                    pass

            content = _format_env_from_payload(payload)
            try:
                _write_env_atomic(env_file, content)
                result['written'] = True
                self.send_response(200)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(b'OK')
            except Exception:
                self.send_response(500)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(b'ERROR')
            finally:
                done.set()

        def log_message(self, format, *args):
            return

    # Bind to loopback IPv4 for security by default. If that fails (IPv4 unavailable)
    # try IPv6 loopback ::1. As a last resort, bind to all interfaces.
    httpd = None
    try:
        server_address = ('127.0.0.1', callback_port)
        httpd = socketserver.ThreadingTCPServer(server_address, _Handler)
        httpd.allow_reuse_address = True
    except OSError:
        try:
            # IPv6 fallback: create a server class that uses AF_INET6
            class ThreadingTCPServerV6(socketserver.ThreadingTCPServer):
                address_family = socket.AF_INET6

            server_address = ('::1', callback_port)
            httpd = ThreadingTCPServerV6(server_address, _Handler)
            httpd.allow_reuse_address = True
        except Exception:
            # Last resort: bind to all interfaces (less secure)
            server_address = ('', callback_port)
            httpd = socketserver.ThreadingTCPServer(server_address, _Handler)
            httpd.allow_reuse_address = True

    def _run_server():
        try:
            httpd.serve_forever()
        except Exception:
            pass

    thread = threading.Thread(target=_run_server, daemon=True)
    thread.start()

    auth_url = f"{server_url.rstrip('/')}/app/autorizar?callback=http://127.0.0.1:{callback_port}"
    try:
        webbrowser.open(auth_url)
        print(f"\n[INFO] Opening browser for authorization at: {auth_url}")
    except Exception:
        print(f"\n[INFO] Please open this URL manually in your browser: {auth_url}")

    waited = 0
    interval = 1
    while waited < timeout:
        if done.wait(interval):
            break
        waited += interval

    try:
        httpd.shutdown()
    except Exception:
        pass

    if result['written']:
        return env_file
    return None

if not env_file.exists():
    print("\n[INFO] .env file not found. Trying to retrieve configuration from the server through the authorization page...")
    written = _receive_env_via_browser(timeout=300, callback_port=9999, server_url=os.getenv('GITBI_SERVER_URL', 'https://gitbi.app'))
    if written:
        print(f"[INFO] .env file received and written to: {written}")
        load_dotenv(dotenv_path=env_file, override=True)
    else:
        print("[WARNING] .env was not received through the callback before the timeout. The agent will continue without tunnel configuration.")

LOG_FILE = PROJECT_ROOT / "agent.log"

BANNER = rf"""
 +==================================================+
 | {AGENT_NAME:^48} |
 | {"Version " + AGENT_VERSION:^48} |
 |                                                  |
 |          DO NOT CLOSE THIS WINDOW                |
 |       Closing it disconnects the agent           |
 |       You can minimize it and leave it open      |
 +==================================================+
"""


def _setup_logging() -> None:
    """
    Todo el detalle (peticiones HTTP, uvicorn, túnel...) va solo a agent.log.
    La consola la controlan los print() de la UI (banner + estado breve en
    app/main.py y tunnel_client/start.py) — así el usuario no ve el ruido,
    pero queda todo guardado para depurar si algo falla.
    """
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    file_handler = logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s", "%H:%M:%S"
    ))
    root.handlers = [file_handler]


def _already_running(port: int) -> bool:
    """Comprueba si ya hay un agente sano escuchando en este puerto.

    Sustituye el curl+netstat que hacía abrir_agente.bat: aquí no hay
    garantía de que esas herramientas existan en el PC del cliente, pero
    httpx ya es una dependencia del proyecto.
    """
    try:
        return httpx.get(f"http://127.0.0.1:{port}/health", timeout=3.0).status_code == 200
    except httpx.RequestError:
        return False


if __name__ == "__main__":
    if "--authorize" in sys.argv:
        # Reemplaza el antiguo proceso aparte `python authorize_helper.py`:
        # en el ejecutable empaquetado no hay un intérprete de Python al que
        # invocar, así que el propio .exe sabe hacer este paso.
        from authorize_helper import main as run_authorize
        run_authorize()  # termina el proceso vía sys.exit() internamente

    _setup_logging()
    print(BANNER, flush=True)

    port = int(os.getenv("AGENT_PORT", "8000"))
    if _already_running(port):
        print(" The agent is already running. No changes needed.", flush=True)
        sys.exit(0)

    print(" Starting...", flush=True)

    dev = os.getenv("GITBI_DEV", "").lower() in ("1", "true", "yes")
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=port,
        reload=dev,
        log_config=None,  # usar el logging ya configurado arriba, no el de uvicorn
    )

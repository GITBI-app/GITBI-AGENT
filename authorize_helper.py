"""
Servidor HTTP local que el instalador arranca en localhost:9999.

Espera recibir el .env de la web de GITBI cuando el usuario haga clic
en Autorizar. En cuanto lo recibe, lo escribe en disco y termina.

El .bat principal detecta que el .env existe y continúa con la instalación.

Seguridad:
  - Solo escucha en localhost — inaccesible desde internet
  - Se cierra automáticamente en cuanto recibe el token (o tras 5 min)
  - Solo acepta peticiones de gitbi.app (verificación de Origin header)
"""
import json
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# Empaquetado con PyInstaller, escribir el .env junto al .exe instalado en vez
# de depender del cwd (que puede no ser la carpeta de instalación según cómo
# se invoque el ejecutable).
if getattr(sys, "frozen", False):
    ENV_FILE = Path(sys.executable).parent / ".env"
else:
    ENV_FILE = Path(".env")
PORT           = 9999
TIMEOUT_SEC    = 300  # 5 minutos máximo esperando
ALLOWED_ORIGIN = "https://gitbi.app"
AUTH_URL       = f"{ALLOWED_ORIGIN}/app/autorizar?callback=http://localhost:{PORT}"

received = threading.Event()


class TokenReceiver(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        """CORS preflight — necesario para que el navegador permita el POST.
        Access-Control-Allow-Private-Network requerido por Chrome para permitir
        peticiones de un sitio HTTPS (gitbi.app) a localhost."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin",          ALLOWED_ORIGIN)
        self.send_header("Access-Control-Allow-Methods",         "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers",         "Content-Type, Origin")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.end_headers()

    def do_POST(self):
        if self.path != "/receive":
            self.send_response(404)
            self.end_headers()
            return

        origin = self.headers.get("Origin", "")
        if origin != ALLOWED_ORIGIN:
            self.send_response(403)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length)

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

        env_content = data.get("env", "")
        if not env_content:
            self.send_response(400)
            self.end_headers()
            return

        ENV_FILE.write_text(env_content, encoding="utf-8")

        self.send_response(200)
        self.send_header("Content-Type",                         "text/plain")
        self.send_header("Access-Control-Allow-Origin",          ALLOWED_ORIGIN)
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.end_headers()
        self.wfile.write(b"ok")

        received.set()

    def log_message(self, *args):
        pass  # silenciar logs del servidor HTTP


def main():
    server = HTTPServer(("localhost", PORT), TokenReceiver)
    # handle_request() bloquea en select() con este timeout — sin fijarlo
    # (queda en None) espera una conexión indefinidamente. server.shutdown()
    # NO interrumpe esa espera salvo que serve_forever() esté corriendo en
    # otro hilo (lo cual no es nuestro caso), así que el límite de tiempo se
    # aplica aquí, comprobando el deadline en cada vuelta del bucle.
    server.timeout = 1.0

    webbrowser.open(AUTH_URL)
    print("Waiting for browser authorization...", flush=True)

    deadline = time.monotonic() + TIMEOUT_SEC
    while not received.is_set() and time.monotonic() < deadline:
        server.handle_request()

    if received.is_set() and ENV_FILE.exists():
        print("Configuration received.", flush=True)
        sys.exit(0)
    else:
        print("Error: configuration was not received (timed out).", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

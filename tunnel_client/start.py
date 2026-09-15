"""
Arranca el túnel Pangolin (newt) en background al iniciar el agente.
Completamente transparente para el usuario — no ve ventanas ni mensajes de túnel.

Tras arrancar newt, comprueba con un self-ping que el túnel responde de verdad
de punta a punta (no basta con que el proceso esté vivo y el log limpio — un
bug histórico de Pangolin dejaba el túnel devolviendo 503 con el log de newt
perfectamente limpio). Si no responde tras varios reintentos, pide al servidor
que repare el túnel (POST /agent/heal) y relanza newt con las credenciales
nuevas. Un solo intento de heal por arranque — si también falla, el agente
sigue vivo pero deja el túnel roto hasta el siguiente arranque.

Requisitos:
  - newt.exe en la carpeta raíz de agent-local (junto a start.py)
  - Variables en .env: PANGOLIN_SERVER, PANGOLIN_ID, PANGOLIN_SECRET, AGENT_BEARER_TOKEN,
    AGENT_PUBLIC_URL, GITBI_SERVER_URL

Descargar newt.exe desde:
  https://github.com/fosrl/newt/releases  → Windows x64
"""
import os
import sys
import time
import logging
import subprocess
from pathlib import Path

import httpx
import tempfile
import shutil
from datetime import datetime
from dotenv import load_dotenv
from typing import Optional

load_dotenv()
logger = logging.getLogger(__name__)

# Raíz del proyecto: la carpeta que contiene start.py y app/.
# Empaquetado con PyInstaller, __file__ apunta dentro del bundle (_internal/),
# no a la carpeta de instalación donde están newt.exe y los logs — en ese caso
# la raíz real es la carpeta que contiene el .exe.
if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys.executable).parent
else:
    PROJECT_ROOT = Path(__file__).parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

SELF_PING_RETRIES = 7
# Un subdominio nuevo (primera instalación, o recién recreado por un heal)
# puede devolver 502 mientras Traefik emite su certificado Let's Encrypt por
# primera vez — eso no es un túnel roto, solo necesita más margen. Backoff
# generoso (~95s totales) para no confundir esa espera con un fallo real.
SELF_PING_BACKOFF = [2, 4, 8, 15, 15, 25, 25]  # segundos entre reintentos


def _find_newt() -> str:
    candidates = [
        PROJECT_ROOT / "newt.exe",                   # junto a start.py  ← ubicación esperada
        Path(sys.executable).parent / "newt.exe",    # junto al intérprete Python
        Path("newt.exe"),                             # directorio de trabajo
    ]
    for path in candidates:
        if path.exists():
            return str(path)

    raise FileNotFoundError(
        "\n"
        "  newt.exe not found.\n"
        "  Download it from: https://github.com/fosrl/newt/releases\n"
        f"  and place it at: {PROJECT_ROOT / 'newt.exe'}\n"
    )


def _launch_newt(newt_id: str, newt_secret: str, server: str) -> subprocess.Popen:
    """Lanza newt.exe en background con las credenciales dadas."""
    preview = newt_id[:8] + "..." if len(newt_id) > 8 else newt_id
    logger.info(f"Conectando túnel → {server} (id: {preview})")

    newt_path = _find_newt()

    # CREATE_NO_WINDOW evita que aparezca una ventana CMD en Windows
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

    log_path = PROJECT_ROOT / "newt_debug.log"
    log_file = open(log_path, "w", encoding="utf-8")

    process = subprocess.Popen(
        [newt_path, "--id", newt_id, "--secret", newt_secret, "--endpoint", server],
        stdout=log_file,
        stderr=log_file,
        creationflags=flags,
    )

    time.sleep(3)
    log_file.flush()

    if process.poll() is not None:
        log_file.close()
        raise RuntimeError(
            f"The tunnel could not connect. Check {log_path} for details.\n"
        )

    # Cerrar el handle explícitamente: si más tarde se llama otra vez a
    # _launch_newt en el mismo proceso (tras un heal), reabrir este mismo log
    # con un handle anterior aún abierto puede fallar en Windows (archivo
    # bloqueado) y tirar el agente entero.
    log_file.close()

    try:
        output = log_path.read_text(encoding="utf-8", errors="replace")
        if "ERROR" in output:
            logger.warning(f"newt reportó errores:\n{output[:600]}")
        else:
            logger.info("newt arrancado, comprobando conectividad end-to-end...")
    except Exception:
        pass

    return process


def _self_ping(public_url: str) -> bool:
    """
    Comprueba que el túnel responde de punta a punta vía su URL pública.
    Reintenta con backoff creciente para no confundir "túnel roto" con "red
    lenta tras reiniciar el PC". True en el primer 200 OK, False si se agotan
    los intentos.
    """
    if not public_url:
        logger.warning("AGENT_PUBLIC_URL no configurada — no se puede self-ping")
        return False

    url = f"{public_url}/health"
    for attempt, wait in enumerate(SELF_PING_BACKOFF, start=1):
        try:
            response = httpx.get(url, timeout=5.0)
            if response.status_code == 200:
                logger.info("Túnel verificado, todo OK")
                return True
        except httpx.RequestError:
            pass
        logger.info(f"Self-ping {attempt}/{SELF_PING_RETRIES} sin respuesta, reintentando en {wait}s...")
        time.sleep(wait)

    logger.warning("El túnel no respondió tras varios intentos")
    return False


def _call_heal(server_url: str, bearer_token: str) -> dict | None:
    """Pide al servidor que reemplace el túnel roto. None si la reparación falla."""
    if not server_url or not bearer_token:
        logger.warning("GITBI_SERVER_URL o AGENT_BEARER_TOKEN no configurados — no se puede reparar")
        return None

    try:
        response = httpx.post(
            f"{server_url}/agent/heal",
            headers={"Authorization": f"Bearer {bearer_token}"},
            timeout=30.0,
        )
    except httpx.RequestError as e:
        logger.error(f"No se pudo contactar al servidor para reparar el túnel: {e}")
        return None

    if response.status_code != 200:
        logger.error(f"El servidor no pudo reparar el túnel ({response.status_code}): {response.text}")
        return None

    try:
        return response.json()
    except ValueError:
        logger.error(f"Respuesta de /agent/heal no es JSON válido: {response.text[:300]!r}")
        return None


def _rewrite_env(new_config: dict) -> None:
    """Reescribe el .env completo con las credenciales nuevas y refresca el proceso actual.

    Hace un backup de seguridad, escribe de forma atómica y recarga variables.
    """
    # Validar que new_config contiene al menos las claves mínimas
    required = ("PANGOLIN_ID", "PANGOLIN_SECRET")
    if not all(k in new_config and new_config[k] for k in required):
        # Guardar en un fichero alternativo para revisión manual
        alt = ENV_FILE.with_suffix(".new")
        content = "\n".join(f"{k}={v}" for k, v in new_config.items())
        alt.write_text(content, encoding="utf-8")
        logger.warning("new_config incompleto: escrito en %s en lugar de sobrescribir .env", alt)
        return

    # Crear backup
    try:
        if ENV_FILE.exists():
            bak = ENV_FILE.with_suffix(f".bak.{datetime.utcnow().strftime('%Y%m%d%H%M%S')}")
            shutil.copy2(ENV_FILE, bak)
            logger.info("Backup de .env creado en %s", bak)
    except Exception:
        logger.exception("No se pudo crear backup de .env")

    # Escritura atómica: escribir a temp y renombrar
    content = "\n".join(f"{k}={v}" for k, v in new_config.items())
    try:
        with tempfile.NamedTemporaryFile(mode="w", delete=False, dir=ENV_FILE.parent, encoding="utf-8") as tf:
            tf.write(content)
            temp_name = tf.name
        # Reemplazar de forma atómica
        Path(temp_name).replace(ENV_FILE)
        load_dotenv(dotenv_path=ENV_FILE, override=True)
        logger.info("Credenciales nuevas escritas en .env (atómico)")
    except Exception:
        logger.exception("Fallo escribiendo .env de forma atómica")


def start_tunnel() -> Optional[subprocess.Popen]:
    """
    Arranca newt en background. Solo lanza el proceso — NO verifica
    conectividad aquí. La verificación (verify_and_heal) corre por separado,
    en un hilo aparte, para no bloquear el arranque del propio servidor: si el
    self-ping bloqueara el event loop mientras espera respuesta, el agente
    nunca podría contestarse a sí mismo a través del túnel, y la verificación
    fallaría siempre sin importar el margen de espera (deadlock con uno mismo).
    Devuelve el proceso — el caller llama a process.terminate() al cerrar la app.
    """
    newt_id     = os.getenv("PANGOLIN_ID", "").strip()
    newt_secret = os.getenv("PANGOLIN_SECRET", "").strip()
    server      = os.getenv("PANGOLIN_SERVER", "https://pangolin.gitbi.app").strip()

    if not newt_id or not newt_secret:
        logger.warning("PANGOLIN_ID y/o PANGOLIN_SECRET no definidos en .env: el túnel no se iniciará automáticamente")
        return None

    return _launch_newt(newt_id, newt_secret, server)


def verify_and_heal(process_holder: dict) -> None:
    """
    Comprueba que el túnel responde de punta a punta y, si no, lo repara.
    Pensada para ejecutarse en un hilo aparte (ver app/main.py,
    asyncio.to_thread) DESPUÉS de que el servidor ya esté aceptando
    peticiones — así el self-ping puede recibir respuesta de verdad.

    process_holder es un dict mutable con la clave "process": si se repara el
    túnel, aquí se sustituye por el proceso nuevo, para que el caller pueda
    terminar el que esté vigente al apagar el agente aunque haya cambiado.
    """
    server = os.getenv("PANGOLIN_SERVER", "https://pangolin.gitbi.app").strip()
    public_url = os.getenv("AGENT_PUBLIC_URL", "").strip()

    if not public_url:
        # .env anterior a AGENT_PUBLIC_URL (instalado antes de este cambio):
        # no podemos verificar el túnel, pero "no se puede comprobar" no es lo
        # mismo que "está roto" — no disparar una reparación a ciegas en cada
        # arranque. Se autocorrige solo: en cuanto haya un heal o una
        # reinstalación, el .env nuevo ya incluye AGENT_PUBLIC_URL.
        logger.warning("AGENT_PUBLIC_URL no está en el .env (instalación previa a esta función) — self-ping omitido")
        print(" Agent is active (the connection could not be verified).", flush=True)
        return

    if _self_ping(public_url):
        print(" Connection verified ✓", flush=True)
        return

    logger.warning("Túnel no responde tras los reintentos, solicitando reparación al servidor...")
    print(" Repairing connection...", flush=True)

    # Permitir desactivar la reparación automática desde .env
    if os.getenv("DISABLE_AUTO_HEAL", "").lower() in ("1", "true", "yes", "on"):
        logger.info("Reparación automática deshabilitada por DISABLE_AUTO_HEAL")
        print(" Automatic heal disabled by configuration.", flush=True)
        return

    server_url   = os.getenv("GITBI_SERVER_URL", "https://gitbi.app").strip()
    bearer_token = os.getenv("AGENT_BEARER_TOKEN", "").strip()
    new_config   = _call_heal(server_url, bearer_token)

    if not new_config:
        logger.error(
            "No se pudo reparar el túnel. El agente seguirá ejecutándose pero la "
            "conexión puede no funcionar. Reinicia el agente para reintentar."
        )
        print(" The connection could not be verified (check agent.log). The agent is still active.", flush=True)
        return

    # Terminar proceso anterior solo si existe
    if process_holder.get("process"):
        try:
            process_holder["process"].terminate()
        except Exception:
            logger.exception("Error terminando proceso anterior del túnel")

    # Validar y aplicar la nueva configuración de forma segura
    _rewrite_env(new_config)

    # Si new_config contiene las claves necesarias, relanzar newt
    if new_config.get("PANGOLIN_ID") and new_config.get("PANGOLIN_SECRET"):
        process_holder["process"] = _launch_newt(
            new_config["PANGOLIN_ID"], new_config["PANGOLIN_SECRET"], server
        )
    else:
        logger.warning("new_config no contenía credenciales completas: no se relanzará el túnel automáticamente")
    # Un único self-ping adicional solo para loguear el resultado — no se
    # vuelve a llamar a heal aunque siga fallando (un solo intento por arranque).
    if _self_ping(new_config.get("AGENT_PUBLIC_URL", "")):
        logger.info("Túnel reparado correctamente")
        print(" Connection repaired ✓", flush=True)
    else:
        logger.warning("El túnel sigue sin responder tras la reparación")
        print(" The connection is still unresponsive (check agent.log). The agent is still active.", flush=True)

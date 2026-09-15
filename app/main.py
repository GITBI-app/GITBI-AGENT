import os
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv

from app.services.files import obtener_archivos_proyecto
from app.routers.git_router import router as router_git
from app.version import AGENT_NAME, AGENT_VERSION
from app.routers.page_router import router as router_page
from app.routers.model_router import router as router_model
from app.routers.query_dax_router import router as router_query_dax
from app.routers.explorador_router import router as router_explorador
from tunnel_client.start import start_tunnel, verify_and_heal

load_dotenv()
logger = logging.getLogger(__name__)

_security = HTTPBearer()
BEARER_TOKEN = os.getenv("AGENT_BEARER_TOKEN", "").strip()


def verify_reflex_token(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
):
    """Verifica que la petición viene del servidor Reflex."""
    if not BEARER_TOKEN:
        logger.error("AGENT_BEARER_TOKEN no configurado en .env")
        raise HTTPException(status_code=500, detail="Agente mal configurado")
    if credentials.credentials != BEARER_TOKEN:
        logger.warning("Token inválido recibido — petición rechazada")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autorizado")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting GITBI Agent...")
    print(" Connecting to GITBI...", flush=True)
    try:
        process = start_tunnel()
    except Exception as e:
        logger.exception("Error arrancando el túnel: %s", e)
        process = None
    process_holder = {"process": process}
    port = os.getenv("AGENT_PORT", "8000")
    logger.info(f"Agent ready on port {port}")
    print(f" Agent ready (port {port}). Verifying connection...", flush=True)

    # verify_and_heal hace su propio self-ping HTTP contra este mismo agente,
    # a través del túnel — si corriera en este punto (bloqueando el arranque),
    # el agente nunca podría contestarse a sí mismo y el self-ping fallaría
    # siempre. Se lanza en un hilo aparte para no bloquear el event loop, y NO
    # se espera (await) aquí: el servidor debe terminar de arrancar y quedar
    # listo para responder ANTES de que la verificación le llegue.
    verify_task = asyncio.create_task(asyncio.to_thread(verify_and_heal, process_holder))

    yield
    logger.info("Shutting down agent...")
    verify_task.cancel()
    if process_holder.get("process"):
        try:
            process_holder["process"].terminate()
        except Exception:
            logger.exception("Error terminando el proceso del túnel")


app = FastAPI(title="GITBI Agent", lifespan=lifespan)

# CORS: las llamadas de Reflex llegan a través del túnel (newt → localhost),
# por lo que siguen apareciendo como localhost. Se mantiene la restricción original.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_auth = [Depends(verify_reflex_token)]

app.include_router(router_git,        prefix="/git",        dependencies=_auth)
app.include_router(router_page,       prefix="/page",       dependencies=_auth)
app.include_router(router_model,      prefix="/model",      dependencies=_auth)
app.include_router(router_query_dax,  prefix="/query",      dependencies=_auth)
app.include_router(router_explorador, prefix="/explorador", dependencies=_auth)


@app.get("/health")
async def health():
    """Reflex llama a este endpoint para verificar que el agente está activo."""
    return {
        "status": "ok",
        "agent": AGENT_NAME,
        "version": AGENT_VERSION,
    }


@app.get("/ping")
def ping():
    """Kept for backward compatibility con herramientas locales."""
    return {"ok": True}


@app.get("/project-files/{ruta:path}", dependencies=_auth)
def get_project_files(ruta: str):
    try:
        archivos = obtener_archivos_proyecto(ruta)
        return {"ok": True, "data": archivos}
    except FileNotFoundError as e:
        return {"ok": False, "error": str(e)}
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": f"Error inesperado: {e}"}

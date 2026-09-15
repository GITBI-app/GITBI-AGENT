
from pathlib import Path
from app.services.files import cargar_json, carga_tdml, carga_tmdl_relationships, cargar_texto_archivo
from app.services.git_services import git_diff_archivo, git_status_directorio
from typing import Optional


def _listar_estructura(ruta: Path) -> dict:
    """Construye recursivamente un diccionario con la estructura de archivos y carpetas."""
    estructura = {}
    for item in sorted(ruta.iterdir()):
        if item.name.startswith("."):
            continue
        if item.is_dir():
            estructura[item.name] = {
                "tipo": "directorio",
                "contenido": _listar_estructura(item)
            }
        else:
            estructura[item.name] = {
                "tipo": "archivo",
                "extension": item.suffix
            }
    return estructura


def explorar_directorio(ruta_repo: str, subdirectorio: Optional[str] = None, commit1: Optional[str] = None, commit2: Optional[str] = None):
    """
    Lista la estructura de archivos de una carpeta como diccionario.
    Incluye git_diff del subdirectorio (o raíz si no se especifica).
    """
    ruta_base = Path(ruta_repo)
    ruta_dir = ruta_base / subdirectorio if subdirectorio else ruta_base

    if not ruta_dir.exists():
        raise FileNotFoundError(f"❌ No se encontró el directorio: {ruta_dir}")
    if not ruta_dir.is_dir():
        raise ValueError(f"⚠️ La ruta no es un directorio: {ruta_dir}")

    estructura = _listar_estructura(ruta_dir)

    resultado = {
        "ruta": str(ruta_dir),
        "estructura": estructura,
        "git_diff": git_status_directorio(str(ruta_base), subdirectorio, commit1, commit2)
    }
    return resultado


def leer_archivo_explorador(ruta_repo: str, ruta_archivo: str, commit1: Optional[str] = None, commit2: Optional[str] = None):
    """
    Lee un archivo usando la función apropiada según su extensión.
    Incluye git_diff del archivo.
    """
    ruta_base = Path(ruta_repo)
    ruta_completa = ruta_base / ruta_archivo

    if not ruta_completa.exists():
        raise FileNotFoundError(f"❌ No se encontró el archivo: {ruta_completa}")
    if not ruta_completa.is_file():
        raise ValueError(f"⚠️ La ruta no es un archivo: {ruta_completa}")

    extension = ruta_completa.suffix.lower()

    if extension == ".json":
        contenido = cargar_json(str(ruta_completa))
    elif extension == ".tmdl":
        if ruta_completa.name == "relationships.tmdl":
            contenido = carga_tmdl_relationships(str(ruta_completa))
        else:
            contenido = carga_tdml(str(ruta_completa))
    else:
        contenido = cargar_texto_archivo(str(ruta_completa))

    ruta_relativa = ruta_archivo.replace("\\", "/")
    resultado = {
        "archivo": ruta_archivo,
        "extension": extension,
        "contenido": contenido,
        "git_diff": git_diff_archivo(str(ruta_repo), ruta_relativa, commit1, commit2)
    }
    return resultado

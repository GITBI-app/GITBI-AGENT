from fastapi import APIRouter
from app.services.info_explorador import explorar_directorio, leer_archivo_explorador
from typing import Optional

router = APIRouter()


@router.get("/read_directory")
def get_read_directory(ruta: str, subdirectorio: Optional[str] = None, commit1: Optional[str] = None, commit2: Optional[str] = None):
    info = explorar_directorio(ruta, subdirectorio, commit1, commit2)
    return info


@router.get("/read_file")
def get_read_file(ruta: str, ruta_archivo: str, commit1: Optional[str] = None, commit2: Optional[str] = None):
    info = leer_archivo_explorador(ruta, ruta_archivo, commit1, commit2)
    return info

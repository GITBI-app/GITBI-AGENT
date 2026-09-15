from typing import Optional

from fastapi import APIRouter
from app.services.info_model import info_model


router = APIRouter()

# Verifica si Git está instalado en el sistema
@router.get("/info_model") #, response_model=GitInstallationResponse)
def get_info_model(ruta: str, commit1: Optional[str] = None, commit2: Optional[str] = None):
    info = info_model(ruta, commit1, commit2)
    return info
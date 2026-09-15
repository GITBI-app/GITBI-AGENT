from fastapi import APIRouter
from app.services.info_page import info_page
from typing import Optional

router = APIRouter()

# Verifica si Git está instalado en el sistema
@router.get("/info_page") #, response_model=GitInstallationResponse)
def get_info_page(ruta: str, page_id: str, commit1: Optional[str] = None, commit2: Optional[str] = None):
    info = info_page(ruta, page_id, commit1, commit2)
    return info
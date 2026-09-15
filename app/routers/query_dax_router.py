from fastapi import APIRouter
from app.services.info_query_DAX import info_query_dax
from app.services.info_query_TDML import info_query_tdml
from typing import Optional

router = APIRouter()

@router.get("/info_dax_query") 
def get_info_dax_query(ruta: str, commit1: Optional[str] = None, commit2: Optional[str] = None):
    info = info_query_dax(ruta, commit1, commit2)
    return info

@router.get("/info_tdml_query") 
def get_info_tdml_query(ruta: str, commit1: Optional[str] = None, commit2: Optional[str] = None):
    info = info_query_tdml(ruta, commit1, commit2)
    return info
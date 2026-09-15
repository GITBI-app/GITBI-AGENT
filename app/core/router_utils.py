"""
Utilidades comunes para routers FastAPI.
Incluye decoradores y funciones auxiliares para manejo de errores.
"""
from functools import wraps
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)


def handle_git_exceptions(func):
    """
    Decorador que maneja excepciones comunes en operaciones Git.
    Convierte ValueError en HTTPException 400 y otras excepciones en HTTPException 500.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValueError as e:
            logger.warning(f"Validation error in {func.__name__}: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}")
            raise HTTPException(status_code=500, detail=f"Error inesperado: {e}")
    return wrapper


def format_git_response(response_dict: dict) -> dict:
    """
    Formatea la respuesta de servicios Git para la API.
    Mantiene compatibilidad con clientes existentes.
    """
    # Si la respuesta tiene 'success', la envolvemos en 'data' para mantener compatibilidad
    if 'success' in response_dict:
        return {"ok": response_dict.get("ok", True), "data": response_dict}
    
    # Si no tiene 'success', devolvemos tal como está
    return response_dict
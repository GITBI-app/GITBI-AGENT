"""
Utilidades comunes para operaciones Git.
Contiene funciones auxiliares reutilizables.
"""
import subprocess
import os
from pathlib import Path
from git import Repo
from git.exc import InvalidGitRepositoryError, NoSuchPathError
from typing import Dict, Optional, Tuple


class GitUtils:
    """Clase utilitaria para operaciones Git comunes."""
    
    @staticmethod
    def get_safe_env() -> Dict[str, str]:
        """
        Retorna variables de entorno con configuración safe.directory.
        Evita errores de ownership en Windows con usuarios de dominio/AzureAD.
        """
        env = os.environ.copy()
        env.update({
            'GIT_CONFIG_COUNT': '1',
            'GIT_CONFIG_KEY_0': 'safe.directory',
            'GIT_CONFIG_VALUE_0': '*'
        })
        return env
    
    @staticmethod
    def get_absolute_path(ruta_repo: str = ".") -> str:
        """Retorna la ruta absoluta del repositorio."""
        return str(Path(ruta_repo).resolve())
    
    @staticmethod
    def validate_git_repository(ruta_repo: str = ".") -> Tuple[bool, Optional[str]]:
        """
        Valida si una ruta es un repositorio Git válido.
        
        Returns:
            Tuple[bool, Optional[str]]: (es_valido, mensaje_error)
        """
        try:
            ruta_absoluta = GitUtils.get_absolute_path(ruta_repo)
            env = GitUtils.get_safe_env()
            
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=ruta_absoluta,
                capture_output=True,
                text=True,
                timeout=5,
                env=env
            )
            
            if result.returncode != 0:
                return False, "La ruta no es un repositorio Git válido"
            
            return True, None
            
        except Exception as e:
            return False, f"Error al validar repositorio: {str(e)}"
    
    @staticmethod
    def get_repo_instance(ruta_repo: str = ".") -> Tuple[Optional[Repo], Optional[str]]:
        """
        Obtiene una instancia de Repo de GitPython.
        
        Returns:
            Tuple[Optional[Repo], Optional[str]]: (repo_instance, mensaje_error)
        """
        try:
            repo = Repo(ruta_repo, search_parent_directories=True)
            return repo, None
        except (InvalidGitRepositoryError, NoSuchPathError):
            return None, f"No es un repositorio Git válido: {ruta_repo}"
        except Exception as e:
            return None, f"Error al acceder al repositorio: {str(e)}"
    
    @staticmethod
    def run_git_command(
        command: list, 
        cwd: str, 
        timeout: int = 10,
        check: bool = False
    ) -> subprocess.CompletedProcess:
        """
        Ejecuta un comando git con configuración segura.
        
        Args:
            command: Lista con el comando git y argumentos
            cwd: Directorio de trabajo
            timeout: Timeout en segundos
            check: Si lanzar excepción en caso de error
            
        Returns:
            subprocess.CompletedProcess: Resultado de la ejecución
        """
        env = GitUtils.get_safe_env()
        return subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            check=check
        )
    
    @staticmethod
    def configure_safe_directory_globally(ruta_repo: str = ".") -> Tuple[bool, str]:
        """
        Configura safe.directory globalmente para el repositorio.
        
        Returns:
            Tuple[bool, str]: (exito, mensaje)
        """
        try:
            ruta_absoluta = GitUtils.get_absolute_path(ruta_repo)
            result = subprocess.run(
                ["git", "config", "--global", "--add", "safe.directory", ruta_absoluta],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                return True, f"Directorio {ruta_absoluta} añadido a safe.directory"
            else:
                return False, f"Error al configurar safe.directory: {result.stderr}"
                
        except Exception as e:
            return False, f"Error al configurar safe.directory: {str(e)}"
    
    @staticmethod
    def clean_branch_name(branch_name: str) -> Tuple[str, Optional[str]]:
        """
        Limpia y valida el nombre de rama según las reglas de Git.
        
        Args:
            branch_name: Nombre de rama a limpiar
            
        Returns:
            Tuple[str, Optional[str]]: (nombre_limpio, mensaje_error)
        """
        import re
        
        if not branch_name.strip():
            return "", "El nombre de la rama no puede estar vacío"
        
        # Reemplazar espacios por guiones
        cleaned_name = branch_name.strip().replace(" ", "-")
        
        # Reemplazar caracteres no permitidos por Git
        cleaned_name = re.sub(r'[~^:?*\[\]\\@{}]+', '-', cleaned_name)
        
        # Eliminar puntos al principio o final
        cleaned_name = cleaned_name.strip('.')
        
        # Reemplazar múltiples guiones consecutivos por uno solo
        cleaned_name = re.sub(r'-+', '-', cleaned_name)
        
        # Eliminar guiones al principio o final
        cleaned_name = cleaned_name.strip('-')
        
        if not cleaned_name:
            return "", "El nombre de la rama no es válido después de limpiar caracteres no permitidos"
        
        return cleaned_name, None


class GitErrors:
    """Manejo centralizado de errores Git."""
    
    @staticmethod
    def handle_ownership_error(error_msg: str) -> bool:
        """
        Detecta si un error es de ownership y lo maneja.
        
        Returns:
            bool: True si es error de ownership, False en caso contrario
        """
        error_lower = error_msg.lower()
        return 'dubious ownership' in error_lower or 'safe.directory' in error_lower
    
    @staticmethod
    def create_error_response(error_msg: str, **kwargs) -> Dict:
        """
        Crea respuesta de error estándar.
        
        Args:
            error_msg: Mensaje de error
            **kwargs: Campos adicionales para la respuesta
            
        Returns:
            Dict: Respuesta de error estándar
        """
        base_response = {
            "ok": False,
            "error": error_msg
        }
        base_response.update(kwargs)
        return base_response
    
    @staticmethod
    def create_success_response(**kwargs) -> Dict:
        """
        Crea respuesta de éxito estándar.
        
        Args:
            **kwargs: Campos para la respuesta
            
        Returns:
            Dict: Respuesta de éxito estándar
        """
        base_response = {"ok": True, "error": None}
        base_response.update(kwargs)
        return base_response
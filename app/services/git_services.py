"""
Servicios para operaciones Git.
Refactorizado para mayor mantenibilidad y reutilización de código.
"""
from git import Repo
from git.exc import InvalidGitRepositoryError, NoSuchPathError
import subprocess
import base64
import re
from functools import wraps
from typing import Dict, List, Optional, Any
import logging
from pathlib import Path

from app.core.git_utils import GitUtils, GitErrors
from app.models.git_models import (
    GitInstallationResponse,
    RepositoryStatusResponse,
    BranchesResponse,
    CommitListResponse,
    CommitOperationResponse,
    CheckoutResponse,
    BranchCreateResponse,
    InitRepositoryResponse,
    ResetResponse,
    GitDiffResponse,
    MergeResponse,
    MergeConflictsStatusResponse,
    ResolveConflictResponse,
    AbortMergeResponse,
    MergeStatusResponse,
    RemoteInfo,
    RemoteListResponse,
    RemoteOperationResponse,
    CloneResponse,
    PushResponse,
    PullResponse,
    FetchResponse,
    RemoteBranchesResponse,
    BranchDeleteResponse,
    TagInfo,
    TagListResponse,
    TagOperationResponse,
    StashInfo,
    StashListResponse,
    StashOperationResponse
)

# Configurar logging
logger = logging.getLogger(__name__)

# Última actividad de merge por ruta absoluta de repositorio
_LAST_MERGE_ACTIVITY: Dict[str, Dict[str, Optional[str]]] = {}


def _handle_ownership_error(func):
    """
    Decorador que detecta errores de ownership y configura safe.directory automáticamente.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_msg = str(e).lower()
            # Detectar error de dubious ownership
            if GitErrors.handle_ownership_error(error_msg):
                try:
                    # Configurar safe.directory para todos los directorios
                    subprocess.run(
                        ["git", "config", "--global", "safe.directory", "*"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                        check=True
                    )
                    # Reintentar la función
                    return func(*args, **kwargs)
                except Exception:
                    # Si falla la configuración, lanzar el error original
                    raise e
            else:
                # Si no es error de ownership, lanzar el error original
                raise e
    return wrapper


def verificar_git_instalado() -> Dict[str, Any]:
    """
    Verifica si Git está instalado en el sistema.
    Devuelve un diccionario con el estado y la versión instalada.
    """
    try:
        resultado = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if resultado.returncode == 0:
            version = resultado.stdout.strip()
            return GitInstallationResponse(
                ok=True, 
                installed=True, 
                version=version
            ).dict()
        else:
            return GitInstallationResponse(
                ok=False, 
                installed=False, 
                error="Git no responde correctamente"
            ).dict()
    except FileNotFoundError:
        return GitInstallationResponse(
            ok=False, 
            installed=False, 
            error="Git no está instalado en el sistema"
        ).dict()
    except Exception as e:
        logger.error(f"Error al verificar Git: {e}")
        return GitInstallationResponse(
            ok=False, 
            installed=False, 
            error=f"Error al verificar Git: {e}"
        ).dict()


def verificar_repo_inicializado(ruta_repo: str = ".") -> Dict[str, Any]:
    """
    Verifica si una ruta es un repositorio Git válido e inicializado.
    Devuelve un diccionario con el estado y detalles del repositorio.
    Un repositorio bare es un repositorio Git sin directorio de trabajo.
    """
    try:
        ruta_absoluta = GitUtils.get_absolute_path(ruta_repo)
        env = GitUtils.get_safe_env()
        
        # Verificar si es un repo git
        check_repo = GitUtils.run_git_command(
            ["git", "rev-parse", "--git-dir"],
            cwd=ruta_absoluta,
            timeout=5
        )
        
        if check_repo.returncode != 0:
            return RepositoryStatusResponse(
                ok=False, 
                initialized=False, 
                error="La ruta no es un repositorio Git válido"
            ).dict()
        
        # Obtener información del repo usando comandos git
        branch_result = GitUtils.run_git_command(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=ruta_absoluta
        )
        branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None
        
        hash_result = GitUtils.run_git_command(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ruta_absoluta
        )
        short_hash = hash_result.stdout.strip() if hash_result.returncode == 0 else None
        
        message_result = GitUtils.run_git_command(
            ["git", "log", "-1", "--pretty=%B"],
            cwd=ruta_absoluta
        )
        commit_message = message_result.stdout.strip() if message_result.returncode == 0 else None
        
        date_result = GitUtils.run_git_command(
            ["git", "log", "-1", "--pretty=%cI"],
            cwd=ruta_absoluta
        )
        commit_date = date_result.stdout.strip() if date_result.returncode == 0 else None
        
        status_result = GitUtils.run_git_command(
            ["git", "status", "--porcelain"],
            cwd=ruta_absoluta
        )
        dirty = len(status_result.stdout.strip()) > 0 if status_result.returncode == 0 else False
        
        return RepositoryStatusResponse(
            ok=True,
            initialized=True,
            path=ruta_absoluta,
            bare=False,
            branch=branch,
            detached=branch == "HEAD",
            short_hash=short_hash,
            commit_date=commit_date,
            commit_message=commit_message,
            dirty=dirty
        ).dict()
        
    except (InvalidGitRepositoryError, NoSuchPathError):
        return RepositoryStatusResponse(
            ok=False, 
            initialized=False, 
            error="La ruta no es un repositorio Git válido"
        ).dict()
    except Exception as e:
        logger.error(f"Error al verificar repositorio: {e}")
        return RepositoryStatusResponse(
            ok=False, 
            initialized=False, 
            error=f"Error al verificar repositorio: {e}"
        ).dict()
def listar_ramas(ruta_repo: str = ".") -> Dict[str, Any]:
    """
    Devuelve la lista de ramas del repositorio y la rama actual.
    """
    ruta_absoluta = GitUtils.get_absolute_path(ruta_repo)
    
    # Validar repositorio
    is_valid, error_msg = GitUtils.validate_git_repository(ruta_absoluta)
    if not is_valid:
        return BranchesResponse(
            ok=False, 
            branches=[], 
            current=None, 
            error=error_msg
        ).dict()

    try:
        current_res = GitUtils.run_git_command(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=ruta_absoluta
        )
        current = current_res.stdout.strip() if current_res.returncode == 0 else None

        branches_res = GitUtils.run_git_command(
            ["git", "branch", "--format", "%(refname:short)"],
            cwd=ruta_absoluta
        )
        branches = []
        if branches_res.returncode == 0:
            branches = [b.lstrip("* ").strip() for b in branches_res.stdout.splitlines() if b.strip()]

        return BranchesResponse(
            ok=True, 
            branches=branches, 
            current=current
        ).dict()
        
    except Exception as e:
        logger.error(f"Error al listar ramas: {e}")
        return BranchesResponse(
            ok=False, 
            branches=[], 
            current=None, 
            error=f"Error al listar ramas: {e}"
        ).dict()


@_handle_ownership_error
def hacer_commit(ruta_repo: str = ".", mensaje: str = "") -> Dict[str, Any]:
    """
    Realiza un commit en el repositorio Git especificado incluyendo todos los archivos modificados.
    
    Args:
        ruta_repo (str): Ruta al repositorio Git. Por defecto es el directorio actual.
        mensaje (str): Mensaje del commit. Es obligatorio.
    
    Returns:
        Dict[str, Any]: Información del commit realizado
    
    Raises:
        ValueError: Si la ruta no es un repositorio git válido o si el mensaje está vacío.
    """
    if not mensaje.strip():
        raise ValueError("El mensaje del commit no puede estar vacío")
    
    repo, error_msg = GitUtils.get_repo_instance(ruta_repo)
    if not repo:
        raise ValueError(error_msg)
    
    try:
        # Agregar todos los archivos modificados y rastreados
        repo.git.add(A=True)  # Equivale a 'git add -A'
        
        # Verificar que hay cambios en staging para hacer commit
        if not repo.index.diff("HEAD"):
            # Si no hay diferencias con HEAD, verificar si es el primer commit
            try:
                repo.head.commit
                # Si llegamos aquí, HEAD existe, no hay cambios para commit
                return CommitOperationResponse(
                    ok=False,
                    success=False,
                    commit_hash=None,
                    short_hash=None,
                    message=mensaje,
                    author=None,
                    date=None,
                    files_committed=[],
                    error="No hay cambios para hacer commit"
                ).dict()
            except:
                # Es el primer commit del repositorio, continuar
                pass
        
        # Realizar el commit
        commit = repo.index.commit(mensaje)
        
        # Obtener los archivos que fueron incluidos en el commit
        files_committed = []
        if commit.parents:  # No es el primer commit
            # Comparar con el commit padre para obtener los archivos modificados
            parent = commit.parents[0]
            for diff_item in parent.diff(commit):
                if diff_item.a_path:
                    files_committed.append(diff_item.a_path)
                if diff_item.b_path and diff_item.b_path != diff_item.a_path:
                    files_committed.append(diff_item.b_path)
        else:
            # Es el primer commit, obtener todos los archivos del commit
            for item in commit.tree.traverse():
                if item.type == 'blob':  # Es un archivo
                    files_committed.append(item.path)
        
        return CommitOperationResponse(
            ok=True,
            success=True,
            commit_hash=commit.hexsha,
            short_hash=commit.hexsha[:7],
            message=commit.message.strip(),
            author=f"{commit.author.name} <{commit.author.email}>",
            date=commit.committed_datetime.isoformat(),
            files_committed=list(set(files_committed)),  # Eliminar duplicados
            error=None
        ).dict()
        
    except Exception as e:
        logger.error(f"Error al realizar commit: {e}")
        return CommitOperationResponse(
            ok=False,
            success=False,
            commit_hash=None,
            short_hash=None,
            message=mensaje,
            author=None,
            date=None,
            files_committed=[],
            error=f"Error al realizar commit: {str(e)}"
        ).dict()


@_handle_ownership_error
def hacer_checkout_commit(ruta_repo: str = ".", commit_hash: str = "", forzar: bool = False) -> Dict[str, Any]:
    """
    Realiza checkout a un commit específico en el repositorio Git.
    
    Args:
        ruta_repo (str): Ruta al repositorio Git. Por defecto es el directorio actual.
        commit_hash (str): Hash del commit al cual hacer checkout. Puede ser hash completo o corto.
        forzar (bool): Si es True, fuerza el checkout descartando cambios sin confirmar. Por defecto es False.
    
    Returns:
        Dict[str, Any]: Información del resultado del checkout
    
    Raises:
        ValueError: Si la ruta no es un repositorio git válido o si el commit_hash está vacío.
    """
    if not commit_hash.strip():
        raise ValueError("El hash del commit no puede estar vacío")
    
    repo, error_msg = GitUtils.get_repo_instance(ruta_repo)
    if not repo:
        raise ValueError(error_msg)
    
    # Guardar el estado actual antes del checkout
    if repo.head.is_detached:
        previous_state = {"branch": None, "commit": repo.head.commit.hexsha[:7]}
    else:
        try:
            previous_state = {"branch": repo.active_branch.name, "commit": repo.head.commit.hexsha[:7]}
        except Exception:
            previous_state = {"branch": None, "commit": repo.head.commit.hexsha[:7]}
    
    try:
        # Verificar que el working tree esté limpio antes del checkout (solo si no se fuerza)
        if not forzar and repo.is_dirty(untracked_files=True):
            return CheckoutResponse(
                ok=False,
                success=False,
                commit_hash=None,
                short_hash=None,
                message=None,
                author=None,
                date=None,
                detached_head=False,
                previous_state=previous_state,
                error="El working tree tiene cambios sin confirmar. Haz commit o stash antes del checkout, o usa forzar=True."
            ).dict()
        
        # Buscar el commit por hash (GitPython maneja tanto hash completo como corto)
        try:
            commit = repo.commit(commit_hash)
        except Exception:
            return CheckoutResponse(
                ok=False,
                success=False,
                commit_hash=None,
                short_hash=None,
                message=None,
                author=None,
                date=None,
                detached_head=False,
                previous_state=previous_state,
                error=f"No se encontró el commit con hash: {commit_hash}"
            ).dict()
        
        # Realizar el checkout al commit específico
        if forzar:
            # Checkout forzado que descarta cambios locales
            repo.git.checkout(commit.hexsha, force=True)
        else:
            # Checkout normal
            repo.git.checkout(commit.hexsha)
        
        # Verificar si quedamos en detached HEAD
        is_detached = repo.head.is_detached
        
        return CheckoutResponse(
            ok=True,
            success=True,
            commit_hash=commit.hexsha,
            short_hash=commit.hexsha[:7],
            message=commit.message.strip(),
            author=f"{commit.author.name} <{commit.author.email}>",
            date=commit.committed_datetime.isoformat(),
            detached_head=is_detached,
            previous_state=previous_state,
            error=None
        ).dict()
        
    except Exception as e:
        logger.error(f"Error al hacer checkout: {e}")
        return CheckoutResponse(
            ok=False,
            success=False,
            commit_hash=None,
            short_hash=None,
            message=None,
            author=None,
            date=None,
            detached_head=False,
            previous_state=previous_state,
            error=f"Error al hacer checkout: {str(e)}"
        ).dict()


@_handle_ownership_error
def hacer_checkout_rama(ruta_repo: str = ".", branch_name: str = "", forzar: bool = False) -> Dict[str, Any]:
    """
    Realiza checkout a una rama por nombre en el repositorio Git.

    Args:
        ruta_repo (str): Ruta al repositorio Git. Por defecto es el directorio actual.
        branch_name (str): Nombre de la rama a la que hacer checkout.
        forzar (bool): Si True, fuerza el checkout descartando cambios locales.

    Returns:
        Dict[str, Any]: Información del resultado del checkout.
    """
    if not branch_name.strip():
        raise ValueError("El nombre de la rama no puede estar vacío")

    repo, error_msg = GitUtils.get_repo_instance(ruta_repo)
    if not repo:
        raise ValueError(error_msg)

    # Guardar estado previo
    if repo.head.is_detached:
        previous_state = {"branch": None, "commit": repo.head.commit.hexsha[:7]}
    else:
        try:
            previous_state = {"branch": repo.active_branch.name, "commit": repo.head.commit.hexsha[:7]}
        except Exception:
            previous_state = {"branch": None, "commit": repo.head.commit.hexsha[:7]}

    try:
        # Verificar estado del working tree
        if not forzar and repo.is_dirty(untracked_files=True):
            return CheckoutResponse(
                ok=False,
                success=False,
                branch=None,
                commit_hash=None,
                short_hash=None,
                message=None,
                author=None,
                date=None,
                detached_head=repo.head.is_detached,
                previous_state=previous_state,
                error="El working tree tiene cambios sin confirmar. Haz commit o stash antes del checkout, o usa forzar=True."
            ).dict()

        # Verificar que la rama exista (local, remota exacta, o remota por nombre corto)
        branch_names = [b.name for b in repo.branches]
        is_local = branch_name in branch_names
        remote_ref = None
        is_remote_direct = False  # True si el usuario pasa "origin/master" directamente

        if not is_local:
            # Primero: buscar coincidencia exacta con ref remota (ej: "origin/master")
            for remote in repo.remotes:
                for ref in remote.refs:
                    if ref.name == branch_name:
                        remote_ref = ref
                        is_remote_direct = True
                        break
                if remote_ref is not None:
                    break

            # Segundo: buscar por nombre corto (ej: "feature-x" -> origin/feature-x)
            if remote_ref is None:
                for remote in repo.remotes:
                    for ref in remote.refs:
                        if ref.remote_head == branch_name:
                            remote_ref = ref
                            break
                    if remote_ref is not None:
                        break

            if remote_ref is None:
                return CheckoutResponse(
                    ok=False,
                    success=False,
                    branch=None,
                    commit_hash=None,
                    short_hash=None,
                    message=None,
                    author=None,
                    date=None,
                    detached_head=repo.head.is_detached,
                    previous_state=previous_state,
                    error=f"No se encontró la rama: {branch_name}"
                ).dict()

        # Realizar el checkout
        if is_local:
            if forzar:
                repo.git.checkout(branch_name, force=True)
            else:
                repo.git.checkout(branch_name)
        elif is_remote_direct:
            # Checkout directo a ref remota (detached HEAD para inspección)
            if forzar:
                repo.git.checkout(str(remote_ref), force=True)
            else:
                repo.git.checkout(str(remote_ref))
        else:
            # Crear rama local que trackea la remota
            if forzar:
                repo.git.checkout("-b", branch_name, "--track", str(remote_ref), force=True)
            else:
                repo.git.checkout("-b", branch_name, "--track", str(remote_ref))

        # Obtener commit
        commit = repo.head.commit

        return CheckoutResponse(
            ok=True,
            success=True,
            branch=branch_name,
            commit_hash=commit.hexsha,
            short_hash=commit.hexsha[:7],
            message=commit.message.strip(),
            author=f"{commit.author.name} <{commit.author.email}>",
            date=commit.committed_datetime.isoformat(),
            detached_head=repo.head.is_detached,
            previous_state=previous_state,
            error=None
        ).dict()

    except Exception as e:
        logger.error(f"Error al hacer checkout de rama: {e}")
        return CheckoutResponse(
            ok=False,
            success=False,
            branch=None,
            commit_hash=None,
            short_hash=None,
            message=None,
            author=None,
            date=None,
            detached_head=repo.head.is_detached,
            previous_state=previous_state,
            error=f"Error al hacer checkout de rama: {str(e)}"
        ).dict()


@_handle_ownership_error
def crear_rama(ruta_repo: str = ".", branch_name: str = "", desde_commit: str = "", checkout: bool = True) -> Dict[str, Any]:
    """
    Crea una nueva rama en el repositorio Git.

    Args:
        ruta_repo (str): Ruta al repositorio Git. Por defecto es el directorio actual.
        branch_name (str): Nombre de la nueva rama a crear. Los espacios se reemplazarán por guiones.
        desde_commit (str): Hash del commit desde el cual crear la rama. Si está vacío, usa HEAD.
        checkout (bool): Si True, hace checkout automático a la nueva rama. Por defecto True.

    Returns:
        Dict[str, Any]: Información del resultado

    Raises:
        ValueError: Si la ruta no es un repositorio git válido o si el nombre de rama está vacío.
    """
    if not branch_name.strip():
        raise ValueError("El nombre de la rama no puede estar vacío")

    # Limpiar y validar el nombre de la rama usando GitUtils
    cleaned_name, error_msg = GitUtils.clean_branch_name(branch_name)
    if error_msg:
        return BranchCreateResponse(
            ok=False,
            success=False,
            branch=None,
            commit_hash=None,
            short_hash=None,
            message=None,
            author=None,
            date=None,
            checked_out=False,
            error=error_msg
        ).dict()

    repo, error_msg = GitUtils.get_repo_instance(ruta_repo)
    if not repo:
        raise ValueError(error_msg)

    try:
        # Verificar que la rama no exista ya
        branch_names = [b.name for b in repo.branches]
        if cleaned_name in branch_names:
            return BranchCreateResponse(
                ok=False,
                success=False,
                branch=None,
                commit_hash=None,
                short_hash=None,
                message=None,
                author=None,
                date=None,
                checked_out=False,
                error=f"La rama '{cleaned_name}' ya existe"
            ).dict()

        # Determinar desde qué commit crear la rama
        if desde_commit.strip():
            try:
                commit = repo.commit(desde_commit)
            except Exception:
                return BranchCreateResponse(
                    ok=False,
                    success=False,
                    branch=None,
                    commit_hash=None,
                    short_hash=None,
                    message=None,
                    author=None,
                    date=None,
                    checked_out=False,
                    error=f"No se encontró el commit: {desde_commit}"
                ).dict()
        else:
            # Usar HEAD (commit actual)
            commit = repo.head.commit

        # Crear la nueva rama
        new_branch = repo.create_head(cleaned_name, commit)

        # Hacer checkout si se solicita
        checked_out = False
        if checkout:
            try:
                new_branch.checkout()
                checked_out = True
            except Exception as e:
                # La rama se creó pero no se pudo hacer checkout
                return BranchCreateResponse(
                    ok=True,
                    success=True,
                    branch=cleaned_name,
                    commit_hash=commit.hexsha,
                    short_hash=commit.hexsha[:7],
                    message=commit.message.strip(),
                    author=f"{commit.author.name} <{commit.author.email}>",
                    date=commit.committed_datetime.isoformat(),
                    checked_out=False,
                    error=f"Rama creada pero no se pudo hacer checkout: {str(e)}"
                ).dict()

        return BranchCreateResponse(
            ok=True,
            success=True,
            branch=cleaned_name,
            commit_hash=commit.hexsha,
            short_hash=commit.hexsha[:7],
            message=commit.message.strip(),
            author=f"{commit.author.name} <{commit.author.email}>",
            date=commit.committed_datetime.isoformat(),
            checked_out=checked_out,
            error=None
        ).dict()

    except Exception as e:
        logger.error(f"Error al crear rama: {e}")
        return BranchCreateResponse(
            ok=False,
            success=False,
            branch=None,
            commit_hash=None,
            short_hash=None,
            message=None,
            author=None,
            date=None,
            checked_out=False,
            error=f"Error al crear rama: {str(e)}"
        ).dict()



def inicializar_git(ruta_repo: str = ".", mensaje: str = "Initial commit") -> Dict[str, Any]:
    """
    Inicializa un repositorio git en la ruta dada y realiza el commit inicial.
    Configura safe.directory para evitar problemas de ownership en Windows.
    """
    try:
        ruta_absoluta = GitUtils.get_absolute_path(ruta_repo)
        env = GitUtils.get_safe_env()
        
        # Ejecutar comandos git en secuencia
        comandos = [
            (["git", "init"], "Error al inicializar"),
            (["git", "add", "-A"], "Error al añadir archivos"),
            (["git", "commit", "-m", mensaje], "Error al hacer commit")
        ]
        
        for cmd, error_msg in comandos:
            resultado = GitUtils.run_git_command(cmd, cwd=ruta_absoluta, timeout=10)
            if resultado.returncode != 0:
                return InitRepositoryResponse(
                    ok=False, 
                    error=f"{error_msg}: {resultado.stderr}"
                ).dict()
        
        # Añadir a safe.directory permanentemente
        GitUtils.configure_safe_directory_globally(ruta_absoluta)
        
        # Obtener hash del commit
        resultado = GitUtils.run_git_command(
            ["git", "rev-parse", "HEAD"], 
            cwd=ruta_absoluta, 
            timeout=5
        )
        commit_hash = resultado.stdout.strip() if resultado.returncode == 0 else "unknown"
        
        return InitRepositoryResponse(
            ok=True, 
            commit=commit_hash, 
            mensaje=mensaje, 
            path=ruta_absoluta
        ).dict()
    except Exception as e:
        logger.error(f"Error al inicializar git: {e}")
        return InitRepositoryResponse(
            ok=False, 
            error=str(e)
        ).dict()


@_handle_ownership_error
def git_diff_archivo(
    ruta_repo: str, 
    ruta_archivo: str, 
    commit1: Optional[str] = None, 
    commit2: Optional[str] = None
) -> Dict[str, Any]:

    """
    Genera un diccionario con la respuesta de git diff para un archivo específico.
    
    Args:
        ruta_repo (str): Ruta al repositorio Git
        ruta_archivo (str): Ruta del archivo a comparar
        commit1 (Optional[str]): Primer commit para comparación (opcional)
        commit2 (Optional[str]): Segundo commit para comparación (opcional)
    
    Lógica de comparación:
        - Si no hay commits: compara working directory con HEAD
        - Si hay un commit: compara working directory con ese commit
        - Si hay dos commits: compara commit1 vs commit2
    
    Returns:
        Dict[str, Any]: Información del diff del archivo
    """

    ruta_archivo = ruta_archivo.replace("\\", "/")  # Normalizar separadores de ruta para Git

    if not ruta_archivo.strip():
        return GitDiffResponse(
            ok=False,
            error="La ruta del archivo no puede estar vacía"
        ).dict()
    
    try:
        ruta_absoluta = GitUtils.get_absolute_path(ruta_repo)
        
        # Validar que es un repositorio Git válido
        is_valid, error_msg = GitUtils.validate_git_repository(ruta_absoluta)
        if not is_valid:
            return GitDiffResponse(
                ok=False,
                error=error_msg
            ).dict()
        
        repo, repo_error = GitUtils.get_repo_instance(ruta_repo)
        if not repo:
            return GitDiffResponse(
                ok=False,
                error=repo_error
            ).dict()
        
        # Determinar el tipo de comparación y ejecutar git diff
        diff_content = ""
        comparacion = ""
        commit1_info = None
        commit2_info = None
        
        try:
            if commit1 is None and commit2 is None:
                # Caso 1: Working directory vs HEAD
                comparacion = "Working directory vs HEAD"
                
                # Verificar si el archivo es nuevo (untracked)
                is_untracked = False
                try:
                    status_result = GitUtils.run_git_command(
                        ["git", "ls-files", "--others", "--exclude-standard", "--", ruta_archivo],
                        cwd=ruta_absoluta,
                        timeout=10
                    )
                    is_untracked = len(status_result.stdout.strip()) > 0
                except Exception:
                    pass
                
                if is_untracked:
                    # Para archivos no rastreados, usar git diff con /dev/null
                    result = GitUtils.run_git_command(
                        ["git", "diff", "--no-index", "/dev/null", ruta_archivo],
                        cwd=ruta_absoluta,
                        timeout=30
                    )
                    # git diff --no-index retorna código 1 cuando hay diferencias
                    if result.returncode in [0, 1]:
                        diff_content = result.stdout
                    else:
                        diff_content = result.stdout
                else:
                    # Para archivos rastreados, usar diff normal
                    result = GitUtils.run_git_command(
                        ["git", "diff", "HEAD", "--", ruta_archivo],
                        cwd=ruta_absoluta,
                        timeout=30
                    )
                    diff_content = result.stdout
                
                # Info del commit HEAD
                try:
                    head_commit = repo.head.commit
                    commit2_info = {
                        "hash": head_commit.hexsha[:7],
                        "hash_completo": head_commit.hexsha,
                        "mensaje": head_commit.message.strip(),
                        "autor": head_commit.author.name,
                        "fecha": head_commit.committed_datetime.isoformat()
                    }
                except Exception:
                    commit2_info = {"hash": "HEAD", "mensaje": "Unknown"}
                    
            elif commit1 is not None and commit2 is None:
                # Caso 2: Working directory vs commit específico
                comparacion = f"Working directory vs {commit1}"
                result = GitUtils.run_git_command(
                    ["git", "diff", commit1, "--", ruta_archivo],
                    cwd=ruta_absoluta,
                    timeout=30
                )
                diff_content = result.stdout
                
                # Info del commit especificado
                try:
                    commit_obj = repo.commit(commit1)
                    commit2_info = {
                        "hash": commit_obj.hexsha[:7],
                        "hash_completo": commit_obj.hexsha,
                        "mensaje": commit_obj.message.strip(),
                        "autor": commit_obj.author.name,
                        "fecha": commit_obj.committed_datetime.isoformat()
                    }
                except Exception:
                    commit2_info = {"hash": commit1, "mensaje": "Commit no encontrado"}
                    
            else:
                # Caso 3: Comparar entre dos commits
                comparacion = f"{commit1} vs {commit2}"
                result = GitUtils.run_git_command(
                    ["git", "diff", commit1, commit2, "--", ruta_archivo],
                    cwd=ruta_absoluta,
                    timeout=30
                )
                diff_content = result.stdout
                
                # Info de ambos commits
                try:
                    commit1_obj = repo.commit(commit1)
                    commit1_info = {
                        "hash": commit1_obj.hexsha[:7],
                        "hash_completo": commit1_obj.hexsha,
                        "mensaje": commit1_obj.message.strip(),
                        "autor": commit1_obj.author.name,
                        "fecha": commit1_obj.committed_datetime.isoformat()
                    }
                except Exception:
                    commit1_info = {"hash": commit1, "mensaje": "Commit no encontrado"}
                
                try:
                    commit2_obj = repo.commit(commit2)
                    commit2_info = {
                        "hash": commit2_obj.hexsha[:7],
                        "hash_completo": commit2_obj.hexsha,
                        "mensaje": commit2_obj.message.strip(),
                        "autor": commit2_obj.author.name,
                        "fecha": commit2_obj.committed_datetime.isoformat()
                    }
                except Exception:
                    commit2_info = {"hash": commit2, "mensaje": "Commit no encontrado"}
        
            # Verificar si el comando git diff fue exitoso
            # git diff --no-index retorna código 1 cuando hay diferencias, así que aceptamos 0 y 1
            if result.returncode not in [0, 1]:
                return GitDiffResponse(
                    ok=False,
                    ruta_repo=ruta_absoluta,
                    ruta_archivo=ruta_archivo,
                    error=f"Error al ejecutar git diff: {result.stderr.strip()}"
                ).dict()
        
            # Analizar el diff para extraer estadísticas
            hay_cambios = len(diff_content.strip()) > 0
            lineas_agregadas = 0
            lineas_eliminadas = 0
            es_archivo_nuevo = False
            
            if hay_cambios:
                # Detectar si es un archivo nuevo (--- /dev/null o new file mode)
                es_archivo_nuevo = '--- /dev/null' in diff_content or 'new file mode' in diff_content
                
                for line in diff_content.split('\n'):
                    if line.startswith('+') and not line.startswith('+++'):
                        lineas_agregadas += 1
                    elif line.startswith('-') and not line.startswith('---'):
                        lineas_eliminadas += 1
        
            return GitDiffResponse(
                ok=True,
                ruta_repo=ruta_absoluta,
                ruta_archivo=ruta_archivo,
                comparacion=comparacion,
                diff_content=diff_content,
                hay_cambios=hay_cambios,
                es_archivo_nuevo=es_archivo_nuevo,
                lineas_agregadas=lineas_agregadas,
                lineas_eliminadas=lineas_eliminadas,
                commit1_info=commit1_info,
                commit2_info=commit2_info,
                error=None
            ).dict()
        
        except subprocess.TimeoutExpired:
            return GitDiffResponse(
                ok=False,
                ruta_repo=ruta_absoluta,
                ruta_archivo=ruta_archivo,
                error="Timeout al ejecutar git diff"
            ).dict()
            
    except Exception as e:
        logger.error(f"Error en git_diff_archivo: {e}")
        return GitDiffResponse(
            ok=False,
            ruta_repo=ruta_repo,
            ruta_archivo=ruta_archivo,
            error=f"Error inesperado: {str(e)}"
        ).dict()




@_handle_ownership_error
def git_reset_hard_head(ruta_repo: str = ".") -> Dict[str, Any]:
    """
    Ejecuta `git reset --hard HEAD` para descartar todos los cambios en el working tree
    y en el index, seguido de `git clean -fd` para eliminar archivos y directorios no
    rastreados, dejando el repositorio limpio en el estado del último commit (HEAD).
    """
    try:
        ruta_absoluta = GitUtils.get_absolute_path(ruta_repo)

        # Validar que es un repositorio Git
        is_valid, error_msg = GitUtils.validate_git_repository(ruta_absoluta)
        if not is_valid:
            return ResetResponse(
                ok=False,
                success=False, 
                error=error_msg, 
                stderr=None, 
                stdout=""
            ).dict()

        # Ejecutar reset --hard HEAD
        cmd = ["git", "reset", "--hard", "HEAD"]
        resultado = GitUtils.run_git_command(cmd, cwd=ruta_absoluta, timeout=20)

        if resultado.returncode != 0:
            return ResetResponse(
                ok=False,
                success=False,
                stdout=resultado.stdout.strip(),
                stderr=resultado.stderr.strip(),
                error="Fallo al ejecutar git reset --hard HEAD"
            ).dict()

        # Limpiar archivos y directorios no rastreados
        clean_cmd = ["git", "clean", "-fd"]
        clean_result = GitUtils.run_git_command(clean_cmd, cwd=ruta_absoluta, timeout=30)

        clean_stderr = None
        if clean_result.returncode != 0:
            # Reintentar ignorando errores de borrado de directorios
            clean_cmd_quiet = ["git", "clean", "-fd", "--quiet"]
            clean_result = GitUtils.run_git_command(clean_cmd_quiet, cwd=ruta_absoluta, timeout=30)
            if clean_result.returncode != 0:
                clean_stderr = clean_result.stderr.strip() if clean_result.stderr else None
                logger.warning(f"git clean -fd falló: {clean_stderr}")

        combined_stdout = resultado.stdout.strip()
        if clean_result.stdout and clean_result.stdout.strip():
            combined_stdout += "\n" + clean_result.stdout.strip()

        return ResetResponse(
            ok=True,
            success=True,
            stdout=combined_stdout,
            stderr=clean_stderr,
            error=None
        ).dict()
    except Exception as e:
        logger.error(f"Error al ejecutar git reset --hard HEAD: {e}")
        return ResetResponse(
            ok=False,
            success=False,
            stdout="",
            stderr=None,
            error=f"Error al ejecutar git reset --hard HEAD: {e}"
        ).dict()


def _get_conflicting_files(ruta_absoluta: str) -> List[str]:
    """Obtiene la lista de archivos en conflicto (unmerged)."""
    result = GitUtils.run_git_command(
        ["git", "diff", "--name-only", "--diff-filter=U"],
        cwd=ruta_absoluta,
        timeout=10
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _is_merge_in_progress(ruta_absoluta: str) -> bool:
    """Indica si hay un merge en progreso (MERGE_HEAD presente)."""
    result = GitUtils.run_git_command(
        ["git", "rev-parse", "-q", "--verify", "MERGE_HEAD"],
        cwd=ruta_absoluta,
        timeout=5
    )
    return result.returncode == 0


def _set_last_merge_activity(
    ruta_absoluta: str,
    operation: str,
    stdout: Optional[str],
    stderr: Optional[str]
) -> None:
    """Registra la última actividad de operaciones de merge por repositorio."""
    _LAST_MERGE_ACTIVITY[ruta_absoluta] = {
        "operation": operation,
        "stdout": (stdout or "").strip() if stdout is not None else None,
        "stderr": (stderr or "").strip() if stderr is not None else None,
    }


@_handle_ownership_error
def hacer_merge_rama(ruta_repo: str = ".", source_ref: str = "") -> Dict[str, Any]:
    """
    Ejecuta merge de una referencia/rama sobre la rama actual.
    Si hay conflictos, retorna el listado para resolución vía API.
    """
    if not source_ref.strip():
        raise ValueError("La referencia a mergear no puede estar vacía")

    ruta_absoluta = GitUtils.get_absolute_path(ruta_repo)
    is_valid, error_msg = GitUtils.validate_git_repository(ruta_absoluta)
    if not is_valid:
        raise ValueError(error_msg)

    current_branch_result = GitUtils.run_git_command(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=ruta_absoluta,
        timeout=5
    )
    current_branch = current_branch_result.stdout.strip() if current_branch_result.returncode == 0 else None

    merge_result = GitUtils.run_git_command(
        ["git", "merge", source_ref],
        cwd=ruta_absoluta,
        timeout=60
    )
    _set_last_merge_activity(
        ruta_absoluta,
        f"merge {source_ref}",
        merge_result.stdout,
        merge_result.stderr
    )

    if merge_result.returncode == 0:
        return MergeResponse(
            ok=True,
            success=True,
            current_branch=current_branch,
            merged_ref=source_ref,
            has_conflicts=False,
            conflicting_files=[],
            stdout=merge_result.stdout.strip(),
            stderr=None,
            error=None
        ).dict()

    conflicting_files = _get_conflicting_files(ruta_absoluta)
    merge_in_progress = _is_merge_in_progress(ruta_absoluta)
    has_conflicts = len(conflicting_files) > 0 or merge_in_progress

    return MergeResponse(
        ok=False,
        success=False,
        current_branch=current_branch,
        merged_ref=source_ref,
        has_conflicts=has_conflicts,
        conflicting_files=conflicting_files,
        stdout=merge_result.stdout.strip(),
        stderr=merge_result.stderr.strip() if merge_result.stderr else None,
        error=(
            "Merge con conflictos. Resuelve los conflictos y finaliza el merge por API."
            if has_conflicts
            else f"Fallo al ejecutar merge: {(merge_result.stderr or '').strip()}"
        )
    ).dict()


@_handle_ownership_error
def obtener_conflictos_merge(ruta_repo: str = ".") -> Dict[str, Any]:
    """Consulta si hay merge en progreso y qué archivos están en conflicto."""
    ruta_absoluta = GitUtils.get_absolute_path(ruta_repo)
    is_valid, error_msg = GitUtils.validate_git_repository(ruta_absoluta)
    if not is_valid:
        raise ValueError(error_msg)

    merge_in_progress = _is_merge_in_progress(ruta_absoluta)
    conflicting_files = _get_conflicting_files(ruta_absoluta)

    return MergeConflictsStatusResponse(
        ok=True,
        merge_in_progress=merge_in_progress,
        conflicting_files=conflicting_files,
        error=None
    ).dict()


@_handle_ownership_error
def resolver_conflicto_archivo(
    ruta_repo: str = ".",
    ruta_archivo: str = "",
    estrategia: str = "",
    contenido_resuelto: Optional[str] = None
) -> Dict[str, Any]:
    """
    Resuelve un archivo en conflicto usando estrategia ours/theirs/manual y lo marca en staging.
    """
    if not ruta_archivo.strip():
        raise ValueError("La ruta del archivo no puede estar vacía")

    estrategia_limpia = estrategia.strip().lower()
    if estrategia_limpia not in {"ours", "theirs", "manual"}:
        raise ValueError("La estrategia debe ser: ours, theirs o manual")

    ruta_absoluta = GitUtils.get_absolute_path(ruta_repo)
    is_valid, error_msg = GitUtils.validate_git_repository(ruta_absoluta)
    if not is_valid:
        raise ValueError(error_msg)

    archivo_git = ruta_archivo.replace("\\", "/").strip()
    conflicting_files = _get_conflicting_files(ruta_absoluta)

    if archivo_git not in conflicting_files:
        return ResolveConflictResponse(
            ok=False,
            success=False,
            file_path=archivo_git,
            strategy=estrategia_limpia,
            remaining_conflicts=conflicting_files,
            error="El archivo no está en estado de conflicto"
        ).dict()

    try:
        if estrategia_limpia in {"ours", "theirs"}:
            checkout_result = GitUtils.run_git_command(
                ["git", "checkout", f"--{estrategia_limpia}", "--", archivo_git],
                cwd=ruta_absoluta,
                timeout=20
            )
            if checkout_result.returncode != 0:
                return ResolveConflictResponse(
                    ok=False,
                    success=False,
                    file_path=archivo_git,
                    strategy=estrategia_limpia,
                    remaining_conflicts=conflicting_files,
                    error=f"No se pudo aplicar estrategia {estrategia_limpia}: {checkout_result.stderr.strip()}"
                ).dict()
        else:
            if contenido_resuelto is None:
                raise ValueError("Para estrategia manual debes enviar contenido_resuelto")

            repo_path = Path(ruta_absoluta).resolve()
            target_path = (repo_path / archivo_git).resolve()

            if repo_path != target_path and repo_path not in target_path.parents:
                raise ValueError("La ruta del archivo está fuera del repositorio")

            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(contenido_resuelto, encoding="utf-8")

        add_result = GitUtils.run_git_command(
            ["git", "add", "--", archivo_git],
            cwd=ruta_absoluta,
            timeout=20
        )
        if add_result.returncode != 0:
            return ResolveConflictResponse(
                ok=False,
                success=False,
                file_path=archivo_git,
                strategy=estrategia_limpia,
                remaining_conflicts=_get_conflicting_files(ruta_absoluta),
                error=f"No se pudo marcar el archivo como resuelto: {add_result.stderr.strip()}"
            ).dict()

        remaining_conflicts = _get_conflicting_files(ruta_absoluta)
        was_resolved = archivo_git not in remaining_conflicts

        return ResolveConflictResponse(
            ok=was_resolved,
            success=was_resolved,
            file_path=archivo_git,
            strategy=estrategia_limpia,
            remaining_conflicts=remaining_conflicts,
            error=None if was_resolved else "El archivo sigue en conflicto"
        ).dict()
    except Exception as e:
        logger.error(f"Error al resolver conflicto de archivo: {e}")
        return ResolveConflictResponse(
            ok=False,
            success=False,
            file_path=archivo_git,
            strategy=estrategia_limpia,
            remaining_conflicts=_get_conflicting_files(ruta_absoluta),
            error=f"Error al resolver conflicto: {str(e)}"
        ).dict()


@_handle_ownership_error
def finalizar_merge(ruta_repo: str = ".", mensaje: str = "Merge commit") -> Dict[str, Any]:
    """Finaliza un merge en curso creando el commit de merge."""
    if not mensaje.strip():
        raise ValueError("El mensaje del commit de merge no puede estar vacío")

    ruta_absoluta = GitUtils.get_absolute_path(ruta_repo)
    is_valid, error_msg = GitUtils.validate_git_repository(ruta_absoluta)
    if not is_valid:
        raise ValueError(error_msg)

    if not _is_merge_in_progress(ruta_absoluta):
        return CommitOperationResponse(
            ok=False,
            success=False,
            commit_hash=None,
            short_hash=None,
            message=mensaje,
            author=None,
            date=None,
            files_committed=[],
            error="No hay un merge en progreso para finalizar"
        ).dict()

    remaining_conflicts = _get_conflicting_files(ruta_absoluta)
    if remaining_conflicts:
        return CommitOperationResponse(
            ok=False,
            success=False,
            commit_hash=None,
            short_hash=None,
            message=mensaje,
            author=None,
            date=None,
            files_committed=[],
            error=f"Aún hay conflictos sin resolver: {', '.join(remaining_conflicts)}"
        ).dict()

    commit_result = GitUtils.run_git_command(
        ["git", "commit", "-m", mensaje],
        cwd=ruta_absoluta,
        timeout=30
    )
    _set_last_merge_activity(
        ruta_absoluta,
        "merge finalize",
        commit_result.stdout,
        commit_result.stderr
    )

    if commit_result.returncode != 0:
        return CommitOperationResponse(
            ok=False,
            success=False,
            commit_hash=None,
            short_hash=None,
            message=mensaje,
            author=None,
            date=None,
            files_committed=[],
            error=f"No se pudo finalizar el merge: {commit_result.stderr.strip()}"
        ).dict()

    repo, repo_error = GitUtils.get_repo_instance(ruta_absoluta)
    if not repo:
        return CommitOperationResponse(
            ok=False,
            success=False,
            commit_hash=None,
            short_hash=None,
            message=mensaje,
            author=None,
            date=None,
            files_committed=[],
            error=repo_error
        ).dict()

    commit = repo.head.commit

    return CommitOperationResponse(
        ok=True,
        success=True,
        commit_hash=commit.hexsha,
        short_hash=commit.hexsha[:7],
        message=commit.message.strip(),
        author=f"{commit.author.name} <{commit.author.email}>",
        date=commit.committed_datetime.isoformat(),
        files_committed=list(commit.stats.files.keys()),
        error=None
    ).dict()


@_handle_ownership_error
def abortar_merge(ruta_repo: str = ".") -> Dict[str, Any]:
    """Aborta un merge en curso usando `git merge --abort`."""
    ruta_absoluta = GitUtils.get_absolute_path(ruta_repo)
    is_valid, error_msg = GitUtils.validate_git_repository(ruta_absoluta)
    if not is_valid:
        raise ValueError(error_msg)

    if not _is_merge_in_progress(ruta_absoluta):
        return AbortMergeResponse(
            ok=False,
            success=False,
            stdout="",
            stderr=None,
            error="No hay un merge en progreso para abortar"
        ).dict()

    result = GitUtils.run_git_command(
        ["git", "merge", "--abort"],
        cwd=ruta_absoluta,
        timeout=30
    )
    _set_last_merge_activity(
        ruta_absoluta,
        "merge abort",
        result.stdout,
        result.stderr
    )

    if result.returncode != 0:
        return AbortMergeResponse(
            ok=False,
            success=False,
            stdout=result.stdout.strip(),
            stderr=result.stderr.strip() if result.stderr else None,
            error="No se pudo abortar el merge"
        ).dict()

    return AbortMergeResponse(
        ok=True,
        success=True,
        stdout=result.stdout.strip(),
        stderr=None,
        error=None
    ).dict()


@_handle_ownership_error
def obtener_estado_merge_detallado(ruta_repo: str = ".") -> Dict[str, Any]:
    """Obtiene el estado detallado de merge del repositorio."""
    ruta_absoluta = GitUtils.get_absolute_path(ruta_repo)
    is_valid, error_msg = GitUtils.validate_git_repository(ruta_absoluta)
    if not is_valid:
        raise ValueError(error_msg)

    merge_in_progress = _is_merge_in_progress(ruta_absoluta)
    conflicting_files = _get_conflicting_files(ruta_absoluta)
    current_branch_result = GitUtils.run_git_command(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=ruta_absoluta,
        timeout=5
    )
    current_branch = current_branch_result.stdout.strip() if current_branch_result.returncode == 0 else None

    last_activity = _LAST_MERGE_ACTIVITY.get(ruta_absoluta, {})

    return MergeStatusResponse(
        ok=True,
        merge_in_progress=merge_in_progress,
        current_branch=current_branch,
        conflicting_files=conflicting_files,
        can_finalize=merge_in_progress and len(conflicting_files) == 0,
        can_abort=merge_in_progress,
        last_operation=last_activity.get("operation"),
        last_stdout=last_activity.get("stdout"),
        last_stderr=last_activity.get("stderr"),
        error=None
    ).dict()


@_handle_ownership_error
def listar_commits_rama(ruta_repo: str = ".", rama: str = "", max_commits: int = 100) -> Dict[str, Any]:
    """
    Lista los commits de una rama específica con hash corto, fecha y mensaje.
    
    Args:
        ruta_repo (str): Ruta al repositorio Git. Por defecto es el directorio actual.
        rama (str): Nombre de la rama (ej: 'main', 'master', 'develop'). Si está vacío, usa HEAD.
        max_commits (int): Número máximo de commits a mostrar. Por defecto 100.
    
    Returns:
        Dict con la información de los commits
    """
    try:
        ruta_absoluta = GitUtils.get_absolute_path(ruta_repo)
        
        # Validar que es repositorio
        is_valid, error_msg = GitUtils.validate_git_repository(ruta_absoluta)
        if not is_valid:
            return CommitListResponse(
                ok=False,
                rama=rama,
                commits=[],
                total=0,
                error=error_msg
            ).dict()
        
        # Si no se especifica rama, usar HEAD
        rama_ref = rama if rama.strip() else "HEAD"
        
        # Verificar que la rama existe
        if rama.strip():
            check_branch = GitUtils.run_git_command(
                ["git", "rev-parse", "--verify", rama_ref], 
                cwd=ruta_absoluta, 
                timeout=5
            )
            
            if check_branch.returncode != 0:
                return CommitListResponse(
                    ok=False,
                    rama=rama,
                    commits=[],
                    total=0,
                    error=f"La rama '{rama}' no existe"
                ).dict()
        
        # Usar GitPython para obtener commits con precisión
        try:
            repo = Repo(ruta_absoluta, search_parent_directories=True)
            commits_list = []
            
            for commit in repo.iter_commits(rama_ref, max_count=max_commits):
                commits_list.append({
                    "hash_corto": commit.hexsha[:7],
                    "hash_completo": commit.hexsha,
                    "fecha": commit.committed_datetime.isoformat(),
                    "mensaje": commit.message.strip(),
                    "autor": commit.author.name,
                    "email": commit.author.email
                })
            
            return CommitListResponse(
                ok=True,
                rama=rama if rama.strip() else "HEAD",
                commits=commits_list,
                total=len(commits_list),
                error=None
            ).dict()
        except (InvalidGitRepositoryError, NoSuchPathError) as e:
            return CommitListResponse(
                ok=False,
                rama=rama,
                commits=[],
                total=0,
                error=f"Error al acceder al repositorio: {str(e)}"
            ).dict()
        
    except Exception as e:
        logger.error(f"Error al listar commits: {e}")
        return CommitListResponse(
            ok=False,
            rama=rama,
            commits=[],
            total=0,
            error=f"Error al listar commits: {str(e)}"
        ).dict()


# ===================================================================
# HELPERS PARA GIT DISTRIBUIDO
# ===================================================================

def _build_auth_env(token: str = "") -> Dict[str, str]:
    """
    Construye variables de entorno con autenticación opcional por token.
    Usa GIT_CONFIG para inyectar http.extraHeader de forma segura sin persistir en disco.
    """
    env = GitUtils.get_safe_env()
    if token.strip():
        cred = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        # get_safe_env ya configura GIT_CONFIG_COUNT=1 con safe.directory
        env['GIT_CONFIG_COUNT'] = '2'
        env['GIT_CONFIG_KEY_1'] = 'http.extraHeader'
        env['GIT_CONFIG_VALUE_1'] = f'AUTHORIZATION: basic {cred}'
    return env


def _run_git_with_auth(
    command: list,
    cwd: str,
    token: str = "",
    timeout: int = 120
) -> subprocess.CompletedProcess:
    """Ejecuta un comando git con autenticación opcional por token."""
    env = _build_auth_env(token)
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env
    )


def _sanitize_output(text: str) -> str:
    """Elimina credenciales/tokens de URLs en texto de salida."""
    if not text:
        return text
    return re.sub(r'(https?://)([^@\s]+@)', r'\1', text)


def _validate_git_url(url: str) -> bool:
    """Valida que la URL sea una URL de Git válida."""
    url = url.strip()
    return bool(
        url.startswith("https://") or
        url.startswith("http://") or
        url.startswith("git@") or
        url.startswith("ssh://") or
        url.startswith("git://")
    )


def _inject_token_in_url(url: str, token: str) -> str:
    """Inyecta un token de autenticación en una URL HTTPS de Git."""
    if not token.strip() or not url.startswith("https://"):
        return url
    return url.replace("https://", f"https://x-access-token:{token}@", 1)


# ===================================================================
# FUNCIONES DE GIT DISTRIBUIDO
# ===================================================================

# --- REMOTE ---

@_handle_ownership_error
def listar_remotos(ruta_repo: str = ".") -> Dict[str, Any]:
    """Lista todos los remotes configurados con sus URLs."""
    ruta_absoluta = GitUtils.get_absolute_path(ruta_repo)
    is_valid, error_msg = GitUtils.validate_git_repository(ruta_absoluta)
    if not is_valid:
        return RemoteListResponse(ok=False, remotes=[], error=error_msg).dict()

    try:
        result = GitUtils.run_git_command(
            ["git", "remote", "-v"],
            cwd=ruta_absoluta, timeout=10
        )
        if result.returncode != 0:
            return RemoteListResponse(
                ok=False, remotes=[],
                error=f"Error al listar remotos: {result.stderr.strip()}"
            ).dict()

        remotes_dict: Dict[str, Dict[str, str]] = {}
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 2:
                name = parts[0]
                url = parts[1]
                direction = parts[2] if len(parts) > 2 else ""
                if name not in remotes_dict:
                    remotes_dict[name] = {"name": name, "url_fetch": "", "url_push": ""}
                if "(fetch)" in direction:
                    remotes_dict[name]["url_fetch"] = url
                elif "(push)" in direction:
                    remotes_dict[name]["url_push"] = url

        remotes = [RemoteInfo(**r) for r in remotes_dict.values()]
        return RemoteListResponse(ok=True, remotes=remotes, error=None).dict()

    except Exception as e:
        logger.error(f"Error al listar remotos: {e}")
        return RemoteListResponse(
            ok=False, remotes=[],
            error=f"Error al listar remotos: {str(e)}"
        ).dict()


@_handle_ownership_error
def agregar_remoto(ruta_repo: str = ".", nombre: str = "", url: str = "") -> Dict[str, Any]:
    """Agrega un nuevo remote al repositorio."""
    if not nombre.strip():
        raise ValueError("El nombre del remote no puede estar vacío")
    if not url.strip():
        raise ValueError("La URL del remote no puede estar vacía")
    if not _validate_git_url(url):
        raise ValueError("La URL proporcionada no es una URL de Git válida")

    ruta_absoluta = GitUtils.get_absolute_path(ruta_repo)
    is_valid, error_msg = GitUtils.validate_git_repository(ruta_absoluta)
    if not is_valid:
        raise ValueError(error_msg)

    try:
        result = GitUtils.run_git_command(
            ["git", "remote", "add", nombre.strip(), url.strip()],
            cwd=ruta_absoluta, timeout=10
        )
        if result.returncode != 0:
            return RemoteOperationResponse(
                ok=False, success=False, remote_name=nombre.strip(),
                url=url.strip(), stdout=result.stdout.strip(),
                stderr=result.stderr.strip(),
                error=f"Error al agregar remote: {result.stderr.strip()}"
            ).dict()

        return RemoteOperationResponse(
            ok=True, success=True, remote_name=nombre.strip(),
            url=url.strip(), stdout=result.stdout.strip(),
            stderr=None, error=None
        ).dict()
    except Exception as e:
        logger.error(f"Error al agregar remote: {e}")
        return RemoteOperationResponse(
            ok=False, success=False, remote_name=nombre.strip(),
            url=url.strip(), stdout="", stderr=None,
            error=f"Error al agregar remote: {str(e)}"
        ).dict()


@_handle_ownership_error
def eliminar_remoto(ruta_repo: str = ".", nombre: str = "") -> Dict[str, Any]:
    """Elimina un remote del repositorio."""
    if not nombre.strip():
        raise ValueError("El nombre del remote no puede estar vacío")

    ruta_absoluta = GitUtils.get_absolute_path(ruta_repo)
    is_valid, error_msg = GitUtils.validate_git_repository(ruta_absoluta)
    if not is_valid:
        raise ValueError(error_msg)

    try:
        result = GitUtils.run_git_command(
            ["git", "remote", "remove", nombre.strip()],
            cwd=ruta_absoluta, timeout=10
        )
        if result.returncode != 0:
            return RemoteOperationResponse(
                ok=False, success=False, remote_name=nombre.strip(),
                stdout=result.stdout.strip(), stderr=result.stderr.strip(),
                error=f"Error al eliminar remote: {result.stderr.strip()}"
            ).dict()

        return RemoteOperationResponse(
            ok=True, success=True, remote_name=nombre.strip(),
            stdout=result.stdout.strip(), stderr=None, error=None
        ).dict()
    except Exception as e:
        logger.error(f"Error al eliminar remote: {e}")
        return RemoteOperationResponse(
            ok=False, success=False, remote_name=nombre.strip(),
            stdout="", stderr=None,
            error=f"Error al eliminar remote: {str(e)}"
        ).dict()


@_handle_ownership_error
def renombrar_remoto(ruta_repo: str = ".", nombre_actual: str = "", nombre_nuevo: str = "") -> Dict[str, Any]:
    """Renombra un remote en el repositorio."""
    if not nombre_actual.strip():
        raise ValueError("El nombre actual del remote no puede estar vacío")
    if not nombre_nuevo.strip():
        raise ValueError("El nuevo nombre del remote no puede estar vacío")

    ruta_absoluta = GitUtils.get_absolute_path(ruta_repo)
    is_valid, error_msg = GitUtils.validate_git_repository(ruta_absoluta)
    if not is_valid:
        raise ValueError(error_msg)

    try:
        result = GitUtils.run_git_command(
            ["git", "remote", "rename", nombre_actual.strip(), nombre_nuevo.strip()],
            cwd=ruta_absoluta, timeout=10
        )
        if result.returncode != 0:
            return RemoteOperationResponse(
                ok=False, success=False, remote_name=nombre_actual.strip(),
                stdout=result.stdout.strip(), stderr=result.stderr.strip(),
                error=f"Error al renombrar remote: {result.stderr.strip()}"
            ).dict()

        return RemoteOperationResponse(
            ok=True, success=True, remote_name=nombre_nuevo.strip(),
            stdout=result.stdout.strip(), stderr=None, error=None
        ).dict()
    except Exception as e:
        logger.error(f"Error al renombrar remote: {e}")
        return RemoteOperationResponse(
            ok=False, success=False, remote_name=nombre_actual.strip(),
            stdout="", stderr=None,
            error=f"Error al renombrar remote: {str(e)}"
        ).dict()


@_handle_ownership_error
def cambiar_url_remoto(ruta_repo: str = ".", nombre: str = "", url: str = "") -> Dict[str, Any]:
    """Cambia la URL de un remote existente."""
    if not nombre.strip():
        raise ValueError("El nombre del remote no puede estar vacío")
    if not url.strip():
        raise ValueError("La URL del remote no puede estar vacía")
    if not _validate_git_url(url):
        raise ValueError("La URL proporcionada no es una URL de Git válida")

    ruta_absoluta = GitUtils.get_absolute_path(ruta_repo)
    is_valid, error_msg = GitUtils.validate_git_repository(ruta_absoluta)
    if not is_valid:
        raise ValueError(error_msg)

    try:
        result = GitUtils.run_git_command(
            ["git", "remote", "set-url", nombre.strip(), url.strip()],
            cwd=ruta_absoluta, timeout=10
        )
        if result.returncode != 0:
            return RemoteOperationResponse(
                ok=False, success=False, remote_name=nombre.strip(),
                url=url.strip(), stdout=result.stdout.strip(),
                stderr=result.stderr.strip(),
                error=f"Error al cambiar URL: {result.stderr.strip()}"
            ).dict()

        return RemoteOperationResponse(
            ok=True, success=True, remote_name=nombre.strip(),
            url=url.strip(), stdout=result.stdout.strip(),
            stderr=None, error=None
        ).dict()
    except Exception as e:
        logger.error(f"Error al cambiar URL del remote: {e}")
        return RemoteOperationResponse(
            ok=False, success=False, remote_name=nombre.strip(),
            url=url.strip(), stdout="", stderr=None,
            error=f"Error al cambiar URL del remote: {str(e)}"
        ).dict()


# --- CLONE ---

def clonar_repositorio(
    url: str = "",
    ruta_destino: str = "",
    rama: str = "",
    profundidad: int = 0,
    token: str = ""
) -> Dict[str, Any]:
    """
    Clona un repositorio Git remoto.
    Si se proporciona un token, lo usa para autenticación HTTPS.
    Después de clonar, limpia el token de la URL del remote.
    """
    if not url.strip():
        raise ValueError("La URL del repositorio no puede estar vacía")
    if not ruta_destino.strip():
        raise ValueError("La ruta de destino no puede estar vacía")
    if not _validate_git_url(url):
        raise ValueError("La URL proporcionada no es una URL de Git válida")

    try:
        ruta_destino_abs = str(Path(ruta_destino).resolve())

        # Verificar que el directorio destino no exista o esté vacío
        if Path(ruta_destino_abs).exists() and any(Path(ruta_destino_abs).iterdir()):
            return CloneResponse(
                ok=False, success=False, path=ruta_destino_abs,
                error="El directorio de destino ya existe y no está vacío"
            ).dict()

        # Asegurar que el directorio padre existe
        parent_dir = Path(ruta_destino_abs).parent
        parent_dir.mkdir(parents=True, exist_ok=True)

        # Construir comando de clonación
        clone_url = _inject_token_in_url(url.strip(), token) if token.strip() else url.strip()
        cmd = ["git", "clone"]

        if rama.strip():
            cmd.extend(["--branch", rama.strip()])
        if profundidad > 0:
            cmd.extend(["--depth", str(profundidad)])

        cmd.extend([clone_url, ruta_destino_abs])

        # Ejecutar clone con auth env
        result = _run_git_with_auth(
            cmd,
            cwd=str(parent_dir),
            token=token,
            timeout=300
        )

        if result.returncode != 0:
            return CloneResponse(
                ok=False, success=False, path=ruta_destino_abs,
                remote_url=url.strip(),
                stdout=_sanitize_output(result.stdout.strip()),
                stderr=_sanitize_output(result.stderr.strip()),
                error=f"Error al clonar: {_sanitize_output(result.stderr.strip())}"
            ).dict()

        # Si usamos token en la URL, limpiar la URL del remote para no persistir el token
        if token.strip() and url.startswith("https://"):
            GitUtils.run_git_command(
                ["git", "remote", "set-url", "origin", url.strip()],
                cwd=ruta_destino_abs, timeout=10
            )

        # Obtener la rama actual del repo clonado
        branch_result = GitUtils.run_git_command(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=ruta_destino_abs, timeout=5
        )
        branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None

        return CloneResponse(
            ok=True, success=True, path=ruta_destino_abs,
            remote_url=url.strip(), branch=branch,
            stdout=_sanitize_output(result.stdout.strip()),
            stderr=_sanitize_output(result.stderr.strip()) if result.stderr else None,
            error=None
        ).dict()

    except subprocess.TimeoutExpired:
        return CloneResponse(
            ok=False, success=False, path=ruta_destino,
            remote_url=url.strip(),
            error="Timeout al clonar el repositorio (máximo 300 segundos)"
        ).dict()
    except Exception as e:
        logger.error(f"Error al clonar repositorio: {e}")
        return CloneResponse(
            ok=False, success=False, path=ruta_destino,
            remote_url=url.strip(),
            error=f"Error al clonar: {_sanitize_output(str(e))}"
        ).dict()


# --- PUSH ---

@_handle_ownership_error
def hacer_push(
    ruta_repo: str = ".",
    remote: str = "origin",
    rama: str = "",
    forzar: bool = False,
    set_upstream: bool = False,
    tags: bool = False,
    token: str = ""
) -> Dict[str, Any]:
    """
    Ejecuta git push al remote especificado.
    Soporta push forzado, configuración de upstream y envío de tags.
    """
    ruta_absoluta = GitUtils.get_absolute_path(ruta_repo)
    is_valid, error_msg = GitUtils.validate_git_repository(ruta_absoluta)
    if not is_valid:
        raise ValueError(error_msg)

    try:
        # Obtener rama actual si no se especifica
        if not rama.strip():
            branch_result = GitUtils.run_git_command(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=ruta_absoluta, timeout=5
            )
            rama = branch_result.stdout.strip() if branch_result.returncode == 0 else ""

        cmd = ["git", "push"]
        if set_upstream:
            cmd.append("-u")
        if forzar:
            cmd.append("--force")
        if tags:
            cmd.append("--tags")
        cmd.append(remote.strip())
        if rama.strip():
            cmd.append(rama.strip())

        result = _run_git_with_auth(cmd, cwd=ruta_absoluta, token=token, timeout=120)

        if result.returncode != 0:
            return PushResponse(
                ok=False, success=False, remote=remote.strip(),
                branch=rama.strip(), set_upstream=set_upstream,
                stdout=_sanitize_output(result.stdout.strip()),
                stderr=_sanitize_output(result.stderr.strip()),
                error=f"Error al hacer push: {_sanitize_output(result.stderr.strip())}"
            ).dict()

        return PushResponse(
            ok=True, success=True, remote=remote.strip(),
            branch=rama.strip(), set_upstream=set_upstream,
            stdout=_sanitize_output(result.stdout.strip()),
            stderr=_sanitize_output(result.stderr.strip()) if result.stderr else None,
            error=None
        ).dict()

    except subprocess.TimeoutExpired:
        return PushResponse(
            ok=False, success=False, remote=remote.strip(),
            branch=rama.strip(),
            error="Timeout al hacer push (máximo 120 segundos)"
        ).dict()
    except Exception as e:
        logger.error(f"Error al hacer push: {e}")
        return PushResponse(
            ok=False, success=False, remote=remote.strip(),
            branch=rama.strip(),
            error=f"Error al hacer push: {_sanitize_output(str(e))}"
        ).dict()


# --- PULL ---

@_handle_ownership_error
def hacer_pull(
    ruta_repo: str = ".",
    remote: str = "origin",
    rama: str = "",
    rebase: bool = False,
    token: str = ""
) -> Dict[str, Any]:
    """
    Ejecuta git pull desde el remote especificado.
    Soporta pull con rebase.
    """
    ruta_absoluta = GitUtils.get_absolute_path(ruta_repo)
    is_valid, error_msg = GitUtils.validate_git_repository(ruta_absoluta)
    if not is_valid:
        raise ValueError(error_msg)

    try:
        cmd = ["git", "pull"]
        if rebase:
            cmd.append("--rebase")
        cmd.append(remote.strip())
        if rama.strip():
            cmd.append(rama.strip())

        result = _run_git_with_auth(cmd, cwd=ruta_absoluta, token=token, timeout=120)

        # Verificar conflictos
        conflicting_files = _get_conflicting_files(ruta_absoluta)
        has_conflicts = len(conflicting_files) > 0

        if result.returncode != 0 and not has_conflicts:
            return PullResponse(
                ok=False, success=False, remote=remote.strip(),
                branch=rama.strip(), has_conflicts=False,
                conflicting_files=[],
                stdout=_sanitize_output(result.stdout.strip()),
                stderr=_sanitize_output(result.stderr.strip()),
                error=f"Error al hacer pull: {_sanitize_output(result.stderr.strip())}"
            ).dict()

        return PullResponse(
            ok=not has_conflicts, success=not has_conflicts,
            remote=remote.strip(), branch=rama.strip(),
            has_conflicts=has_conflicts,
            conflicting_files=conflicting_files,
            stdout=_sanitize_output(result.stdout.strip()),
            stderr=_sanitize_output(result.stderr.strip()) if result.stderr else None,
            error="Pull completado con conflictos. Resuelve los conflictos." if has_conflicts else None
        ).dict()

    except subprocess.TimeoutExpired:
        return PullResponse(
            ok=False, success=False, remote=remote.strip(),
            branch=rama.strip(),
            error="Timeout al hacer pull (máximo 120 segundos)"
        ).dict()
    except Exception as e:
        logger.error(f"Error al hacer pull: {e}")
        return PullResponse(
            ok=False, success=False, remote=remote.strip(),
            branch=rama.strip(),
            error=f"Error al hacer pull: {_sanitize_output(str(e))}"
        ).dict()


# --- FETCH ---

@_handle_ownership_error
def hacer_fetch(
    ruta_repo: str = ".",
    remote: str = "",
    prune: bool = False,
    tags: bool = True,
    token: str = ""
) -> Dict[str, Any]:
    """
    Ejecuta git fetch desde el remote especificado.
    Soporta prune y fetch de tags.
    """
    ruta_absoluta = GitUtils.get_absolute_path(ruta_repo)
    is_valid, error_msg = GitUtils.validate_git_repository(ruta_absoluta)
    if not is_valid:
        raise ValueError(error_msg)

    try:
        cmd = ["git", "fetch"]
        if prune:
            cmd.append("--prune")
        if tags:
            cmd.append("--tags")
        if remote.strip():
            cmd.append(remote.strip())
        else:
            cmd.append("--all")

        result = _run_git_with_auth(cmd, cwd=ruta_absoluta, token=token, timeout=120)

        if result.returncode != 0:
            return FetchResponse(
                ok=False, success=False,
                remote=remote.strip() or "all",
                stdout=_sanitize_output(result.stdout.strip()),
                stderr=_sanitize_output(result.stderr.strip()),
                error=f"Error al hacer fetch: {_sanitize_output(result.stderr.strip())}"
            ).dict()

        return FetchResponse(
            ok=True, success=True,
            remote=remote.strip() or "all",
            stdout=_sanitize_output(result.stdout.strip()),
            stderr=_sanitize_output(result.stderr.strip()) if result.stderr else None,
            error=None
        ).dict()

    except subprocess.TimeoutExpired:
        return FetchResponse(
            ok=False, success=False,
            remote=remote.strip() or "all",
            error="Timeout al hacer fetch (máximo 120 segundos)"
        ).dict()
    except Exception as e:
        logger.error(f"Error al hacer fetch: {e}")
        return FetchResponse(
            ok=False, success=False,
            remote=remote.strip() or "all",
            error=f"Error al hacer fetch: {_sanitize_output(str(e))}"
        ).dict()


# --- REMOTE BRANCHES ---

@_handle_ownership_error
def listar_ramas_remotas(ruta_repo: str = ".", remote: str = "") -> Dict[str, Any]:
    """Lista las ramas remotas del repositorio."""
    ruta_absoluta = GitUtils.get_absolute_path(ruta_repo)
    is_valid, error_msg = GitUtils.validate_git_repository(ruta_absoluta)
    if not is_valid:
        return RemoteBranchesResponse(ok=False, branches=[], error=error_msg).dict()

    try:
        cmd = ["git", "branch", "-r", "--format", "%(refname:short)"]
        result = GitUtils.run_git_command(cmd, cwd=ruta_absoluta, timeout=10)

        if result.returncode != 0:
            return RemoteBranchesResponse(
                ok=False, branches=[],
                error=f"Error al listar ramas remotas: {result.stderr.strip()}"
            ).dict()

        branches = [b.strip() for b in result.stdout.splitlines() if b.strip()]

        # Filtrar por remote si se especifica
        if remote.strip():
            prefix = f"{remote.strip()}/"
            branches = [b for b in branches if b.startswith(prefix)]

        return RemoteBranchesResponse(
            ok=True, branches=branches,
            remote=remote.strip() or None, error=None
        ).dict()

    except Exception as e:
        logger.error(f"Error al listar ramas remotas: {e}")
        return RemoteBranchesResponse(
            ok=False, branches=[],
            error=f"Error al listar ramas remotas: {str(e)}"
        ).dict()


# --- DELETE BRANCH ---

@_handle_ownership_error
def eliminar_rama(
    ruta_repo: str = ".",
    branch_name: str = "",
    forzar: bool = False,
    eliminar_remoto: bool = False,
    remote: str = "origin",
    token: str = ""
) -> Dict[str, Any]:
    """
    Elimina una rama local y opcionalmente del remoto.
    """
    if not branch_name.strip():
        raise ValueError("El nombre de la rama no puede estar vacío")

    ruta_absoluta = GitUtils.get_absolute_path(ruta_repo)
    is_valid, error_msg = GitUtils.validate_git_repository(ruta_absoluta)
    if not is_valid:
        raise ValueError(error_msg)

    try:
        # Verificar que no estamos en la rama a eliminar
        current_result = GitUtils.run_git_command(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=ruta_absoluta, timeout=5
        )
        current_branch = current_result.stdout.strip() if current_result.returncode == 0 else ""

        if current_branch == branch_name.strip():
            return BranchDeleteResponse(
                ok=False, success=False, branch=branch_name.strip(),
                error="No se puede eliminar la rama actual. Cambia a otra rama primero."
            ).dict()

        # Eliminar rama local
        delete_flag = "-D" if forzar else "-d"
        result = GitUtils.run_git_command(
            ["git", "branch", delete_flag, branch_name.strip()],
            cwd=ruta_absoluta, timeout=10
        )

        if result.returncode != 0:
            return BranchDeleteResponse(
                ok=False, success=False, branch=branch_name.strip(),
                stdout=result.stdout.strip(), stderr=result.stderr.strip(),
                error=f"Error al eliminar rama local: {result.stderr.strip()}"
            ).dict()

        deleted_remote = False
        # Eliminar rama remota si se solicita
        if eliminar_remoto:
            remote_result = _run_git_with_auth(
                ["git", "push", remote.strip(), "--delete", branch_name.strip()],
                cwd=ruta_absoluta, token=token, timeout=60
            )
            deleted_remote = remote_result.returncode == 0

        return BranchDeleteResponse(
            ok=True, success=True, branch=branch_name.strip(),
            deleted_remote=deleted_remote,
            stdout=result.stdout.strip(), stderr=None, error=None
        ).dict()

    except Exception as e:
        logger.error(f"Error al eliminar rama: {e}")
        return BranchDeleteResponse(
            ok=False, success=False, branch=branch_name.strip(),
            error=f"Error al eliminar rama: {str(e)}"
        ).dict()


# --- TAGS ---

@_handle_ownership_error
def listar_tags(ruta_repo: str = ".") -> Dict[str, Any]:
    """Lista todos los tags del repositorio con su información."""
    ruta_absoluta = GitUtils.get_absolute_path(ruta_repo)
    is_valid, error_msg = GitUtils.validate_git_repository(ruta_absoluta)
    if not is_valid:
        return TagListResponse(ok=False, tags=[], total=0, error=error_msg).dict()

    try:
        result = GitUtils.run_git_command(
            ["git", "tag", "-l", "--format", "%(refname:short)%09%(objectname:short)%09%(contents:subject)"],
            cwd=ruta_absoluta, timeout=10
        )

        if result.returncode != 0:
            return TagListResponse(
                ok=False, tags=[], total=0,
                error=f"Error al listar tags: {result.stderr.strip()}"
            ).dict()

        tags = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            name = parts[0] if len(parts) > 0 else ""
            hash_val = parts[1] if len(parts) > 1 else ""
            message = parts[2] if len(parts) > 2 else None
            if name:
                tags.append(TagInfo(name=name, hash=hash_val, message=message or None))

        return TagListResponse(ok=True, tags=tags, total=len(tags), error=None).dict()

    except Exception as e:
        logger.error(f"Error al listar tags: {e}")
        return TagListResponse(
            ok=False, tags=[], total=0,
            error=f"Error al listar tags: {str(e)}"
        ).dict()


@_handle_ownership_error
def crear_tag(
    ruta_repo: str = ".",
    nombre: str = "",
    mensaje: str = "",
    commit: str = ""
) -> Dict[str, Any]:
    """Crea un tag en el repositorio. Si se proporciona mensaje, crea un tag anotado."""
    if not nombre.strip():
        raise ValueError("El nombre del tag no puede estar vacío")

    ruta_absoluta = GitUtils.get_absolute_path(ruta_repo)
    is_valid, error_msg = GitUtils.validate_git_repository(ruta_absoluta)
    if not is_valid:
        raise ValueError(error_msg)

    try:
        cmd = ["git", "tag"]
        if mensaje.strip():
            cmd.extend(["-a", nombre.strip(), "-m", mensaje.strip()])
        else:
            cmd.append(nombre.strip())
        if commit.strip():
            cmd.append(commit.strip())

        result = GitUtils.run_git_command(cmd, cwd=ruta_absoluta, timeout=10)

        if result.returncode != 0:
            return TagOperationResponse(
                ok=False, success=False, tag_name=nombre.strip(),
                stdout=result.stdout.strip(), stderr=result.stderr.strip(),
                error=f"Error al crear tag: {result.stderr.strip()}"
            ).dict()

        # Obtener hash del tag
        hash_result = GitUtils.run_git_command(
            ["git", "rev-parse", nombre.strip()],
            cwd=ruta_absoluta, timeout=5
        )
        tag_hash = hash_result.stdout.strip()[:7] if hash_result.returncode == 0 else None

        return TagOperationResponse(
            ok=True, success=True, tag_name=nombre.strip(),
            commit_hash=tag_hash, stdout=result.stdout.strip(),
            stderr=None, error=None
        ).dict()

    except Exception as e:
        logger.error(f"Error al crear tag: {e}")
        return TagOperationResponse(
            ok=False, success=False, tag_name=nombre.strip(),
            error=f"Error al crear tag: {str(e)}"
        ).dict()


@_handle_ownership_error
def eliminar_tag(
    ruta_repo: str = ".",
    nombre: str = "",
    eliminar_remoto: bool = False,
    remote: str = "origin",
    token: str = ""
) -> Dict[str, Any]:
    """Elimina un tag local y opcionalmente del remoto."""
    if not nombre.strip():
        raise ValueError("El nombre del tag no puede estar vacío")

    ruta_absoluta = GitUtils.get_absolute_path(ruta_repo)
    is_valid, error_msg = GitUtils.validate_git_repository(ruta_absoluta)
    if not is_valid:
        raise ValueError(error_msg)

    try:
        result = GitUtils.run_git_command(
            ["git", "tag", "-d", nombre.strip()],
            cwd=ruta_absoluta, timeout=10
        )

        if result.returncode != 0:
            return TagOperationResponse(
                ok=False, success=False, tag_name=nombre.strip(),
                stdout=result.stdout.strip(), stderr=result.stderr.strip(),
                error=f"Error al eliminar tag: {result.stderr.strip()}"
            ).dict()

        # Eliminar del remoto si se solicita
        if eliminar_remoto:
            _run_git_with_auth(
                ["git", "push", remote.strip(), f":refs/tags/{nombre.strip()}"],
                cwd=ruta_absoluta, token=token, timeout=60
            )

        return TagOperationResponse(
            ok=True, success=True, tag_name=nombre.strip(),
            stdout=result.stdout.strip(), stderr=None, error=None
        ).dict()

    except Exception as e:
        logger.error(f"Error al eliminar tag: {e}")
        return TagOperationResponse(
            ok=False, success=False, tag_name=nombre.strip(),
            error=f"Error al eliminar tag: {str(e)}"
        ).dict()


# --- STASH ---

@_handle_ownership_error
def listar_stashes(ruta_repo: str = ".") -> Dict[str, Any]:
    """Lista todos los stashes del repositorio."""
    ruta_absoluta = GitUtils.get_absolute_path(ruta_repo)
    is_valid, error_msg = GitUtils.validate_git_repository(ruta_absoluta)
    if not is_valid:
        return StashListResponse(ok=False, stashes=[], total=0, error=error_msg).dict()

    try:
        result = GitUtils.run_git_command(
            ["git", "stash", "list"],
            cwd=ruta_absoluta, timeout=10
        )

        if result.returncode != 0:
            return StashListResponse(
                ok=False, stashes=[], total=0,
                error=f"Error al listar stashes: {result.stderr.strip()}"
            ).dict()

        stashes = []
        for i, line in enumerate(result.stdout.splitlines()):
            if not line.strip():
                continue
            ref = f"stash@{{{i}}}"
            message = line.strip()
            stashes.append(StashInfo(index=i, reference=ref, message=message))

        return StashListResponse(
            ok=True, stashes=stashes, total=len(stashes), error=None
        ).dict()

    except Exception as e:
        logger.error(f"Error al listar stashes: {e}")
        return StashListResponse(
            ok=False, stashes=[], total=0,
            error=f"Error al listar stashes: {str(e)}"
        ).dict()


@_handle_ownership_error
def guardar_stash(
    ruta_repo: str = ".",
    mensaje: str = "",
    incluir_untracked: bool = False
) -> Dict[str, Any]:
    """Guarda los cambios actuales en un stash."""
    ruta_absoluta = GitUtils.get_absolute_path(ruta_repo)
    is_valid, error_msg = GitUtils.validate_git_repository(ruta_absoluta)
    if not is_valid:
        raise ValueError(error_msg)

    try:
        cmd = ["git", "stash", "push"]
        if incluir_untracked:
            cmd.append("--include-untracked")
        if mensaje.strip():
            cmd.extend(["-m", mensaje.strip()])

        result = GitUtils.run_git_command(cmd, cwd=ruta_absoluta, timeout=30)

        if result.returncode != 0:
            return StashOperationResponse(
                ok=False, success=False, operation="save",
                stdout=result.stdout.strip(), stderr=result.stderr.strip(),
                error=f"Error al guardar stash: {result.stderr.strip()}"
            ).dict()

        # Verificar si realmente se guardó algo
        no_changes = "no local changes" in result.stdout.lower() or "no hay cambios" in result.stdout.lower()

        return StashOperationResponse(
            ok=not no_changes, success=not no_changes, operation="save",
            message=result.stdout.strip(),
            stdout=result.stdout.strip(), stderr=None,
            error="No hay cambios para guardar en stash" if no_changes else None
        ).dict()

    except Exception as e:
        logger.error(f"Error al guardar stash: {e}")
        return StashOperationResponse(
            ok=False, success=False, operation="save",
            error=f"Error al guardar stash: {str(e)}"
        ).dict()


@_handle_ownership_error
def aplicar_stash(ruta_repo: str = ".", indice: int = 0) -> Dict[str, Any]:
    """Aplica un stash sin eliminarlo de la lista."""
    ruta_absoluta = GitUtils.get_absolute_path(ruta_repo)
    is_valid, error_msg = GitUtils.validate_git_repository(ruta_absoluta)
    if not is_valid:
        raise ValueError(error_msg)

    try:
        result = GitUtils.run_git_command(
            ["git", "stash", "apply", f"stash@{{{indice}}}"],
            cwd=ruta_absoluta, timeout=30
        )

        if result.returncode != 0:
            return StashOperationResponse(
                ok=False, success=False, operation="apply",
                stdout=result.stdout.strip(), stderr=result.stderr.strip(),
                error=f"Error al aplicar stash: {result.stderr.strip()}"
            ).dict()

        return StashOperationResponse(
            ok=True, success=True, operation="apply",
            message=f"Stash @{{{indice}}} aplicado correctamente",
            stdout=result.stdout.strip(), stderr=None, error=None
        ).dict()

    except Exception as e:
        logger.error(f"Error al aplicar stash: {e}")
        return StashOperationResponse(
            ok=False, success=False, operation="apply",
            error=f"Error al aplicar stash: {str(e)}"
        ).dict()


@_handle_ownership_error
def sacar_stash(ruta_repo: str = ".", indice: int = 0) -> Dict[str, Any]:
    """Aplica un stash y lo elimina de la lista (pop)."""
    ruta_absoluta = GitUtils.get_absolute_path(ruta_repo)
    is_valid, error_msg = GitUtils.validate_git_repository(ruta_absoluta)
    if not is_valid:
        raise ValueError(error_msg)

    try:
        result = GitUtils.run_git_command(
            ["git", "stash", "pop", f"stash@{{{indice}}}"],
            cwd=ruta_absoluta, timeout=30
        )

        if result.returncode != 0:
            return StashOperationResponse(
                ok=False, success=False, operation="pop",
                stdout=result.stdout.strip(), stderr=result.stderr.strip(),
                error=f"Error al sacar stash: {result.stderr.strip()}"
            ).dict()

        return StashOperationResponse(
            ok=True, success=True, operation="pop",
            message=f"Stash @{{{indice}}} aplicado y eliminado correctamente",
            stdout=result.stdout.strip(), stderr=None, error=None
        ).dict()

    except Exception as e:
        logger.error(f"Error al sacar stash: {e}")
        return StashOperationResponse(
            ok=False, success=False, operation="pop",
            error=f"Error al sacar stash: {str(e)}"
        ).dict()


@_handle_ownership_error
def eliminar_stash(ruta_repo: str = ".", indice: int = 0) -> Dict[str, Any]:
    """Elimina un stash de la lista sin aplicarlo."""
    ruta_absoluta = GitUtils.get_absolute_path(ruta_repo)
    is_valid, error_msg = GitUtils.validate_git_repository(ruta_absoluta)
    if not is_valid:
        raise ValueError(error_msg)

    try:
        result = GitUtils.run_git_command(
            ["git", "stash", "drop", f"stash@{{{indice}}}"],
            cwd=ruta_absoluta, timeout=10
        )

        if result.returncode != 0:
            return StashOperationResponse(
                ok=False, success=False, operation="drop",
                stdout=result.stdout.strip(), stderr=result.stderr.strip(),
                error=f"Error al eliminar stash: {result.stderr.strip()}"
            ).dict()

        return StashOperationResponse(
            ok=True, success=True, operation="drop",
            message=f"Stash @{{{indice}}} eliminado correctamente",
            stdout=result.stdout.strip(), stderr=None, error=None
        ).dict()

    except Exception as e:
        logger.error(f"Error al eliminar stash: {e}")
        return StashOperationResponse(
            ok=False, success=False, operation="drop",
            error=f"Error al eliminar stash: {str(e)}"
        ).dict()


def git_status_directorio(
    ruta_repo: str,
    subdirectorio: Optional[str] = None,
    commit1: Optional[str] = None,
    commit2: Optional[str] = None
) -> Dict[str, Any]:
    """
    Devuelve el estado git de cada archivo en un directorio:
    'nuevo', 'modificado', 'eliminado' o 'sin_cambios'.

    Args:
        ruta_repo: Ruta al repositorio Git.
        subdirectorio: Subcarpeta relativa (None = raíz del repo).
        commit1: Primer commit para comparación (opcional).
        commit2: Segundo commit para comparación (opcional).

    Returns:
        Dict con ok, comparacion y archivos (dict ruta_relativa → estado).
    """
    try:
        ruta_absoluta = GitUtils.get_absolute_path(ruta_repo)

        is_valid, error_msg = GitUtils.validate_git_repository(ruta_absoluta)
        if not is_valid:
            return {"ok": False, "error": error_msg}

        path_filter = [subdirectorio.replace("\\", "/")] if subdirectorio else ["."]

        archivos: Dict[str, str] = {}

        # --- mapa de letras git → estado legible ---
        STATUS_MAP = {
            "A": "nuevo",
            "M": "modificado",
            "D": "eliminado",
            "R": "renombrado",
            "C": "copiado",
            "T": "modificado",
            "U": "modificado",
        }

        if commit1 is None and commit2 is None:
            comparacion = "Working directory vs HEAD"

            # Archivos modificados / eliminados respecto a HEAD
            result = GitUtils.run_git_command(
                ["git", "diff", "--name-status", "HEAD", "--"] + path_filter,
                cwd=ruta_absoluta, timeout=30
            )
            for line in result.stdout.strip().splitlines():
                if not line.strip():
                    continue
                parts = line.split("\t", 1)
                estado_letra = parts[0][0]
                archivo = parts[1] if len(parts) > 1 else ""
                archivos[archivo] = STATUS_MAP.get(estado_letra, "modificado")

            # Archivos nuevos (untracked)
            result_untracked = GitUtils.run_git_command(
                ["git", "ls-files", "--others", "--exclude-standard", "--"] + path_filter,
                cwd=ruta_absoluta, timeout=30
            )
            for line in result_untracked.stdout.strip().splitlines():
                if line.strip():
                    archivos[line.strip()] = "nuevo"

        elif commit1 is not None and commit2 is None:
            comparacion = f"Working directory vs {commit1}"
            result = GitUtils.run_git_command(
                ["git", "diff", "--name-status", commit1, "--"] + path_filter,
                cwd=ruta_absoluta, timeout=30
            )
            for line in result.stdout.strip().splitlines():
                if not line.strip():
                    continue
                parts = line.split("\t", 1)
                estado_letra = parts[0][0]
                archivo = parts[1] if len(parts) > 1 else ""
                archivos[archivo] = STATUS_MAP.get(estado_letra, "modificado")

        else:
            comparacion = f"{commit1} vs {commit2}"
            result = GitUtils.run_git_command(
                ["git", "diff", "--name-status", commit1, commit2, "--"] + path_filter,
                cwd=ruta_absoluta, timeout=30
            )
            for line in result.stdout.strip().splitlines():
                if not line.strip():
                    continue
                parts = line.split("\t", 1)
                estado_letra = parts[0][0]
                archivo = parts[1] if len(parts) > 1 else ""
                archivos[archivo] = STATUS_MAP.get(estado_letra, "modificado")

        return {
            "ok": True,
            "comparacion": comparacion,
            "archivos": archivos
        }

    except Exception as e:
        logger.error(f"Error en git_status_directorio: {e}")
        return {"ok": False, "error": f"Error al obtener estado del directorio: {str(e)}"}


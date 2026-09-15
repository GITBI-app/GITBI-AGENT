"""
Modelos Pydantic para las operaciones Git.
Definen la estructura de las respuestas de la API Git.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# Modelos de respuesta base
class BaseGitResponse(BaseModel):
    """Respuesta base para operaciones Git."""
    ok: bool = Field(..., description="Indica si la operación fue exitosa")
    error: Optional[str] = Field(None, description="Mensaje de error si la operación falló")


class GitInstallationResponse(BaseGitResponse):
    """Respuesta para verificar instalación de Git."""
    installed: bool = Field(..., description="Indica si Git está instalado")
    version: Optional[str] = Field(None, description="Versión de Git instalada")


class RepositoryStatusResponse(BaseGitResponse):
    """Respuesta para verificar estado del repositorio."""
    initialized: bool = Field(..., description="Indica si el directorio es un repositorio Git")
    path: Optional[str] = Field(None, description="Ruta absoluta del repositorio")
    bare: bool = Field(False, description="Indica si es un repositorio bare")
    branch: Optional[str] = Field(None, description="Rama actual")
    detached: bool = Field(False, description="Indica si está en detached HEAD")
    short_hash: Optional[str] = Field(None, description="Hash corto del commit actual")
    commit_date: Optional[str] = Field(None, description="Fecha del último commit")
    commit_message: Optional[str] = Field(None, description="Mensaje del último commit")
    dirty: bool = Field(False, description="Indica si hay cambios sin confirmar")


class BranchesResponse(BaseGitResponse):
    """Respuesta para listar ramas."""
    branches: List[str] = Field(default_factory=list, description="Lista de ramas")
    current: Optional[str] = Field(None, description="Rama actual")


class CommitInfo(BaseModel):
    """Información de un commit."""
    hash_corto: str = Field(..., description="Hash corto del commit")
    hash_completo: str = Field(..., description="Hash completo del commit")
    fecha: str = Field(..., description="Fecha del commit en formato ISO 8601")
    mensaje: str = Field(..., description="Mensaje del commit")
    autor: str = Field(..., description="Nombre del autor")
    email: str = Field(..., description="Email del autor")


class CommitListResponse(BaseGitResponse):
    """Respuesta para listar commits."""
    rama: str = Field(..., description="Rama consultada")
    commits: List[CommitInfo] = Field(default_factory=list, description="Lista de commits")
    total: int = Field(0, description="Total de commits devueltos")


class CommitOperationResponse(BaseGitResponse):
    """Respuesta para operaciones de commit."""
    success: bool = Field(..., description="Indica si el commit fue exitoso")
    commit_hash: Optional[str] = Field(None, description="Hash completo del commit")
    short_hash: Optional[str] = Field(None, description="Hash corto del commit")
    message: Optional[str] = Field(None, description="Mensaje del commit")
    author: Optional[str] = Field(None, description="Autor del commit")
    date: Optional[str] = Field(None, description="Fecha del commit")
    files_committed: List[str] = Field(default_factory=list, description="Archivos incluidos en el commit")


class CheckoutResponse(BaseGitResponse):
    """Respuesta para operaciones de checkout."""
    success: bool = Field(..., description="Indica si el checkout fue exitoso")
    branch: Optional[str] = Field(None, description="Rama actual después del checkout")
    commit_hash: Optional[str] = Field(None, description="Hash del commit actual")
    short_hash: Optional[str] = Field(None, description="Hash corto del commit actual")
    message: Optional[str] = Field(None, description="Mensaje del commit")
    author: Optional[str] = Field(None, description="Autor del commit")
    date: Optional[str] = Field(None, description="Fecha del commit")
    detached_head: bool = Field(False, description="Indica si está en detached HEAD")
    previous_state: Dict[str, Any] = Field(default_factory=dict, description="Estado anterior antes del checkout")


class BranchCreateResponse(BaseGitResponse):
    """Respuesta para crear una rama."""
    success: bool = Field(..., description="Indica si la rama fue creada exitosamente")
    branch: Optional[str] = Field(None, description="Nombre de la rama creada")
    commit_hash: Optional[str] = Field(None, description="Hash del commit base")
    short_hash: Optional[str] = Field(None, description="Hash corto del commit base")
    message: Optional[str] = Field(None, description="Mensaje del commit base")
    author: Optional[str] = Field(None, description="Autor del commit base")
    date: Optional[str] = Field(None, description="Fecha del commit base")
    checked_out: bool = Field(False, description="Indica si se hizo checkout automático")


class InitRepositoryResponse(BaseGitResponse):
    """Respuesta para inicializar repositorio."""
    commit: Optional[str] = Field(None, description="Hash del commit inicial")
    mensaje: Optional[str] = Field(None, description="Mensaje del commit inicial")
    path: Optional[str] = Field(None, description="Ruta del repositorio")


class ResetResponse(BaseGitResponse):
    """Respuesta para reset hard."""
    success: bool = Field(..., description="Indica si el reset fue exitoso")
    stdout: str = Field("", description="Salida estándar del comando")
    stderr: Optional[str] = Field(None, description="Salida de error del comando")


class GitDiffResponse(BaseGitResponse):
    """Respuesta para operaciones de git diff."""
    ruta_repo: Optional[str] = Field(None, description="Ruta del repositorio")
    ruta_archivo: Optional[str] = Field(None, description="Ruta del archivo analizado")
    comparacion: Optional[str] = Field(None, description="Descripción de la comparación realizada")
    diff_content: Optional[str] = Field(None, description="Contenido del diff")
    hay_cambios: bool = Field(False, description="Indica si hay diferencias")
    es_archivo_nuevo: bool = Field(False, description="Indica si el archivo es nuevo (no existía en la comparación base)")
    lineas_agregadas: int = Field(0, description="Número de líneas agregadas")
    lineas_eliminadas: int = Field(0, description="Número de líneas eliminadas")
    commit1_info: Optional[Dict[str, str]] = Field(None, description="Información del primer commit")
    commit2_info: Optional[Dict[str, str]] = Field(None, description="Información del segundo commit")


class MergeResponse(BaseGitResponse):
    """Respuesta para operaciones de merge."""
    success: bool = Field(..., description="Indica si el merge fue exitoso")
    current_branch: Optional[str] = Field(None, description="Rama actual donde se intentó el merge")
    merged_ref: Optional[str] = Field(None, description="Rama o referencia integrada")
    has_conflicts: bool = Field(False, description="Indica si el merge quedó con conflictos")
    conflicting_files: List[str] = Field(default_factory=list, description="Archivos en conflicto")
    stdout: str = Field("", description="Salida estándar del comando merge")
    stderr: Optional[str] = Field(None, description="Salida de error del comando merge")


class MergeConflictsStatusResponse(BaseGitResponse):
    """Respuesta para consultar estado de conflictos de merge."""
    merge_in_progress: bool = Field(False, description="Indica si hay un merge en curso")
    conflicting_files: List[str] = Field(default_factory=list, description="Archivos actualmente en conflicto")


class ResolveConflictResponse(BaseGitResponse):
    """Respuesta para resolución de conflictos por archivo."""
    success: bool = Field(..., description="Indica si el archivo se resolvió correctamente")
    file_path: Optional[str] = Field(None, description="Ruta del archivo resuelto")
    strategy: Optional[str] = Field(None, description="Estrategia aplicada: ours/theirs/manual")
    remaining_conflicts: List[str] = Field(default_factory=list, description="Archivos que siguen en conflicto")


class AbortMergeResponse(BaseGitResponse):
    """Respuesta para abortar merge en curso."""
    success: bool = Field(..., description="Indica si el aborto de merge fue exitoso")
    stdout: str = Field("", description="Salida estándar del comando")
    stderr: Optional[str] = Field(None, description="Salida de error del comando")


class MergeStatusResponse(BaseGitResponse):
    """Respuesta para estado detallado de merge."""
    merge_in_progress: bool = Field(False, description="Indica si hay merge en progreso")
    current_branch: Optional[str] = Field(None, description="Rama actual")
    conflicting_files: List[str] = Field(default_factory=list, description="Archivos actualmente en conflicto")
    can_finalize: bool = Field(False, description="Indica si el merge puede finalizarse")
    can_abort: bool = Field(False, description="Indica si el merge puede abortarse")
    last_operation: Optional[str] = Field(None, description="Última operación de merge registrada")
    last_stdout: Optional[str] = Field(None, description="Última salida estándar registrada")
    last_stderr: Optional[str] = Field(None, description="Última salida de error registrada")


# Modelos de entrada/request
class CommitRequest(BaseModel):
    """Petición para hacer commit."""
    ruta_repo: str = Field(".", description="Ruta del repositorio")
    mensaje: str = Field(..., description="Mensaje del commit")


class CheckoutCommitRequest(BaseModel):
    """Petición para checkout a commit."""
    ruta_repo: str = Field(".", description="Ruta del repositorio")
    commit_hash: str = Field(..., description="Hash del commit")
    forzar: bool = Field(False, description="Forzar checkout descartando cambios")


class CheckoutBranchRequest(BaseModel):
    """Petición para checkout a rama."""
    ruta_repo: str = Field(".", description="Ruta del repositorio")
    branch_name: str = Field(..., description="Nombre de la rama")
    forzar: bool = Field(False, description="Forzar checkout descartando cambios")


class CreateBranchRequest(BaseModel):
    """Petición para crear rama."""
    ruta_repo: str = Field(".", description="Ruta del repositorio")
    branch_name: str = Field(..., description="Nombre de la nueva rama")
    desde_commit: str = Field("", description="Hash del commit base")
    checkout: bool = Field(True, description="Hacer checkout automático")


class InitRepositoryRequest(BaseModel):
    """Petición para inicializar repositorio."""
    ruta_repo: str = Field(".", description="Ruta del repositorio")
    mensaje: str = Field("Initial commit", description="Mensaje del commit inicial")


class ResetHardHeadRequest(BaseModel):
    """Petición para reset hard HEAD."""
    ruta_repo: str = Field(".", description="Ruta del repositorio")


class GitDiffRequest(BaseModel):
    """Petición para git diff de archivo."""
    ruta_repo: str = Field(".", description="Ruta del repositorio")
    ruta_archivo: str = Field(..., description="Ruta del archivo a comparar")
    commit1: Optional[str] = Field(None, description="Primer commit (opcional)")
    commit2: Optional[str] = Field(None, description="Segundo commit (opcional)")


class MergeRequest(BaseModel):
    """Petición para ejecutar merge de una rama/referencia sobre la rama actual."""
    ruta_repo: str = Field(".", description="Ruta del repositorio")
    source_ref: str = Field(..., description="Rama o referencia a integrar")


class ResolveConflictRequest(BaseModel):
    """Petición para resolver un archivo en conflicto."""
    ruta_repo: str = Field(".", description="Ruta del repositorio")
    ruta_archivo: str = Field(..., description="Ruta del archivo en conflicto")
    estrategia: str = Field(..., description="Estrategia: ours, theirs o manual")
    contenido_resuelto: Optional[str] = Field(None, description="Contenido final cuando estrategia=manual")


class FinalizeMergeRequest(BaseModel):
    """Petición para finalizar merge en curso con commit."""
    ruta_repo: str = Field(".", description="Ruta del repositorio")
    mensaje: str = Field("Merge commit", description="Mensaje del commit de merge")


class AbortMergeRequest(BaseModel):
    """Petición para abortar un merge en curso."""
    ruta_repo: str = Field(".", description="Ruta del repositorio")


# ===================================================================
# MODELOS PARA GIT DISTRIBUIDO (remote, clone, push, pull, fetch, etc.)
# ===================================================================

# --- Remote ---

class RemoteInfo(BaseModel):
    """Información de un remote."""
    name: str = Field(..., description="Nombre del remote")
    url_fetch: str = Field("", description="URL de fetch")
    url_push: str = Field("", description="URL de push")


class RemoteListResponse(BaseGitResponse):
    """Respuesta para listar remotes."""
    remotes: List[RemoteInfo] = Field(default_factory=list, description="Lista de remotes configurados")


class RemoteOperationResponse(BaseGitResponse):
    """Respuesta para operaciones de remote (add/remove/rename/set-url)."""
    success: bool = Field(..., description="Indica si la operación fue exitosa")
    remote_name: Optional[str] = Field(None, description="Nombre del remote afectado")
    url: Optional[str] = Field(None, description="URL del remote (si aplica)")
    stdout: str = Field("", description="Salida estándar del comando")
    stderr: Optional[str] = Field(None, description="Salida de error del comando")


# --- Clone ---

class CloneResponse(BaseGitResponse):
    """Respuesta para clonar un repositorio."""
    success: bool = Field(..., description="Indica si la clonación fue exitosa")
    path: Optional[str] = Field(None, description="Ruta donde se clonó el repositorio")
    remote_url: Optional[str] = Field(None, description="URL del repositorio remoto")
    branch: Optional[str] = Field(None, description="Rama principal del repositorio clonado")
    stdout: str = Field("", description="Salida estándar del comando")
    stderr: Optional[str] = Field(None, description="Salida de error del comando")


# --- Push ---

class PushResponse(BaseGitResponse):
    """Respuesta para push a remoto."""
    success: bool = Field(..., description="Indica si el push fue exitoso")
    remote: Optional[str] = Field(None, description="Remote al que se hizo push")
    branch: Optional[str] = Field(None, description="Rama que se envió")
    set_upstream: bool = Field(False, description="Indica si se configuró upstream")
    stdout: str = Field("", description="Salida estándar del comando")
    stderr: Optional[str] = Field(None, description="Salida de error del comando")


# --- Pull ---

class PullResponse(BaseGitResponse):
    """Respuesta para pull desde remoto."""
    success: bool = Field(..., description="Indica si el pull fue exitoso")
    remote: Optional[str] = Field(None, description="Remote desde el que se hizo pull")
    branch: Optional[str] = Field(None, description="Rama que se recibió")
    has_conflicts: bool = Field(False, description="Indica si hay conflictos después del pull")
    conflicting_files: List[str] = Field(default_factory=list, description="Archivos en conflicto")
    stdout: str = Field("", description="Salida estándar del comando")
    stderr: Optional[str] = Field(None, description="Salida de error del comando")


# --- Fetch ---

class FetchResponse(BaseGitResponse):
    """Respuesta para fetch desde remoto."""
    success: bool = Field(..., description="Indica si el fetch fue exitoso")
    remote: Optional[str] = Field(None, description="Remote desde el que se hizo fetch")
    stdout: str = Field("", description="Salida estándar del comando")
    stderr: Optional[str] = Field(None, description="Salida de error del comando")


# --- Remote Branches ---

class RemoteBranchesResponse(BaseGitResponse):
    """Respuesta para listar ramas remotas."""
    branches: List[str] = Field(default_factory=list, description="Lista de ramas remotas")
    remote: Optional[str] = Field(None, description="Nombre del remote")


# --- Branch Delete ---

class BranchDeleteResponse(BaseGitResponse):
    """Respuesta para eliminar una rama."""
    success: bool = Field(..., description="Indica si la eliminación fue exitosa")
    branch: Optional[str] = Field(None, description="Nombre de la rama eliminada")
    deleted_remote: bool = Field(False, description="Si también se eliminó del remoto")
    stdout: str = Field("", description="Salida estándar del comando")
    stderr: Optional[str] = Field(None, description="Salida de error del comando")


# --- Tag ---

class TagInfo(BaseModel):
    """Información de un tag."""
    name: str = Field(..., description="Nombre del tag")
    hash: str = Field("", description="Hash del commit al que apunta")
    message: Optional[str] = Field(None, description="Mensaje del tag (si es anotado)")


class TagListResponse(BaseGitResponse):
    """Respuesta para listar tags."""
    tags: List[TagInfo] = Field(default_factory=list, description="Lista de tags")
    total: int = Field(0, description="Total de tags")


class TagOperationResponse(BaseGitResponse):
    """Respuesta para operaciones de tag (create/delete)."""
    success: bool = Field(..., description="Indica si la operación fue exitosa")
    tag_name: Optional[str] = Field(None, description="Nombre del tag afectado")
    commit_hash: Optional[str] = Field(None, description="Hash del commit asociado")
    stdout: str = Field("", description="Salida estándar del comando")
    stderr: Optional[str] = Field(None, description="Salida de error del comando")


# --- Stash ---

class StashInfo(BaseModel):
    """Información de un stash."""
    index: int = Field(..., description="Índice del stash")
    reference: str = Field(..., description="Referencia del stash (ej: stash@{0})")
    message: str = Field("", description="Mensaje del stash")


class StashListResponse(BaseGitResponse):
    """Respuesta para listar stashes."""
    stashes: List[StashInfo] = Field(default_factory=list, description="Lista de stashes")
    total: int = Field(0, description="Total de stashes")


class StashOperationResponse(BaseGitResponse):
    """Respuesta para operaciones de stash (save/apply/pop/drop)."""
    success: bool = Field(..., description="Indica si la operación fue exitosa")
    operation: Optional[str] = Field(None, description="Operación realizada")
    message: Optional[str] = Field(None, description="Mensaje descriptivo")
    stdout: str = Field("", description="Salida estándar del comando")
    stderr: Optional[str] = Field(None, description="Salida de error del comando")


# ===== REQUEST MODELS PARA GIT DISTRIBUIDO =====

# --- Remote Requests ---

class RemoteAddRequest(BaseModel):
    """Petición para agregar un remote."""
    ruta_repo: str = Field(".", description="Ruta del repositorio")
    nombre: str = Field(..., description="Nombre del remote (ej: origin)")
    url: str = Field(..., description="URL del remote")


class RemoteRemoveRequest(BaseModel):
    """Petición para eliminar un remote."""
    ruta_repo: str = Field(".", description="Ruta del repositorio")
    nombre: str = Field(..., description="Nombre del remote a eliminar")


class RemoteRenameRequest(BaseModel):
    """Petición para renombrar un remote."""
    ruta_repo: str = Field(".", description="Ruta del repositorio")
    nombre_actual: str = Field(..., description="Nombre actual del remote")
    nombre_nuevo: str = Field(..., description="Nuevo nombre del remote")


class RemoteSetUrlRequest(BaseModel):
    """Petición para cambiar la URL de un remote."""
    ruta_repo: str = Field(".", description="Ruta del repositorio")
    nombre: str = Field(..., description="Nombre del remote")
    url: str = Field(..., description="Nueva URL del remote")


# --- Clone Request ---

class CloneRequest(BaseModel):
    """Petición para clonar un repositorio."""
    url: str = Field(..., description="URL del repositorio a clonar")
    ruta_destino: str = Field(..., description="Ruta donde clonar el repositorio")
    rama: str = Field("", description="Rama específica a clonar (vacío para default)")
    profundidad: int = Field(0, description="Profundidad del clon (0 para completo)", ge=0)
    token: str = Field("", description="Token de autenticación (para repositorios privados HTTPS)")


# --- Push Request ---

class PushRequest(BaseModel):
    """Petición para push a remoto."""
    ruta_repo: str = Field(".", description="Ruta del repositorio")
    remote: str = Field("origin", description="Nombre del remote")
    rama: str = Field("", description="Rama a enviar (vacío para rama actual)")
    forzar: bool = Field(False, description="Forzar push (--force)")
    set_upstream: bool = Field(False, description="Configurar upstream (-u)")
    tags: bool = Field(False, description="Enviar tags (--tags)")
    token: str = Field("", description="Token de autenticación (para HTTPS)")


# --- Pull Request ---

class PullRequest(BaseModel):
    """Petición para pull desde remoto."""
    ruta_repo: str = Field(".", description="Ruta del repositorio")
    remote: str = Field("origin", description="Nombre del remote")
    rama: str = Field("", description="Rama desde la cual hacer pull (vacío para actual)")
    rebase: bool = Field(False, description="Usar rebase en lugar de merge")
    token: str = Field("", description="Token de autenticación (para HTTPS)")


# --- Fetch Request ---

class FetchRequest(BaseModel):
    """Petición para fetch desde remoto."""
    ruta_repo: str = Field(".", description="Ruta del repositorio")
    remote: str = Field("", description="Nombre del remote (vacío para todos)")
    prune: bool = Field(False, description="Eliminar ramas remotas borradas (--prune)")
    tags: bool = Field(True, description="Traer tags")
    token: str = Field("", description="Token de autenticación (para HTTPS)")


# --- Branch Delete Request ---

class BranchDeleteRequest(BaseModel):
    """Petición para eliminar una rama."""
    ruta_repo: str = Field(".", description="Ruta del repositorio")
    branch_name: str = Field(..., description="Nombre de la rama a eliminar")
    forzar: bool = Field(False, description="Forzar eliminación (-D en vez de -d)")
    eliminar_remoto: bool = Field(False, description="También eliminar del remoto")
    remote: str = Field("origin", description="Remote del cual eliminar la rama")
    token: str = Field("", description="Token de autenticación (para eliminar remoto HTTPS)")


# --- Tag Requests ---

class TagCreateRequest(BaseModel):
    """Petición para crear un tag."""
    ruta_repo: str = Field(".", description="Ruta del repositorio")
    nombre: str = Field(..., description="Nombre del tag")
    mensaje: str = Field("", description="Mensaje del tag (vacío para tag ligero)")
    commit: str = Field("", description="Hash del commit (vacío para HEAD)")


class TagDeleteRequest(BaseModel):
    """Petición para eliminar un tag."""
    ruta_repo: str = Field(".", description="Ruta del repositorio")
    nombre: str = Field(..., description="Nombre del tag a eliminar")
    eliminar_remoto: bool = Field(False, description="También eliminar del remoto")
    remote: str = Field("origin", description="Remote del cual eliminar el tag")
    token: str = Field("", description="Token de autenticación (para eliminar remoto HTTPS)")


# --- Stash Requests ---

class StashSaveRequest(BaseModel):
    """Petición para guardar un stash."""
    ruta_repo: str = Field(".", description="Ruta del repositorio")
    mensaje: str = Field("", description="Mensaje descriptivo del stash")
    incluir_untracked: bool = Field(False, description="Incluir archivos no rastreados")


class StashApplyRequest(BaseModel):
    """Petición para aplicar un stash."""
    ruta_repo: str = Field(".", description="Ruta del repositorio")
    indice: int = Field(0, description="Índice del stash a aplicar", ge=0)


class StashPopRequest(BaseModel):
    """Petición para sacar (pop) un stash."""
    ruta_repo: str = Field(".", description="Ruta del repositorio")
    indice: int = Field(0, description="Índice del stash a sacar", ge=0)


class StashDropRequest(BaseModel):
    """Petición para eliminar un stash."""
    ruta_repo: str = Field(".", description="Ruta del repositorio")
    indice: int = Field(0, description="Índice del stash a eliminar", ge=0)
"""
Router para operaciones Git.
Refactorizado para usar modelos Pydantic y manejo centralizado de errores.
"""
from fastapi import APIRouter, Query
from typing import Union

from app.services import git_services
from app.models.git_models import (
    CommitRequest,
    CheckoutCommitRequest, 
    CheckoutBranchRequest,
    CreateBranchRequest,
    InitRepositoryRequest,
    ResetHardHeadRequest,
    MergeRequest,
    ResolveConflictRequest,
    FinalizeMergeRequest,
    AbortMergeRequest,
    GitInstallationResponse,
    RepositoryStatusResponse,
    BranchesResponse,
    CommitListResponse,
    MergeConflictsStatusResponse,
    AbortMergeResponse,
    MergeStatusResponse,
    RemoteAddRequest,
    RemoteRemoveRequest,
    RemoteRenameRequest,
    RemoteSetUrlRequest,
    CloneRequest,
    PushRequest,
    PullRequest,
    FetchRequest,
    BranchDeleteRequest,
    TagCreateRequest,
    TagDeleteRequest,
    StashSaveRequest,
    StashApplyRequest,
    StashPopRequest,
    StashDropRequest,
    RemoteListResponse,
    RemoteBranchesResponse,
    TagListResponse,
    StashListResponse
)
from app.core.router_utils import handle_git_exceptions, format_git_response

router = APIRouter()

# Verifica si Git está instalado en el sistema
@router.get("/check-install", response_model=GitInstallationResponse)
@handle_git_exceptions
def get_check_git_install():
    """Verifica si Git está instalado en el sistema."""
    return git_services.verificar_git_instalado()


# Verifica si la ruta es un repositorio git inicializado
@router.get("/check-repo", response_model=RepositoryStatusResponse)
@handle_git_exceptions
def get_check_repo(ruta_repo: str = Query(".", description="Ruta del repositorio Git")):
    """Verifica si la ruta es un repositorio Git inicializado."""
    return git_services.verificar_repo_inicializado(ruta_repo)


# Lista las ramas del repositorio y la rama actual
@router.get("/branches", response_model=BranchesResponse)
@handle_git_exceptions
def get_branches(ruta_repo: str = Query(".", description="Ruta del repositorio Git")):
    """Lista las ramas del repositorio y muestra la rama actual."""
    return git_services.listar_ramas(ruta_repo)


# Realiza un commit en el repositorio
@router.post("/commit")
@handle_git_exceptions
def post_commit(request: CommitRequest):
    """Realiza un commit en el repositorio Git."""
    result = git_services.hacer_commit(request.ruta_repo, request.mensaje)
    return format_git_response(result)


# Cambia el HEAD al commit especificado
@router.post("/checkout-commit")
@handle_git_exceptions
def post_checkout_commit(request: CheckoutCommitRequest):
    """Cambia el HEAD al commit especificado."""
    result = git_services.hacer_checkout_commit(
        request.ruta_repo, 
        request.commit_hash, 
        request.forzar
    )
    return format_git_response(result)


# Cambia el HEAD a la rama especificada
@router.post("/checkout-branch")
@handle_git_exceptions
def post_checkout_branch(request: CheckoutBranchRequest):
    """Cambia el HEAD a la rama especificada."""
    result = git_services.hacer_checkout_rama(
        request.ruta_repo, 
        request.branch_name, 
        request.forzar
    )
    return format_git_response(result)


# Crea una nueva rama en el repositorio
@router.post("/create-branch")
@handle_git_exceptions
def post_create_branch(request: CreateBranchRequest):
    """Crea una nueva rama en el repositorio Git."""
    result = git_services.crear_rama(
        request.ruta_repo,
        request.branch_name, 
        request.desde_commit,
        request.checkout
    )
    return format_git_response(result)


# Inicializa un repositorio git y realiza el commit inicial
@router.post("/init")
@handle_git_exceptions
def post_init_git(request: InitRepositoryRequest):
    """Inicializa un repositorio Git y realiza el commit inicial."""
    result = git_services.inicializar_git(request.ruta_repo, request.mensaje)
    return format_git_response(result)


# Resetea el repositorio al último commit (HEAD) descartando cambios locales
@router.post("/reset-hard-head")
@handle_git_exceptions
def post_reset_hard_head(request: ResetHardHeadRequest):
    """Resetea el repositorio al último commit (HEAD) descartando cambios locales."""
    result = git_services.git_reset_hard_head(request.ruta_repo)
    return format_git_response(result)


# Lista los commits de una rama específica con hash corto, fecha y mensaje
@router.get("/commits", response_model=CommitListResponse)
@handle_git_exceptions
def get_commits(
    ruta_repo: str = Query(".", description="Ruta del repositorio Git"),
    rama: str = Query("", description="Nombre de la rama (vacío para HEAD)"),
    max_commits: int = Query(100, description="Número máximo de commits", ge=1, le=1000)
):
    """Lista los commits de una rama específica."""
    return git_services.listar_commits_rama(ruta_repo, rama, max_commits)


@router.post("/merge")
@handle_git_exceptions
def post_merge_branch(request: MergeRequest):
    """Ejecuta merge de una rama/referencia sobre la rama actual."""
    result = git_services.hacer_merge_rama(request.ruta_repo, request.source_ref)
    return format_git_response(result)


@router.get("/merge/conflicts", response_model=MergeConflictsStatusResponse)
@handle_git_exceptions
def get_merge_conflicts(ruta_repo: str = Query(".", description="Ruta del repositorio Git")):
    """Obtiene el estado actual de conflictos de merge."""
    return git_services.obtener_conflictos_merge(ruta_repo)


@router.get("/merge/status", response_model=MergeStatusResponse)
@handle_git_exceptions
def get_merge_status(ruta_repo: str = Query(".", description="Ruta del repositorio Git")):
    """Obtiene estado detallado del merge actual."""
    return git_services.obtener_estado_merge_detallado(ruta_repo)


@router.post("/merge/resolve")
@handle_git_exceptions
def post_resolve_conflict(request: ResolveConflictRequest):
    """Resuelve un archivo en conflicto (ours/theirs/manual)."""
    result = git_services.resolver_conflicto_archivo(
        request.ruta_repo,
        request.ruta_archivo,
        request.estrategia,
        request.contenido_resuelto
    )
    return format_git_response(result)


@router.post("/merge/finalize")
@handle_git_exceptions
def post_finalize_merge(request: FinalizeMergeRequest):
    """Finaliza un merge en curso creando el commit de merge."""
    result = git_services.finalizar_merge(request.ruta_repo, request.mensaje)
    return format_git_response(result)


@router.post("/merge/abort", response_model=AbortMergeResponse)
@handle_git_exceptions
def post_abort_merge(request: AbortMergeRequest):
    """Aborta un merge en curso."""
    return git_services.abortar_merge(request.ruta_repo)


# ===================================================================
# ENDPOINTS PARA GIT DISTRIBUIDO (remote, clone, push, pull, fetch, etc.)
# ===================================================================

# --- REMOTES ---

@router.get("/remotes", response_model=RemoteListResponse)
@handle_git_exceptions
def get_remotes(ruta_repo: str = Query(".", description="Ruta del repositorio Git")):
    """Lista todos los remotes configurados en el repositorio."""
    return git_services.listar_remotos(ruta_repo)


@router.post("/remote/add")
@handle_git_exceptions
def post_remote_add(request: RemoteAddRequest):
    """Agrega un nuevo remote al repositorio."""
    result = git_services.agregar_remoto(request.ruta_repo, request.nombre, request.url)
    return format_git_response(result)


@router.post("/remote/remove")
@handle_git_exceptions
def post_remote_remove(request: RemoteRemoveRequest):
    """Elimina un remote del repositorio."""
    result = git_services.eliminar_remoto(request.ruta_repo, request.nombre)
    return format_git_response(result)


@router.post("/remote/rename")
@handle_git_exceptions
def post_remote_rename(request: RemoteRenameRequest):
    """Renombra un remote del repositorio."""
    result = git_services.renombrar_remoto(
        request.ruta_repo, request.nombre_actual, request.nombre_nuevo
    )
    return format_git_response(result)


@router.post("/remote/set-url")
@handle_git_exceptions
def post_remote_set_url(request: RemoteSetUrlRequest):
    """Cambia la URL de un remote existente."""
    result = git_services.cambiar_url_remoto(request.ruta_repo, request.nombre, request.url)
    return format_git_response(result)


# --- CLONE ---

@router.post("/clone")
@handle_git_exceptions
def post_clone(request: CloneRequest):
    """Clona un repositorio Git remoto."""
    result = git_services.clonar_repositorio(
        request.url, request.ruta_destino, request.rama,
        request.profundidad, request.token
    )
    return format_git_response(result)


# --- PUSH ---

@router.post("/push")
@handle_git_exceptions
def post_push(request: PushRequest):
    """Envía commits al repositorio remoto (git push)."""
    result = git_services.hacer_push(
        request.ruta_repo, request.remote, request.rama,
        request.forzar, request.set_upstream, request.tags, request.token
    )
    return format_git_response(result)


# --- PULL ---

@router.post("/pull")
@handle_git_exceptions
def post_pull(request: PullRequest):
    """Descarga y fusiona cambios del repositorio remoto (git pull)."""
    result = git_services.hacer_pull(
        request.ruta_repo, request.remote, request.rama,
        request.rebase, request.token
    )
    return format_git_response(result)


# --- FETCH ---

@router.post("/fetch")
@handle_git_exceptions
def post_fetch(request: FetchRequest):
    """Descarga información del repositorio remoto sin fusionar (git fetch)."""
    result = git_services.hacer_fetch(
        request.ruta_repo, request.remote, request.prune,
        request.tags, request.token
    )
    return format_git_response(result)


# --- REMOTE BRANCHES ---

@router.get("/remote-branches", response_model=RemoteBranchesResponse)
@handle_git_exceptions
def get_remote_branches(
    ruta_repo: str = Query(".", description="Ruta del repositorio Git"),
    remote: str = Query("", description="Filtrar por remote específico")
):
    """Lista las ramas remotas del repositorio."""
    return git_services.listar_ramas_remotas(ruta_repo, remote)


# --- DELETE BRANCH ---

@router.post("/delete-branch")
@handle_git_exceptions
def post_delete_branch(request: BranchDeleteRequest):
    """Elimina una rama local y opcionalmente del remoto."""
    result = git_services.eliminar_rama(
        request.ruta_repo, request.branch_name, request.forzar,
        request.eliminar_remoto, request.remote, request.token
    )
    return format_git_response(result)


# --- TAGS ---

@router.get("/tags", response_model=TagListResponse)
@handle_git_exceptions
def get_tags(ruta_repo: str = Query(".", description="Ruta del repositorio Git")):
    """Lista todos los tags del repositorio."""
    return git_services.listar_tags(ruta_repo)


@router.post("/tag/create")
@handle_git_exceptions
def post_tag_create(request: TagCreateRequest):
    """Crea un nuevo tag en el repositorio."""
    result = git_services.crear_tag(
        request.ruta_repo, request.nombre, request.mensaje, request.commit
    )
    return format_git_response(result)


@router.post("/tag/delete")
@handle_git_exceptions
def post_tag_delete(request: TagDeleteRequest):
    """Elimina un tag del repositorio."""
    result = git_services.eliminar_tag(
        request.ruta_repo, request.nombre, request.eliminar_remoto,
        request.remote, request.token
    )
    return format_git_response(result)


# --- STASH ---

@router.get("/stashes", response_model=StashListResponse)
@handle_git_exceptions
def get_stashes(ruta_repo: str = Query(".", description="Ruta del repositorio Git")):
    """Lista todos los stashes del repositorio."""
    return git_services.listar_stashes(ruta_repo)


@router.post("/stash/save")
@handle_git_exceptions
def post_stash_save(request: StashSaveRequest):
    """Guarda los cambios actuales en un stash."""
    result = git_services.guardar_stash(
        request.ruta_repo, request.mensaje, request.incluir_untracked
    )
    return format_git_response(result)


@router.post("/stash/apply")
@handle_git_exceptions
def post_stash_apply(request: StashApplyRequest):
    """Aplica un stash sin eliminarlo de la lista."""
    result = git_services.aplicar_stash(request.ruta_repo, request.indice)
    return format_git_response(result)


@router.post("/stash/pop")
@handle_git_exceptions
def post_stash_pop(request: StashPopRequest):
    """Aplica un stash y lo elimina de la lista (pop)."""
    result = git_services.sacar_stash(request.ruta_repo, request.indice)
    return format_git_response(result)


@router.post("/stash/drop")
@handle_git_exceptions
def post_stash_drop(request: StashDropRequest):
    """Elimina un stash sin aplicarlo."""
    result = git_services.eliminar_stash(request.ruta_repo, request.indice)
    return format_git_response(result)
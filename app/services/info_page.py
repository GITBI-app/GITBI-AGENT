
from pathlib import Path
from app.services.files import cargar_json
from app.services.git_services import git_diff_archivo
from typing import Optional


def buscar_visuales_ocultos(json):
    """
    Busca dentro de sections los visualContainers que tengan 'display': {'mode': 'hidden'}
    y retorna un diccionario con los IDs de los visuales ocultos y su información.
    """

    ocultos = []
    try:
        sections = json['explorationState']['sections']
        for section_id, section in sections.items():
            visual_containers = section.get('visualContainers', {})
            for visual_id, visual in visual_containers.items():
                single_visual = visual.get('singleVisual', {})
                display = single_visual.get('display', {})
                if display.get('mode') == 'hidden':
                    ocultos.append({"visual_id": visual_id})
    except Exception as e:
        raise RuntimeError(f"Error procesando el JSON: {e}")
    return ocultos

def info_bookmark(ruta_repo,archivo_pbip, page_id, commit1: Optional[str] = None, commit2: Optional[str] = None):

    # no compruebo si el repo es .pbip o no porque ya lo hace info_page
    
    ruta = Path(ruta_repo)
    ruta_info_bookmark = ruta / f"{archivo_pbip}.Report"/ "definition"/ "bookmarks"
    bookmark_info = {}
    bookmark_by_page = {}
    visual_hidden_by_bookmark = {}
    for archivo in ruta_info_bookmark.rglob("*"):
        if archivo.is_file() and archivo.suffix == ".json" and archivo.name != "bookmarks.json":
            bookmark_data = cargar_json(archivo)
            bookmark_info[archivo.name] = bookmark_data
            # Usar ruta relativa respecto al repositorio
            ruta_relativa = archivo.relative_to(ruta)
            bookmark_info[archivo.name]["git_diff"] = git_diff_archivo(str(ruta), str(ruta_relativa), commit1, commit2)
    for bookmark_id, bookmark_each_data in bookmark_info.items():
        # Filtrar solo los datos relevantes para la página específica
        page = bookmark_each_data.get("explorationState").get("activeSection")
        if page == page_id:
            bookmark_by_page[bookmark_id] = bookmark_each_data
            visual_hidden_by_bookmark[bookmark_id]  = buscar_visuales_ocultos(bookmark_each_data)
    esquema = {
        "info_bookmark": bookmark_by_page,
        "visuals_hidden_by_bookmark": visual_hidden_by_bookmark
    }
    return esquema

def info_page(ruta_repo, page_id, commit1: Optional[str] = None, commit2: Optional[str] = None):
    ruta = Path(ruta_repo)
    #nombre del proyecto
    archivos_pbip = list(ruta.glob("*.pbip"))
    if len(archivos_pbip) == 0:
        raise FileNotFoundError("❌ No se encontró ningún archivo .pbip en la carpeta.")
    elif len(archivos_pbip) > 1:
        raise ValueError(f"⚠️ Se encontraron varios archivos .pbip: {archivos_pbip}")
    else:
        archivo_pbip = archivos_pbip[0]
        archivo_pbip = archivo_pbip.stem
    
    #info_page
    ruta_info_page = ruta / f"{archivo_pbip}.Report"/ "definition"/ "pages" / f"{page_id}" / "page.json"
    info_page = cargar_json(ruta_info_page)
    # Usar ruta relativa respecto al repositorio
    ruta_relativa_page = ruta_info_page.relative_to(ruta)
    info_page["git_diff"] = git_diff_archivo(str(ruta), str(ruta_relativa_page), commit1, commit2)
    #info_visuals
    ruta_visuales = ruta / f"{archivo_pbip}.Report"/ "definition"/ "pages" / f"{page_id}" / "visuals"
    visual_info = {}
    for carpeta in ruta_visuales.rglob("*"):
        if carpeta.is_dir():
            archivo_visual = carpeta / "visual.json"
            if archivo_visual.exists():
                visual_info[carpeta.name] = cargar_json(archivo_visual)
                # Usar ruta relativa respecto al repositorio
                ruta_relativa_visual = archivo_visual.relative_to(ruta)
                visual_info[carpeta.name]["git_diff"] = git_diff_archivo(str(ruta), str(ruta_relativa_visual), commit1, commit2)
    #info_bookmark
    info_bookmark_data = info_bookmark(ruta_repo, archivo_pbip, page_id, commit1, commit2)
    esquema = {
        "info_page": info_page,
        "visuals": visual_info,
        "info_bookmark": info_bookmark_data
    }
    return esquema





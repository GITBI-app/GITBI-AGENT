
from pathlib import Path
from app.services.files import carga_tmdl_relationships, cargar_json, carga_tdml, cargar_texto_archivo
from app.services.git_services import git_diff_archivo
from typing import Optional

def info_query_dax(ruta_repo, commit1: Optional[str] = None, commit2: Optional[str] = None):
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
    
    ruta_tableDefinition = ruta / f"{archivo_pbip}.SemanticModel"/ "DAXQueries"
    dax_query_info = {}
    for archivo in ruta_tableDefinition.rglob("*.dax"):
            if archivo.exists():
                dax_query_info[archivo.name] = cargar_texto_archivo(archivo)
                # Usar ruta relativa respecto al repositorio
                ruta_relativa_table = archivo.relative_to(ruta)
                dax_query_info[archivo.name]["git_diff"] = git_diff_archivo(str(ruta), str(ruta_relativa_table), commit1, commit2)

    return dax_query_info
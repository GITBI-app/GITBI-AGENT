
from pathlib import Path
from app.services.files import carga_tmdl_relationships, cargar_json, carga_tdml
from app.services.git_services import git_diff_archivo
from typing import Optional

def info_model(ruta_repo, commit1: Optional[str] = None, commit2: Optional[str] = None):
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
    ruta_diagramLayout = ruta / f"{archivo_pbip}.SemanticModel"/ "diagramLayout.json"
    diagramLayout = cargar_json(ruta_diagramLayout)
    # Usar ruta relativa respecto al repositorio
    ruta_relativa_diagram = ruta_diagramLayout.relative_to(ruta)
    diagramLayout["git_diff"] = git_diff_archivo(str(ruta), str(ruta_relativa_diagram), commit1, commit2)
    
    ruta_tableDefinition = ruta / f"{archivo_pbip}.SemanticModel"/ "definition"/  "tables"
    table_info = {}
    for archivo in ruta_tableDefinition.rglob("*"):
            if archivo.exists():
                table_info[archivo.name] = carga_tdml(archivo)
                # Usar ruta relativa respecto al repositorio
                ruta_relativa_table = archivo.relative_to(ruta)
                table_info[archivo.name]["git_diff"] = git_diff_archivo(str(ruta), str(ruta_relativa_table), commit1, commit2)

    ruta_relationship = ruta / f"{archivo_pbip}.SemanticModel"/ "definition"/  "relationships.tmdl"
    relationship_info = carga_tmdl_relationships(ruta_relationship)
    # Usar ruta relativa respecto al repositorio
    ruta_relativa_rel = ruta_relationship.relative_to(ruta)
    # Crear un diccionario que contenga tanto las relaciones como el git_diff
    relationship_data = {
        "relationships": relationship_info,
        "git_diff": git_diff_archivo(str(ruta), str(ruta_relativa_rel), commit1, commit2)
    }
    
    esquema = {
        "diagramLayout": diagramLayout,
        "tableDefinition": table_info,
        "relationship": relationship_data
    }
    return esquema
from pathlib import Path
import json

# Función para cargar relaciones desde tmdl y convertirlas a JSON
def carga_tmdl_relationships(ruta_archivo):
    """
    Lee un archivo TMDL y extrae las relaciones, devolviéndolas en formato JSON.
    Args:
        ruta_archivo (str): Ruta al archivo TMDL.
    Returns:
        dict: Diccionario con las relaciones y el código original.
    """
    relationships = []
    dict_relationships = {}
    try:
        with open(ruta_archivo, "r", encoding="utf-8") as file:
            lines = file.readlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("relationship "):
                rel = {}
                rel_id = line.split("relationship ")[1].strip()
                rel["id"] = rel_id
                i += 1
                from_col = None
                to_col = None
                # Leer atributos de la relación
                while i < len(lines) and (lines[i].startswith("\t") or ":" in lines[i]):
                    subline = lines[i].strip()
                    if subline.startswith("fromColumn:"):
                        from_col = subline.split("fromColumn:")[1].strip()
                        rel["fromColumn"] = from_col
                    elif subline.startswith("toColumn:"):
                        to_col = subline.split("toColumn:")[1].strip()
                        rel["toColumn"] = to_col
                    elif subline.startswith("crossFilteringBehavior:"):
                        rel["crossFilteringBehavior"] = subline.split("crossFilteringBehavior:")[1].strip()
                    elif subline.startswith("toCardinality:"):
                        rel["toCardinality"] = subline.split("toCardinality:")[1].strip()
                    elif subline.startswith("fromCardinality:"):
                        rel["fromCardinality"] = subline.split("fromCardinality:")[1].strip()
                    elif subline.startswith("isActive:"):
                        val = subline.split("isActive:")[1].strip()
                        rel["isActive"] = val.lower() == "true"
                    i += 1
                # Extraer nombres de tabla de fromColumn y toColumn
                tablas = []
                if from_col and "." in from_col:
                    tabla_from = from_col.split(".", 1)[0].strip()
                    tablas.append(tabla_from)
                if to_col and "." in to_col:
                    tabla_to = to_col.split(".", 1)[0].strip()
                    if tabla_to not in tablas:
                        tablas.append(tabla_to)
                rel["tables"] = tablas
                relationships.append(rel)
                continue
            i += 1
        dict_relationships["relationships_json"] = relationships
        dict_relationships["code"] = "".join(lines)
        return dict_relationships
    except FileNotFoundError:
        raise FileNotFoundError(f"❌ No se encontró el archivo TDML: {ruta_archivo}")
    except Exception as e:
        raise RuntimeError(f"⚠️ Error al leer o procesar el archivo TDML {ruta_archivo}: {e}")

#Funcion general para cargar un archivo JSON
def cargar_json(ruta_archivo):
    try:
        with open(ruta_archivo, "r", encoding="utf-8") as file:
            contenido = json.load(file)
        return contenido
    except FileNotFoundError:
        raise FileNotFoundError(f"❌ No se encontró el archivo: {ruta_archivo}")
    except json.JSONDecodeError:
        raise ValueError(f"❌ El archivo {ruta_archivo} no es un JSON válido")
    except Exception as e:
        raise RuntimeError(f"⚠️ Error al leer {ruta_archivo}: {e}")

# Función para leer un archivo TDML
def carga_tdml(ruta_archivo):
    """
    Lee un archivo TDML y retorna su contenido como un diccionario con nombre y código.
    Args:
        ruta_archivo (str): Ruta al archivo TDML.
    Returns:
        dict: Diccionario con 'nombre' (nombre de la tabla) y 'codigo' (contenido completo).
    """
    try:
        with open(ruta_archivo, "r", encoding="utf-8") as file:
            contenido = file.read()
        
        # Extraer nombre de la tabla y lineageTag
        nombre_tabla = None
        lineage_tag = None
        for line in contenido.splitlines():
            stripped = line.strip()
            if stripped.startswith('table '):
                nombre_tabla = stripped.split('table ')[1].strip()
            elif stripped.startswith('lineageTag:'):
                lineage_tag = stripped.split('lineageTag:')[1].strip()
            if nombre_tabla and lineage_tag:
                break
        
        return {
            "name": nombre_tabla,
            "lineageTag": lineage_tag,
            "codigo": contenido
        }
    except FileNotFoundError:
        raise FileNotFoundError(f"❌ No se encontró el archivo TDML: {ruta_archivo}")
    except Exception as e:
        raise RuntimeError(f"⚠️ Error al leer o procesar el archivo TDML {ruta_archivo}: {e}")
    

    
#Funcion que maneja la obtencion de archivos del proyecto
def obtener_archivos_proyecto(ruta_proyecto) -> dict:
    ruta = Path(ruta_proyecto)
    #nombre del proyecto
    archivos_pbip = list(ruta.glob("*.pbip"))
    if len(archivos_pbip) == 0:
        raise FileNotFoundError("❌ No se encontró ningún archivo .pbip en la carpeta.")
    elif len(archivos_pbip) > 1:
        raise ValueError(f"⚠️ Se encontraron varios archivos .pbip: {archivos_pbip}")
    else:
        archivo_pbip = archivos_pbip[0]
        archivo_pbip = archivo_pbip.stem
    archivos_proyecto = {
        "ruta": str(ruta_proyecto),
        "nombre_proyecto": archivo_pbip
    }
    #version del report
    ruta_version = ruta / f"{archivo_pbip}.Report"/ "Definition"/ "version.json"
    archivo_version= cargar_json(ruta_version)
    #info paginas
    ruta_pages_carpeta = ruta / f"{archivo_pbip}.Report"/ "Definition"/ "pages"
    ruta_pages = ruta / f"{ruta_pages_carpeta}"/ "pages.json"
    archivo_pages= cargar_json(ruta_pages)
    #info de pagina
    
    paginas_info = {}
    for carpeta in ruta_pages_carpeta.rglob("*"):
        if carpeta.is_dir():
            archivo_page = carpeta / "page.json"
            if archivo_page.exists():
                paginas_info[carpeta.name] = cargar_json(archivo_page).get("displayName", "Sin título")
                paginas_info[carpeta.name] = cargar_json(archivo_page).get("displayName", "Sin título")
    # Agregar al diccionario principal - convertir Path a str para serialización JSON
    archivos_proyecto = {
        "ruta": str(ruta_proyecto),
        "nombre_proyecto": str(archivo_pbip),
        "version": archivo_version,
        "paginas": archivo_pages,
        "pagina_titles": paginas_info

    }
    # Validar que sea JSON-serializable
    try:
        json.dumps(archivos_proyecto, ensure_ascii=False)
    except (TypeError, ValueError) as e:
        raise RuntimeError(f"⚠️ Error al serializar a JSON: {e}")
    return archivos_proyecto


def cargar_texto_archivo(ruta_archivo):
    """
    Lee un archivo de texto y retorna su contenido como string para envío via API.
    Args:
        ruta_archivo (str): Ruta al archivo.
    Returns:
        dict: Diccionario con 'nombre' y 'contenido' del archivo.
    """
    ruta = Path(ruta_archivo)
    try:
        with open(ruta, "r", encoding="utf-8") as file:
            contenido = file.read()
        return {
            "nombre": ruta.name,
            "contenido": contenido
        }
    except FileNotFoundError:
        raise FileNotFoundError(f"❌ No se encontró el archivo: {ruta_archivo}")
    except Exception as e:
        raise RuntimeError(f"⚠️ Error al leer el archivo {ruta_archivo}: {e}")



"""
config.py — lee y guarda los ajustes de mibarra.

Los ajustes viven en "config.json", al lado de este archivo.
Si el archivo no existe, se crea solo la primera vez con valores por defecto.
Si borras una opción del archivo, se usa la de por defecto.
"""

import json
import os
from pathlib import Path

# La carpeta donde está este archivo (sirve para encontrar config.json venga de donde venga)
CARPETA = Path(__file__).resolve().parent
RUTA_CONFIG = CARPETA / "config.json"


def _apps_por_defecto():
    """Arma la lista inicial de apps fijadas, solo con las que existen en ESTE computador."""
    candidatas = [
        ("Explorador", r"%WINDIR%\explorer.exe"),
        ("Edge", r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        ("Chrome", r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        ("Brave", r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        ("VS Code", r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
        ("Spotify", r"%APPDATA%\Spotify\Spotify.exe"),
    ]
    apps = []
    for nombre, ruta in candidatas:
        # expandvars cambia %WINDIR% por C:\Windows, etc.
        if Path(os.path.expandvars(ruta)).exists():
            apps.append({"nombre": nombre, "ruta": ruta})
    # "ms-settings:" no es un archivo, es un "enlace" que abre la Configuración de Windows
    apps.append({"nombre": "Configuración", "ruta": "ms-settings:", "emoji": "⚙"})
    return apps


POR_DEFECTO = {
    "posicion": "abajo",            # "abajo" o "arriba"
    "alineacion": "centro",         # "centro" (flotante, justo del tamaño necesario) o "completa"
    "alto": 56,                     # alto de la barra en píxeles
    "margen": 8,                    # separación con el borde de la pantalla
    "estilo": "vidrio",             # "vidrio" (fondo borroso) o "solido"
    "color_acento": "#7aa2ff",      # color de los detalles (puntos, barras de progreso)
    "ocultar_barra_windows": True,  # esconder la barra de tareas de Windows mientras mibarra está abierta
    "reservar_espacio": True,       # que las ventanas maximizadas no queden debajo de mibarra
    "esconder_en_pantalla_completa": True,  # esconderse con juegos/videos en pantalla completa
    "apps_fijadas": None,           # None = se llena con _apps_por_defecto()
    "widgets": ["musica", "clima", "red", "cpu", "ram", "bateria", "volumen", "bandeja", "reloj"],
    "clima": {"ciudad": "Santiago", "latitud": -33.45, "longitud": -70.66},
    "tema": "oscuro",               # "oscuro", "claro" o "auto" (igual que Windows)
    "moneda": {"cantidad": 1, "desde": "USD", "hacia": "CLP"},
}


def cargar():
    """Devuelve un diccionario con todos los ajustes."""
    datos = {}
    if RUTA_CONFIG.exists():
        try:
            datos = json.loads(RUTA_CONFIG.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as error:
            # Si el archivo quedó mal escrito (por ejemplo, falta una coma), no lo borramos:
            # avisamos y usamos los valores por defecto.
            print(f"[mibarra] config.json tiene un error y no se pudo leer: {error}")
            print("[mibarra] Uso los ajustes por defecto. Revisa el archivo.")
            datos = {}
        era_nuevo = False
    else:
        era_nuevo = True

    # Mezclar: lo que falte en el archivo se completa con POR_DEFECTO
    config = dict(POR_DEFECTO)
    config.update(datos)
    if not config.get("apps_fijadas"):
        config["apps_fijadas"] = _apps_por_defecto()

    if era_nuevo:
        guardar(config)
    return config


def guardar(config):
    """Escribe los ajustes en config.json (bonito y legible)."""
    try:
        RUTA_CONFIG.write_text(
            json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError as error:
        print(f"[mibarra] No pude guardar config.json: {error}")

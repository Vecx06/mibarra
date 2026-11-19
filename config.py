"""
config.py — lee y guarda los ajustes de mibarra.

Los ajustes viven en "config.json", al lado de este archivo.
Si el archivo no existe, se crea solo la primera vez con valores por defecto.
Si borras una opción del archivo, se usa la de por defecto.
"""

import json
import os
from pathlib import Path

import rutas
from registro import log

RUTA_CONFIG = rutas.ARCHIVO_CONFIG


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
    "bienvenida_vista": False,      # ¿ya vio la pantalla de bienvenida?
    "buscar_actualizaciones": True, # avisar cuando hay una versión nueva en GitHub
    "auto_ocultar": False,          # la barra se esconde y aparece al llevar el mouse al borde
    "boton_inicio": "windows",      # "windows" (menú Inicio) o "buscador" (el buscador de mibarra)
    "atajo_buscador": "alt+espacio",
    "atajo_barra": "ctrl+alt+b",    # mostrar / ocultar la barra
    "enfoque_minutos": 25,
    "avisar_limite_ia": True,       # avisar cuando te queda poco de Claude o Codex
    "buscador_uso": {},             # qué abres más (para ordenar mejor el buscador)
}


WIDGETS_VALIDOS = [
    "reloj", "anio", "enfoque", "cpu", "ram", "disco", "red", "bateria", "bandeja", "musica",
    "volumen", "clima", "comando", "notas", "conexiones", "tema", "capturas", "bateria_anillo",
    "cpu_anillo", "almacenamiento", "moneda", "claude_limites", "claude_tokens", "codex_limites",
]
VERSION_CONFIG = 2


def _entero(valor, minimo, maximo, defecto):
    try:
        return max(minimo, min(maximo, int(valor)))
    except (TypeError, ValueError):
        return defecto


def _decimal(valor, minimo, maximo, defecto):
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return defecto
    return numero if minimo <= numero <= maximo else defecto


def _opcion(valor, opciones, defecto):
    return valor if valor in opciones else defecto


def validar(c):
    """
    Revisa cada ajuste y arregla lo que esté mal escrito o fuera de rango.
    Así, si alguien edita config.json a mano y se equivoca, mibarra no se cae:
    usa el valor por defecto para ESE ajuste y sigue.
    """
    d = POR_DEFECTO
    c["posicion"] = _opcion(c.get("posicion"), ("abajo", "arriba"), d["posicion"])
    c["alineacion"] = _opcion(c.get("alineacion"), ("centro", "completa"), d["alineacion"])
    c["estilo"] = _opcion(c.get("estilo"), ("vidrio", "solido"), d["estilo"])
    c["tema"] = _opcion(c.get("tema"), ("oscuro", "claro", "auto"), d["tema"])
    c["alto"] = _entero(c.get("alto"), 44, 76, d["alto"])
    c["margen"] = _entero(c.get("margen"), 0, 24, d["margen"])
    color = str(c.get("color_acento", ""))
    if not (len(color) == 7 and color.startswith("#")
            and all(ch in "0123456789abcdefABCDEF" for ch in color[1:])):
        c["color_acento"] = d["color_acento"]
    c["boton_inicio"] = _opcion(c.get("boton_inicio"), ("windows", "buscador"), d["boton_inicio"])
    c["enfoque_minutos"] = _entero(c.get("enfoque_minutos"), 5, 180, d["enfoque_minutos"])
    for clave in ("atajo_buscador", "atajo_barra"):
        valor = c.get(clave)
        c[clave] = valor.strip().lower() if isinstance(valor, str) and "+" in valor else d[clave]
    uso = c.get("buscador_uso")
    c["buscador_uso"] = {str(k): int(v) for k, v in uso.items()
                         if isinstance(v, int)} if isinstance(uso, dict) else {}
    for clave in ("ocultar_barra_windows", "reservar_espacio", "esconder_en_pantalla_completa",
                  "bienvenida_vista", "buscar_actualizaciones", "auto_ocultar", "avisar_limite_ia"):
        c[clave] = bool(c.get(clave, d.get(clave, True)))

    # Widgets: solo nombres conocidos y sin repetir (respetando el orden)
    widgets = c.get("widgets") if isinstance(c.get("widgets"), list) else list(d["widgets"])
    vistos = []
    for w in widgets:
        if isinstance(w, str) and w in WIDGETS_VALIDOS and w not in vistos:
            vistos.append(w)
    c["widgets"] = vistos

    # Apps: cada una necesita al menos una "ruta" de texto
    apps = c.get("apps_fijadas") if isinstance(c.get("apps_fijadas"), list) else []
    c["apps_fijadas"] = [
        {k: str(v) for k, v in app.items() if k in ("nombre", "ruta", "emoji")}
        for app in apps if isinstance(app, dict) and isinstance(app.get("ruta"), str) and app["ruta"]
    ]

    clima = c.get("clima") if isinstance(c.get("clima"), dict) else {}
    c["clima"] = {
        "ciudad": str(clima.get("ciudad") or d["clima"]["ciudad"])[:60],
        "latitud": _decimal(clima.get("latitud"), -90, 90, d["clima"]["latitud"]),
        "longitud": _decimal(clima.get("longitud"), -180, 180, d["clima"]["longitud"]),
    }

    moneda = c.get("moneda") if isinstance(c.get("moneda"), dict) else {}

    def codigo(valor, defecto):
        valor = str(valor or "").strip().upper()
        return valor if len(valor) == 3 and valor.isalpha() else defecto

    c["moneda"] = {
        "cantidad": _decimal(moneda.get("cantidad"), 0.0001, 1e12, 1),
        "desde": codigo(moneda.get("desde"), "USD"),
        "hacia": codigo(moneda.get("hacia"), "CLP"),
    }
    c["version_config"] = VERSION_CONFIG
    return c


def cargar():
    """Devuelve un diccionario con todos los ajustes (ya revisados)."""
    datos = {}
    era_nuevo = not RUTA_CONFIG.exists()
    if not era_nuevo:
        try:
            datos = json.loads(RUTA_CONFIG.read_text(encoding="utf-8"))
            if not isinstance(datos, dict):
                raise ValueError("no es un objeto JSON")
        except (ValueError, OSError) as error:
            # Si el archivo quedó mal escrito no lo borramos: lo respaldamos y seguimos
            log.error("config.json tiene un error y no se pudo leer (%s). Uso los ajustes por defecto.", error)
            try:
                RUTA_CONFIG.replace(RUTA_CONFIG.with_name("config.con-error.json"))
            except OSError:
                pass
            datos = {}
            era_nuevo = True

    config = dict(POR_DEFECTO)
    config.update(datos)
    if not config.get("apps_fijadas"):
        config["apps_fijadas"] = _apps_por_defecto()
    if not era_nuevo and "bienvenida_vista" not in datos:
        config["bienvenida_vista"] = True   # ya la venía usando: no mostrar la bienvenida
    validar(config)
    guardar(config)
    return config


def por_defecto():
    """Ajustes de fábrica (para "Restablecer")."""
    config = dict(POR_DEFECTO)
    config["apps_fijadas"] = _apps_por_defecto()
    config["bienvenida_vista"] = True
    return validar(config)


def guardar(config):
    """Escribe los ajustes en config.json de forma segura (primero a un temporal, después lo reemplaza)."""
    try:
        temporal = RUTA_CONFIG.with_suffix(".tmp")
        temporal.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        temporal.replace(RUTA_CONFIG)    # así, si se corta la luz a mitad, config.json no queda a medias
    except OSError as error:
        log.error("No pude guardar config.json: %s", error)

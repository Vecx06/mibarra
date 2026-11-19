"""
rutas.py — dónde vive cada archivo de mibarra.

Hay dos lugares:
  - CARPETA_APP: donde están los archivos del programa (el código, el ícono).
  - CARPETA_DATOS: donde guardamos TUS cosas (ajustes, notas, registro de errores).

Si usas mibarra instalada (el .exe), Windows no deja escribir en "Archivos de programa",
así que tus datos van a %APPDATA%\\mibarra (por ejemplo C:\\Users\\Vito\\AppData\\Roaming\\mibarra).
Si la usas con Python (la versión en .zip), todo queda junto en la misma carpeta, como antes.
"""

import os
import sys
from pathlib import Path

# ¿Estamos corriendo como .exe (hecho con PyInstaller)?
ES_EXE = bool(getattr(sys, "frozen", False))

if ES_EXE:
    # PyInstaller descomprime los archivos del programa en sys._MEIPASS
    CARPETA_APP = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    CARPETA_DATOS = Path(os.environ.get("APPDATA", Path.home())) / "mibarra"
else:
    CARPETA_APP = Path(__file__).resolve().parent
    CARPETA_DATOS = CARPETA_APP

# Para pruebas o uso "portátil" (en un pendrive) se puede elegir otra carpeta de datos
if os.environ.get("MIBARRA_DATOS"):
    CARPETA_DATOS = Path(os.environ["MIBARRA_DATOS"])

CARPETA_DATOS.mkdir(parents=True, exist_ok=True)

ARCHIVO_CONFIG = CARPETA_DATOS / "config.json"
ARCHIVO_NOTAS = CARPETA_DATOS / "notas.txt"
ARCHIVO_ESTADO_BARRA = CARPETA_DATOS / "estado_barra_windows.json"
ARCHIVO_REGISTRO = CARPETA_DATOS / "mibarra.log"
ICONO = CARPETA_APP / "recursos" / "mibarra.ico"


def comando_propio(*argumentos):
    """
    El comando para volver a abrir mibarra (para reiniciar, iniciar con Windows o el guardián).
    Devuelve (programa, [argumentos]).
    """
    if ES_EXE:
        return sys.executable, list(argumentos)
    python = Path(sys.executable)
    sin_consola = python.with_name("pythonw.exe")   # pythonw = Python sin la ventana negra
    if sin_consola.exists():
        python = sin_consola
    return str(python), [str(CARPETA_APP / "main.py"), *argumentos]

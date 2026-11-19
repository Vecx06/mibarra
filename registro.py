"""
registro.py — el "diario" de mibarra.

En vez de print(), usamos el módulo logging de Python. Todo queda anotado en
mibarra.log (en la carpeta de datos). Cuando el archivo pasa de 512 KB, se guarda
como mibarra.log.1 y se empieza uno nuevo (así nunca crece para siempre).

Uso en cualquier archivo:
    from registro import log
    log.info("algo pasó")
    log.warning("ojo con esto")
    log.exception("falló esto")   # dentro de un except: anota también el error completo
"""

import logging
import sys
from logging.handlers import RotatingFileHandler

import rutas

log = logging.getLogger("mibarra")


def configurar():
    if log.handlers:
        return
    log.setLevel(logging.INFO)
    formato = logging.Formatter("%(asctime)s  %(levelname)-7s  %(module)s: %(message)s", "%Y-%m-%d %H:%M:%S")
    try:
        archivo = RotatingFileHandler(rutas.ARCHIVO_REGISTRO, maxBytes=512 * 1024, backupCount=2, encoding="utf-8")
        archivo.setFormatter(formato)
        log.addHandler(archivo)
    except OSError:
        pass
    if sys.stderr is not None:          # el .exe sin consola no tiene stderr
        consola = logging.StreamHandler()
        consola.setFormatter(formato)
        log.addHandler(consola)

"""
actualizaciones.py — revisa en GitHub si hay una versión nueva de mibarra.

Solo LEE la página pública de "Releases" del repositorio: no envía ningún dato tuyo.
"""

import json
import urllib.request

from version import REPOSITORIO, VERSION


def a_numeros(texto):
    """'v2.1.0' -> (2, 1, 0). Sirve para comparar versiones como números y no como texto."""
    numeros = []
    for parte in texto.strip().lstrip("vV").split("."):
        digitos = "".join(ch for ch in parte if ch.isdigit())
        numeros.append(int(digitos) if digitos else 0)
    while len(numeros) < 3:
        numeros.append(0)
    return tuple(numeros[:3])


def es_mas_nueva(otra, actual=VERSION):
    return a_numeros(otra) > a_numeros(actual)


def consultar():
    """
    Devuelve {"version": "2.1.0", "url": "...", "notas": "..."} si hay una versión más nueva,
    o None si ya tienes la última. Si no hay internet, lanza un error (quien llama decide qué hacer).
    """
    pedido = urllib.request.Request(
        f"https://api.github.com/repos/{REPOSITORIO}/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": f"mibarra/{VERSION}"})
    with urllib.request.urlopen(pedido, timeout=10) as respuesta:
        datos = json.load(respuesta)
    etiqueta = datos.get("tag_name", "")
    if etiqueta and es_mas_nueva(etiqueta):
        return {"version": etiqueta.lstrip("vV"), "url": datos.get("html_url", ""),
                "notas": datos.get("body", "")}
    return None

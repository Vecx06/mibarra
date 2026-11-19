"""Pruebas del buscador rápido y de los atajos de teclado."""

import pytest

import atajos
import buscador


@pytest.mark.parametrize("nombre, consulta, minimo", [
    ("Chrome", "chrome", 100), ("Chrome", "chr", 80), ("Google Chrome", "chr", 60),
    ("Visual Studio Code", "vsc", 50), ("Notepad++", "pad", 30), ("Calculadora", "cálc", 80),
])
def test_puntaje(nombre, consulta, minimo):
    assert buscador.puntaje(nombre, consulta) >= minimo


def test_puntaje_sin_relacion():
    assert buscador.puntaje("Spotify", "word") == 0


def test_indexar_programas(tmp_path):
    (tmp_path / "Carpeta").mkdir()
    for nombre in ("Spotify.lnk", "Carpeta/Discord.lnk", "Uninstall Discord.lnk", "leeme.txt", "Carpeta/Spotify.lnk"):
        (tmp_path / nombre).write_text("")
    nombres = sorted(p["nombre"] for p in buscador.indexar_programas([tmp_path]))
    assert nombres == ["Discord", "Spotify"]


def test_buscar_ordena_y_agrega_google():
    programas = [{"nombre": "Discord", "detalle": "Programa", "ruta": "d.lnk"},
                 {"nombre": "Google Chrome", "detalle": "Programa", "ruta": "c.lnk"}]
    r = buscador.buscar("dis", programas)
    assert r[0]["nombre"] == "Discord"
    assert r[-1]["accion"] == "web" and "google.com" in r[-1]["valor"]


def test_buscar_lo_que_mas_usas_sube():
    programas = [{"nombre": "Paint", "detalle": "Programa", "ruta": "p.lnk"},
                 {"nombre": "Paint 3D", "detalle": "Programa", "ruta": "p3.lnk"}]
    assert buscador.buscar("paint", programas)[0]["nombre"] == "Paint"
    assert buscador.buscar("pai", programas, uso={"Paint 3D": 8})[0]["nombre"] == "Paint 3D"


def test_buscar_cuentas_y_webs():
    r = buscador.buscar("15*3", [])
    assert r[0]["accion"] == "copiar" and r[0]["valor"] == "45"
    r = buscador.buscar("youtube.com", [])
    assert r[0]["accion"] == "web" and r[0]["valor"] == "https://youtube.com"
    assert buscador.parece_cuenta("=2+2") and not buscador.parece_cuenta("2026")
    assert not buscador.parece_web("hola mundo")


def test_buscar_vacio():
    assert buscador.buscar("   ", []) == []


@pytest.mark.parametrize("texto, esperado", [
    ("alt+espacio", (0x0001, 0x20)), ("ctrl+alt+b", (0x0003, 0x42)),
    ("win + shift + k", (0x000C, 0x4B)), ("ctrl+f5", (0x0002, 0x74)),
])
def test_interpretar_atajos(texto, esperado):
    assert atajos.interpretar(texto) == esperado


@pytest.mark.parametrize("malo", ["b", "ctrl+", "hiper+b", "ctrl+ñandú"])
def test_atajos_invalidos(malo):
    with pytest.raises(ValueError):
        atajos.interpretar(malo)


def test_atajo_bonito():
    assert atajos.bonito("ctrl+alt+b") == "Ctrl + Alt + B"
    assert atajos.bonito("alt+espacio") == "Alt + Espacio"

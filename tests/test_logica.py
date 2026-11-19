"""Pruebas de la lógica que no necesita ventanas."""

import json

import pytest

import actualizaciones
import config
import rutas


# ---------------- Calculadora del widget Comando ----------------
@pytest.mark.parametrize("texto, esperado", [
    ("2+2", 4), ("15*3", 45), ("2^3", 8), ("1,5*2", 3), ("(1+2)*3", 9), ("10/4", 2.5), ("-3+1", -2),
])
def test_calcular(texto, esperado):
    from mas_widgets import calcular
    assert calcular(texto) == esperado


@pytest.mark.parametrize("peligroso", ["__import__('os')", "open('x')", "a+1", "[1,2]"])
def test_calcular_rechaza_codigo(peligroso):
    from mas_widgets import calcular
    with pytest.raises(ValueError):
        calcular(peligroso)


def test_formato_chileno():
    from mas_widgets import _formato
    assert _formato(37558.734) == "37.558,73"
    assert _formato(0.5) == "0,50"


# ---------------- Versiones ----------------
def test_versiones():
    assert actualizaciones.a_numeros("v2.1") == (2, 1, 0)
    assert actualizaciones.a_numeros("2.0.10") == (2, 0, 10)
    assert actualizaciones.es_mas_nueva("2.0.1", "2.0.0")
    assert actualizaciones.es_mas_nueva("v2.10.0", "2.9.9")
    assert not actualizaciones.es_mas_nueva("v1.9.9", "2.0.0")
    assert not actualizaciones.es_mas_nueva("2.0.0", "2.0.0")


# ---------------- Ajustes ----------------
def test_validar_arregla_valores_malos():
    malo = {
        "alto": 999, "margen": -5, "posicion": "al lado", "estilo": 3, "tema": "rosado",
        "color_acento": "rojo", "widgets": ["reloj", "reloj", "inventado", 7, "cpu"],
        "apps_fijadas": [{"nombre": "Sin ruta"}, {"nombre": "OK", "ruta": "C:/a.exe"}, "texto"],
        "clima": {"ciudad": "", "latitud": 500, "longitud": "x"},
        "moneda": {"cantidad": -1, "desde": "dolares", "hacia": "clp"},
    }
    c = config.validar(dict(malo))
    assert c["alto"] == 76 and c["margen"] == 0
    assert c["posicion"] == "abajo" and c["estilo"] == "vidrio" and c["tema"] == "oscuro"
    assert c["color_acento"] == config.POR_DEFECTO["color_acento"]
    assert c["widgets"] == ["reloj", "cpu"]
    assert c["apps_fijadas"] == [{"nombre": "OK", "ruta": "C:/a.exe"}]
    assert c["clima"]["latitud"] == config.POR_DEFECTO["clima"]["latitud"]
    assert c["moneda"] == {"cantidad": 1, "desde": "USD", "hacia": "CLP"}


def test_cargar_config_rota_no_se_cae():
    rutas.ARCHIVO_CONFIG.write_text("{ esto no es json", encoding="utf-8")
    c = config.cargar()
    assert c["alto"] == config.POR_DEFECTO["alto"]
    assert rutas.ARCHIVO_CONFIG.with_name("config.con-error.json").exists()


def test_cargar_config_antigua_mantiene_tus_cosas():
    antigua = {"posicion": "arriba", "widgets": ["reloj", "cpu"],
               "apps_fijadas": [{"nombre": "Mi app", "ruta": "C:/app.exe"}]}
    rutas.ARCHIVO_CONFIG.write_text(json.dumps(antigua), encoding="utf-8")
    c = config.cargar()
    assert c["posicion"] == "arriba"
    assert c["widgets"] == ["reloj", "cpu"]
    assert c["apps_fijadas"][0]["nombre"] == "Mi app"
    assert c["bienvenida_vista"] is True          # quien ya la usaba no ve la bienvenida
    assert c["version_config"] == config.VERSION_CONFIG


def test_config_nueva_muestra_bienvenida():
    rutas.ARCHIVO_CONFIG.unlink(missing_ok=True)
    c = config.cargar()
    assert c["bienvenida_vista"] is False
    assert rutas.ARCHIVO_CONFIG.exists()

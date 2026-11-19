"""Pruebas de la interfaz (se abren las ventanas "en invisible")."""

import pytest

import config


@pytest.fixture
def dock(app):
    from dock import Dock
    c = config.por_defecto()
    c.update({"ocultar_barra_windows": False, "reservar_espacio": False, "esconder_en_pantalla_completa": False,
              "estilo": "solido", "widgets": list(config.WIDGETS_VALIDOS)})
    d = Dock(c)
    d.show()
    d.iniciar()
    yield d
    d.limpiar()
    d.close()


def test_catalogo_y_validos_coinciden():
    from ajustes import CATALOGO
    assert {c[0] for c in CATALOGO} == set(config.WIDGETS_VALIDOS)


def test_todos_los_widgets_se_crean(dock):
    # "bandeja" no se crea si la barra de Windows queda visible (ocultar_barra_windows = False)
    esperados = [w for w in config.WIDGETS_VALIDOS if w != "bandeja"]
    assert [w.id_widget for w in dock.widgets] == esperados


def test_si_no_caben_se_esconden_y_el_reloj_queda(dock):
    # Con 20 widgets en una pantalla de prueba chica, algunos no caben
    assert dock.widgets_sin_espacio
    assert "reloj" not in dock.widgets_sin_espacio
    assert dock.width() <= dock.screen().geometry().width()


@pytest.mark.parametrize("tema", ["oscuro", "claro"])
@pytest.mark.parametrize("forma", ["centro", "completa"])
def test_aplicar_config_en_vivo(dock, tema, forma):
    dock.config.update({"tema": tema, "alineacion": forma, "alto": 64})
    dock.aplicar_config("todo")
    assert dock.height() == 64
    pantalla = dock.screen().geometry()
    assert dock.width() <= pantalla.width()


def test_barra_centrada_queda_al_medio(dock, app):
    dock.config["widgets"] = ["reloj"]
    dock.config["alineacion"] = "centro"
    dock.aplicar_config("todo")
    app.processEvents()
    dock._ajustar_ancho(animar=False)
    g, pantalla = dock.geometry(), dock.screen().geometry()
    izquierda = g.left() - pantalla.left()
    derecha = pantalla.right() - g.right()
    assert abs(izquierda - derecha) <= 2


def test_modo_edicion_y_quitar_widget(dock):
    from widgets import InsigniaQuitar
    dock.modo_edicion(True)
    assert all(w.findChildren(InsigniaQuitar) for w in dock.widgets)
    dock.quitar_widget("cpu")
    assert "cpu" not in dock.config["widgets"]
    dock.modo_edicion(False)


def test_todas_las_paginas_de_ajustes(dock):
    dock.abrir_ajustes()
    ajustes = dock.ventana_ajustes
    for clave, *_ in ajustes.PAGINAS:
        ajustes.ir_a(clave)
    ajustes.campo_buscar.setText("reloj")
    ajustes.campo_buscar.setText("no existe nada así")
    ajustes.close()


def test_bienvenida_y_aviso(dock):
    from bienvenida import Aviso, Bienvenida
    b = Bienvenida(dock)
    b.mostrar()
    b.close()
    assert dock.config["bienvenida_vista"] is True
    a = Aviso("Título", "Texto", "Ver", "https://example.com")
    a.mostrar_sobre(dock)
    a.close()


def test_logo(app):
    from logo import dibujar_logo
    assert not dibujar_logo(64).isNull()

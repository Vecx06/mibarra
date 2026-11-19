"""
Pruebas que SOLO corren en Windows: llaman a las funciones reales de Windows.
(En GitHub Actions corren en un Windows de verdad.)
"""

import json
import os
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

import pytest

import rutas
import sistema_windows as sw

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="solo en Windows")


def test_funciones_basicas_no_fallan():
    ventanas = sw.listar_ventanas()
    assert isinstance(ventanas, list)
    for v in ventanas:
        assert isinstance(v.titulo, str)
    sw.ventana_activa()
    assert isinstance(sw.hay_pantalla_completa(), bool)
    assert isinstance(sw.windows_usa_tema_claro(), bool)
    assert isinstance(sw.red_wifi(), str)
    assert isinstance(sw.inicio_automatico_activo(), bool)


def test_guardian_restaura_si_la_barra_se_cae():
    if not sw.BarraWindows._ventanas():
        pytest.skip("este Windows no tiene barra de tareas (Shell_TrayWnd)")
    estado = sw.BarraWindows._leer_estado()
    victima = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    rutas.ARCHIVO_ESTADO_BARRA.write_text(json.dumps({"estado_original": estado, "pid": victima.pid}))
    import main
    hilo = threading.Thread(target=main.modo_guardian, args=(victima.pid,), daemon=True)
    hilo.start()
    time.sleep(0.5)
    victima.kill()                      # "se cae" la barra
    hilo.join(timeout=10)
    assert not rutas.ARCHIVO_ESTADO_BARRA.exists()
    assert sw.BarraWindows._leer_estado() == estado


def test_guardian_no_toca_archivo_de_otra_mibarra():
    rutas.ARCHIVO_ESTADO_BARRA.write_text(json.dumps({"estado_original": 2, "pid": 999999}))
    assert sw.BarraWindows.restaurar_desde_archivo(solo_si_es_de_pid=12345) is False
    assert rutas.ARCHIVO_ESTADO_BARRA.exists()
    rutas.ARCHIVO_ESTADO_BARRA.unlink()


def test_barra_real_en_windows(tmp_path):
    """
    Abre mibarra DE VERDAD (con ventanas reales de Windows, no invisibles), esconde la barra
    de Windows, reserva espacio, y al cerrar revisa que todo quedó como estaba.
    Además saca una captura de pantalla para revisar cómo se ve.
    """
    if not sw.BarraWindows._ventanas():
        pytest.skip("este Windows no tiene barra de tareas (Shell_TrayWnd)")
    estado_antes = sw.BarraWindows._leer_estado()
    capturas = Path(os.environ.get("MIBARRA_CAPTURAS", tmp_path))
    capturas.mkdir(parents=True, exist_ok=True)
    guion = textwrap.dedent(f"""
        import base64, json, sys
        sys.path.insert(0, {str(Path(__file__).resolve().parent.parent)!r})
        from PyQt6.QtCore import QBuffer, QIODevice, QTimer
        from PyQt6.QtWidgets import QApplication
        import config, estilo, sistema_windows as sw
        from dock import Dock
        app = QApplication(sys.argv)
        app.setStyleSheet(estilo.hoja_global())
        c = config.por_defecto()
        c.update({{"widgets": ["capturas", "almacenamiento", "comando", "tema", "conexiones",
                              "cpu_anillo", "moneda", "notas", "clima", "reloj"]}})
        resultado = {{}}
        def revisar(nombre):
            barra = sw.BarraWindows._ventanas()[0]
            pantalla = app.primaryScreen().geometry()
            animacion = getattr(d, "_animacion", None)
            resultado[nombre] = {{
                "barra_windows_visible": bool(sw.user32.IsWindowVisible(barra)),
                "espacio_reservado": d.espacio.activo,
                "geometria": [d.x(), d.y(), d.width(), d.height()],
                "pantalla": [pantalla.width(), pantalla.height(), app.primaryScreen().devicePixelRatio()],
                "medida_contenido": d._medir(),
                "sin_espacio": d.widgets_sin_espacio,
                "animando": bool(animacion and animacion.state() == animacion.State.Running),
                "vidrio": d.vidrio,
                "fuente_iconos": estilo.fuente_iconos(),
            }}
            completa = app.primaryScreen().grabWindow(0)
            completa.save({str(capturas)!r} + "/" + nombre + ".png")
            # Un recorte de la parte de abajo (donde está la barra), en texto, para verlo en el registro
            recorte = completa.copy(0, completa.height() - 110, completa.width(), 110)
            buffer = QBuffer(); buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            recorte.save(buffer, "PNG")
            print("CAPTURA_" + nombre + "=" + base64.b64encode(bytes(buffer.data())).decode())
        def paso2():
            revisar("oscuro")
            c["tema"] = "claro"; d.aplicar_config("todo")
            QTimer.singleShot(1500, lambda: (revisar("claro"), app.quit()))
        d = Dock(c); d.show(); d.iniciar()
        app.aboutToQuit.connect(d.limpiar)
        QTimer.singleShot(3000, paso2)
        app.exec()
        print("RESULTADO=" + json.dumps(resultado))
    """)
    entorno = dict(os.environ)
    entorno.pop("QT_QPA_PLATFORM", None)          # ventanas reales
    proceso = subprocess.run([sys.executable, "-c", guion], capture_output=True, text=True, timeout=90, env=entorno)
    print(proceso.stdout, proceso.stderr[-3000:])
    linea = [x for x in proceso.stdout.splitlines() if x.startswith("RESULTADO=")]
    assert linea, "la barra no terminó bien"
    resultado = json.loads(linea[0].split("=", 1)[1])
    assert resultado["oscuro"]["barra_windows_visible"] is False
    assert resultado["oscuro"]["espacio_reservado"] is True
    # Al cerrar: la barra de Windows vuelve y queda igual que antes
    barra = sw.BarraWindows._ventanas()[0]
    assert sw.user32.IsWindowVisible(barra)
    assert sw.BarraWindows._leer_estado() == estado_antes
    assert not rutas.ARCHIVO_ESTADO_BARRA.exists()

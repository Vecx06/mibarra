"""
main.py — el punto de partida de mibarra.

    mibarra                     -> abre la barra
    mibarra --restaurar         -> arregla la barra de Windows si mibarra se cerró mal
    mibarra --guardian <pid>    -> (uso interno) vigila a la barra y arregla todo si se cae
"""

import atexit
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # para encontrar los otros archivos

import registro  # noqa: E402
import rutas  # noqa: E402
from registro import log  # noqa: E402
from version import VERSION  # noqa: E402


def registrar_error(tipo, valor, rastro):
    """
    Si algo falla, NO cerramos la barra de golpe (dejaría la barra de Windows escondida):
    lo anotamos en mibarra.log y seguimos.
    """
    log.error("Error no controlado", exc_info=(tipo, valor, rastro))


def modo_guardian(pid):
    """
    El guardián es una segunda copia de mibarra, invisible y sin ventanas, que solo
    espera a que la barra se cierre. Si se cerró MAL (se colgó, la cerraron desde el
    Administrador de tareas...), devuelve la barra de Windows a como estaba.
    """
    import sistema_windows as sw
    sw.esperar_a_que_termine(pid)
    if sw.BarraWindows.restaurar_desde_archivo(solo_si_es_de_pid=pid):
        log.warning("mibarra (proceso %s) se cerró mal: el guardián restauró la barra de Windows", pid)


def lanzar_guardian():
    import sistema_windows as sw
    if not sw.ES_WINDOWS:
        return
    programa, argumentos = rutas.comando_propio("--guardian", str(os.getpid()))
    try:
        subprocess.Popen([programa, *argumentos], close_fds=True,
                         creationflags=0x00000008 | 0x00000200 | 0x08000000)   # sin ventana, independiente
    except OSError:
        log.exception("No pude iniciar el guardián")


def main():
    registro.configurar()

    if "--restaurar" in sys.argv:
        import sistema_windows as sw
        sw.BarraWindows.restaurar_desde_archivo()
        log.info("Barra de Windows restaurada a mano (--restaurar)")
        return

    if "--guardian" in sys.argv:
        try:
            modo_guardian(int(sys.argv[sys.argv.index("--guardian") + 1]))
        except (IndexError, ValueError):
            pass
        return

    sys.excepthook = registrar_error

    from PyQt6.QtCore import QLockFile, QTimer
    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import QApplication

    import config
    import estilo
    import sistema_windows as sw
    from dock import Dock

    app = QApplication(sys.argv)
    app.setApplicationName("mibarra")
    app.setApplicationVersion(VERSION)
    app.setQuitOnLastWindowClosed(False)
    if rutas.ICONO.exists():
        app.setWindowIcon(QIcon(str(rutas.ICONO)))

    # Solo una mibarra a la vez
    candado = QLockFile(os.path.join(tempfile.gettempdir(), "mibarra.lock"))
    if not candado.tryLock(100):
        log.info("mibarra ya está abierta: no abro otra")
        return
    app.candado = candado
    sw.marcar_instancia()

    log.info("Iniciando mibarra %s (%s)", VERSION, "exe" if rutas.ES_EXE else "Python")
    ajustes = config.cargar()
    estilo.poner_acento(ajustes.get("color_acento", "#7aa2ff"))
    app.setStyleSheet(estilo.hoja_global())
    app.setFont(estilo.fuente(13))

    dock = Dock(ajustes)
    dock.show()
    dock.iniciar()
    lanzar_guardian()

    # Pase lo que pase al cerrar, devolver la barra de Windows
    app.aboutToQuit.connect(dock.limpiar)
    atexit.register(dock.limpiar)

    # Ctrl+C en la consola cierra la barra de forma ordenada.
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    latido = QTimer()
    latido.timeout.connect(lambda: None)
    latido.start(300)

    # Primera vez: bienvenida. Si no: revisar si hay versión nueva (en segundo plano)
    if not ajustes.get("bienvenida_vista"):
        QTimer.singleShot(600, dock.mostrar_bienvenida)
    elif ajustes.get("buscar_actualizaciones", True):
        QTimer.singleShot(8000, dock.revisar_actualizaciones)

    codigo = app.exec()
    log.info("mibarra se cerró normalmente")
    sys.exit(codigo)


if __name__ == "__main__":
    main()

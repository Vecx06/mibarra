"""
main.py — el punto de partida de mibarra.

    python main.py              -> abre la barra
    python main.py --restaurar  -> arregla la barra de Windows si mibarra se cerró mal
"""

import atexit
import os
import signal
import sys
import tempfile
import traceback
from datetime import datetime
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
sys.path.insert(0, str(CARPETA))   # para que los "import" encuentren los otros archivos


def registrar_error(tipo, valor, rastro):
    """
    Si algo falla, NO cerramos la barra de golpe (dejaría la barra de Windows escondida):
    anotamos el error en error.log y seguimos.
    """
    texto = "".join(traceback.format_exception(tipo, valor, rastro))
    print(texto, file=sys.stderr)
    try:
        with open(CARPETA / "error.log", "a", encoding="utf-8") as archivo:
            archivo.write(f"\n--- {datetime.now():%Y-%m-%d %H:%M:%S} ---\n{texto}")
    except OSError:
        pass


def main():
    if "--restaurar" in sys.argv:
        import sistema_windows as sw
        sw.BarraWindows.restaurar_desde_archivo()
        print("Listo: la barra de tareas de Windows volvió a la normalidad.")
        return

    sys.excepthook = registrar_error

    from PyQt6.QtCore import QLockFile, QTimer
    from PyQt6.QtWidgets import QApplication

    import config
    import estilo
    from dock import Dock

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # Solo una mibarra a la vez
    candado = QLockFile(os.path.join(tempfile.gettempdir(), "mibarra.lock"))
    if not candado.tryLock(100):
        print("mibarra ya está abierta.")
        return
    app.candado = candado

    ajustes = config.cargar()
    estilo.poner_acento(ajustes.get("color_acento", "#7aa2ff"))
    app.setStyleSheet(estilo.hoja_global())
    app.setFont(estilo.fuente(13))

    dock = Dock(ajustes)
    dock.show()
    dock.iniciar()

    # Pase lo que pase al cerrar, devolver la barra de Windows
    app.aboutToQuit.connect(dock.limpiar)
    atexit.register(dock.limpiar)

    # Ctrl+C en la consola cierra la barra de forma ordenada.
    # (El timer "despierta" a Python cada 0,3 s para que pueda notar el Ctrl+C.)
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    latido = QTimer()
    latido.timeout.connect(lambda: None)
    latido.start(300)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

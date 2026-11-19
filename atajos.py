"""
atajos.py — atajos de teclado que funcionan en cualquier parte de Windows.

Windows tiene una función, RegisterHotKey, que le dice: "cuando alguien apriete esta
combinación, avísame a mí". Los avisos llegan a un "hilo" que se queda esperando; ese hilo
le pasa el aviso a la barra con una señal de Qt.

Los atajos se escriben como texto: "alt+espacio", "ctrl+alt+b", "win+shift+k"...
"""

import threading

from PyQt6.QtCore import QObject, pyqtSignal

import sistema_windows as sw
from registro import log

MODIFICADORES = {"alt": 0x0001, "ctrl": 0x0002, "control": 0x0002, "shift": 0x0004, "mayus": 0x0004,
                 "win": 0x0008, "windows": 0x0008}
TECLAS = {"espacio": 0x20, "space": 0x20, "enter": 0x0D, "intro": 0x0D, "tab": 0x09, "esc": 0x1B}
MOD_NOREPEAT = 0x4000
WM_HOTKEY, WM_QUIT = 0x0312, 0x0012


def interpretar(texto):
    """'ctrl+alt+b' -> (0x0003, 0x42). Lanza ValueError si no se entiende."""
    partes = [p.strip().lower() for p in texto.replace(" ", "").split("+") if p.strip()]
    if len(partes) < 2:
        raise ValueError("Un atajo necesita al menos una tecla especial y una tecla")
    mods = 0
    for p in partes[:-1]:
        if p not in MODIFICADORES:
            raise ValueError(f"No conozco la tecla {p!r}")
        mods |= MODIFICADORES[p]
    tecla = partes[-1]
    if tecla in TECLAS:
        codigo = TECLAS[tecla]
    elif len(tecla) == 1 and tecla.isalnum():
        codigo = ord(tecla.upper())
    elif tecla.startswith("f") and tecla[1:].isdigit() and 1 <= int(tecla[1:]) <= 12:
        codigo = 0x70 + int(tecla[1:]) - 1
    else:
        raise ValueError(f"No conozco la tecla {tecla!r}")
    return mods, codigo


def bonito(texto):
    """'ctrl+alt+b' -> 'Ctrl + Alt + B' (para mostrar en pantalla)."""
    nombres = {"espacio": "Espacio", "space": "Espacio", "win": "Win", "ctrl": "Ctrl", "alt": "Alt",
               "shift": "Shift"}
    return " + ".join(nombres.get(p.lower(), p.upper()) for p in texto.replace(" ", "").split("+") if p)


class Atajos(QObject):
    activado = pyqtSignal(str)        # entrega el NOMBRE del atajo, ej. "buscador"

    def __init__(self):
        super().__init__()
        self._hilo = None
        self._id_hilo = None
        self.fallidos = []             # atajos que Windows no dejó usar (otro programa ya los tiene)

    def empezar(self, atajos):
        """atajos = {"buscador": "alt+espacio", "barra": "ctrl+alt+b"}"""
        self.detener()
        if not sw.ES_WINDOWS:
            return
        listo = threading.Event()
        self.fallidos = []

        def trabajo():
            import ctypes
            from ctypes import wintypes
            self._id_hilo = sw.kernel32.GetCurrentThreadId()
            registrados = {}
            for numero, (nombre, texto) in enumerate(atajos.items(), start=1):
                try:
                    mods, tecla = interpretar(texto)
                except ValueError as error:
                    log.warning("Atajo %s inválido (%s): %s", nombre, texto, error)
                    self.fallidos.append(nombre)
                    continue
                if sw.user32.RegisterHotKey(None, numero, mods | MOD_NOREPEAT, tecla):
                    registrados[numero] = nombre
                else:
                    log.warning("Windows no dejó usar el atajo %s (%s): otro programa ya lo usa", texto, nombre)
                    self.fallidos.append(nombre)
            listo.set()
            mensaje = wintypes.MSG()
            while sw.user32.GetMessageW(ctypes.byref(mensaje), None, 0, 0) > 0:
                if mensaje.message == WM_HOTKEY and mensaje.wParam in registrados:
                    try:
                        self.activado.emit(registrados[mensaje.wParam])
                    except RuntimeError:
                        break
            for numero in registrados:
                sw.user32.UnregisterHotKey(None, numero)

        self._hilo = threading.Thread(target=trabajo, daemon=True)
        self._hilo.start()
        listo.wait(2)

    def detener(self):
        if self._hilo is not None and self._id_hilo:
            sw.user32.PostThreadMessageW(self._id_hilo, WM_QUIT, 0, 0)
            self._hilo.join(timeout=2)
        self._hilo = None
        self._id_hilo = None

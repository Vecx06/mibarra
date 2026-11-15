"""
sistema_windows.py — todo lo que habla DIRECTAMENTE con Windows.

Python no trae funciones para "listar ventanas abiertas" o "esconder la barra de tareas".
Pero Windows sí las tiene, dentro de unos archivos llamados DLL (user32.dll, shell32.dll...).
Con la librería `ctypes` (viene con Python) podemos llamar a esas funciones de Windows.

Palabras que vas a ver mucho:
  - HWND   = "handle de ventana": un número que identifica a una ventana.
  - PID    = número que identifica a un programa en ejecución (proceso).
  - AppBar = una barra pegada al borde de la pantalla que "reserva" su espacio
             (la barra de tareas de Windows es una AppBar).

Si este archivo se ejecuta fuera de Windows (por ejemplo para probar en Linux),
todas las funciones devuelven valores vacíos en vez de fallar.
"""

import json
import os
import sys
from collections import namedtuple
from pathlib import Path

ES_WINDOWS = sys.platform == "win32"

# Una ventana abierta: su número, su título, la ruta de su programa y el número de proceso
Ventana = namedtuple("Ventana", "hwnd titulo exe pid")

# Aquí guardamos cómo estaba la barra de Windows antes de tocarla (para poder dejarla igual)
ARCHIVO_ESTADO = Path(__file__).resolve().parent / "estado_barra_windows.json"

# ----------------------------------------------------------------------------
# Constantes de Windows (son números fijos definidos por Microsoft)
# ----------------------------------------------------------------------------
GW_OWNER = 4
GWL_EXSTYLE = -20
GWL_STYLE = -16
WS_CAPTION = 0x00C00000
# Respuestas de SHQueryUserNotificationState
QUNS_BUSY, QUNS_RUNNING_D3D_FULL_SCREEN, QUNS_PRESENTATION_MODE = 2, 3, 4
WS_EX_TOOLWINDOW = 0x00000080
SW_HIDE, SW_SHOW, SW_MINIMIZE, SW_RESTORE = 0, 5, 6, 9
WM_CLOSE = 0x0010
WM_USER = 0x0400
DWMWA_CLOAKED = 14
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND = 2
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
MONITOR_DEFAULTTONEAREST = 2

# Mensajes para las AppBar
ABM_NEW, ABM_REMOVE, ABM_QUERYPOS, ABM_SETPOS, ABM_GETSTATE, ABM_SETSTATE = 0, 1, 2, 3, 4, 10
ABS_AUTOHIDE, ABS_ALWAYSONTOP = 1, 2
ABE_TOP, ABE_BOTTOM = 1, 3

# Teclas (códigos "VK" = virtual key)
KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP = 0x1, 0x2
VK_MENU = 0x12          # Alt
VK_LWIN = 0x5B          # tecla Windows
VK_SHIFT = 0x10
VK_SNAPSHOT = 0x2C      # tecla Imprimir pantalla
VK_A = 0x41
VK_D = 0x44
VK_S = 0x53
VK_X = 0x58
VK_VOLUME_MUTE, VK_VOLUME_DOWN, VK_VOLUME_UP = 0xAD, 0xAE, 0xAF
VK_MEDIA_NEXT, VK_MEDIA_PREV, VK_MEDIA_PLAY_PAUSE = 0xB0, 0xB1, 0xB3
_TECLAS_EXTENDIDAS = {VK_LWIN, VK_SNAPSHOT, VK_VOLUME_MUTE, VK_VOLUME_DOWN, VK_VOLUME_UP,
                      VK_MEDIA_NEXT, VK_MEDIA_PREV, VK_MEDIA_PLAY_PAUSE}

# Ventanas "de sistema" que no queremos mostrar como apps
CLASES_IGNORADAS = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
                    "Windows.UI.Core.CoreWindow"}


# ----------------------------------------------------------------------------
# Preparar ctypes: decirle a Python cómo son las funciones de Windows
# (qué reciben y qué devuelven). Sin esto, en Windows de 64 bits pueden fallar.
# ----------------------------------------------------------------------------
if ES_WINDOWS:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    dwmapi = ctypes.WinDLL("dwmapi")

    # Tipo de función que Windows llama una vez por cada ventana (para EnumWindows)
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    class APPBARDATA(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND),
                    ("uCallbackMessage", wintypes.UINT), ("uEdge", wintypes.UINT),
                    ("rc", wintypes.RECT), ("lParam", wintypes.LPARAM)]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

    class ACCENTPOLICY(ctypes.Structure):
        _fields_ = [("AccentState", ctypes.c_int), ("AccentFlags", ctypes.c_int),
                    ("GradientColor", ctypes.c_uint), ("AnimationId", ctypes.c_int)]

    class WINCOMPATTRDATA(ctypes.Structure):
        _fields_ = [("Attribute", ctypes.c_int), ("Data", ctypes.c_void_p),
                    ("SizeOfData", ctypes.c_size_t)]

    def _firmar(funcion, argumentos, retorno=wintypes.BOOL):
        funcion.argtypes = argumentos
        funcion.restype = retorno

    H = wintypes.HWND
    _firmar(user32.EnumWindows, [WNDENUMPROC, wintypes.LPARAM])
    _firmar(user32.IsWindowVisible, [H])
    _firmar(user32.IsIconic, [H])
    _firmar(user32.IsZoomed, [H])
    _firmar(user32.GetWindowTextLengthW, [H], ctypes.c_int)
    _firmar(user32.GetWindowTextW, [H, wintypes.LPWSTR, ctypes.c_int], ctypes.c_int)
    _firmar(user32.GetClassNameW, [H, wintypes.LPWSTR, ctypes.c_int], ctypes.c_int)
    _firmar(user32.GetWindow, [H, wintypes.UINT], H)
    _firmar(user32.GetWindowLongW, [H, ctypes.c_int], wintypes.LONG)
    _firmar(user32.GetWindowThreadProcessId, [H, ctypes.POINTER(wintypes.DWORD)], wintypes.DWORD)
    _firmar(user32.ShowWindow, [H, ctypes.c_int])
    _firmar(user32.SetForegroundWindow, [H])
    _firmar(user32.GetForegroundWindow, [], H)
    _firmar(user32.PostMessageW, [H, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM])
    _firmar(user32.keybd_event, [ctypes.c_ubyte, ctypes.c_ubyte, wintypes.DWORD, ctypes.c_size_t], None)
    _firmar(user32.SendMessageTimeoutW, [H, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
                                         wintypes.UINT, wintypes.UINT, ctypes.c_void_p], ctypes.c_size_t)
    _firmar(user32.FindWindowW, [wintypes.LPCWSTR, wintypes.LPCWSTR], H)
    _firmar(user32.FindWindowExW, [H, H, wintypes.LPCWSTR, wintypes.LPCWSTR], H)
    _firmar(user32.GetWindowRect, [H, ctypes.POINTER(wintypes.RECT)])
    _firmar(user32.MonitorFromWindow, [H, wintypes.DWORD], wintypes.HMONITOR)
    _firmar(user32.GetMonitorInfoW, [wintypes.HMONITOR, ctypes.POINTER(MONITORINFO)])
    _firmar(kernel32.OpenProcess, [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE)
    _firmar(kernel32.QueryFullProcessImageNameW,
            [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)])
    _firmar(kernel32.CloseHandle, [wintypes.HANDLE])
    _firmar(shell32.SHAppBarMessage, [wintypes.DWORD, ctypes.POINTER(APPBARDATA)], ctypes.c_size_t)
    _firmar(shell32.SHQueryUserNotificationState, [ctypes.POINTER(ctypes.c_int)], ctypes.c_long)
    _firmar(dwmapi.DwmGetWindowAttribute, [H, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD], ctypes.c_long)
    _firmar(dwmapi.DwmSetWindowAttribute, [H, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD], ctypes.c_long)
    # Esta función no está documentada oficialmente; si no existe, el vidrio simplemente no se usa
    _SetWindowCompositionAttribute = getattr(user32, "SetWindowCompositionAttribute", None)
    if _SetWindowCompositionAttribute is not None:
        _firmar(_SetWindowCompositionAttribute, [H, ctypes.POINTER(WINCOMPATTRDATA)])


def es_windows_11():
    return ES_WINDOWS and sys.getwindowsversion().build >= 22000


# ----------------------------------------------------------------------------
# Ventanas abiertas
# ----------------------------------------------------------------------------
def _titulo(hwnd):
    largo = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(largo + 1)
    user32.GetWindowTextW(hwnd, buffer, largo + 1)
    return buffer.value


def _clase(hwnd):
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, 256)
    return buffer.value


def pid_de(hwnd):
    """Número del proceso (programa) dueño de la ventana."""
    if not ES_WINDOWS or not hwnd:
        return 0
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def es_mia(hwnd):
    """¿Esta ventana es de mibarra?"""
    return pid_de(hwnd) == os.getpid()


_cache_exe = {}


def ruta_exe(pid):
    """Ruta completa del .exe de un proceso, por ejemplo C:\\...\\chrome.exe"""
    if pid in _cache_exe:
        return _cache_exe[pid]
    if len(_cache_exe) > 500:   # que el caché no crezca para siempre
        _cache_exe.clear()
    ruta = ""
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if h:
        buffer = ctypes.create_unicode_buffer(1024)
        tamano = wintypes.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h, 0, buffer, ctypes.byref(tamano)):
            ruta = buffer.value
        kernel32.CloseHandle(h)
    _cache_exe[pid] = ruta
    return ruta


def _oculta_por_dwm(hwnd):
    """Windows a veces tiene ventanas 'invisibles pero visibles' (en otro escritorio, en segundo plano)."""
    valor = ctypes.c_int(0)
    dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(valor), ctypes.sizeof(valor))
    return valor.value != 0


def listar_ventanas():
    """Devuelve una lista de Ventana con las apps abiertas (más o menos las mismas que muestra Alt+Tab)."""
    if not ES_WINDOWS:
        return []
    resultado = []
    mi_pid = os.getpid()

    def revisar(hwnd, _):
        # Windows llama a esta función una vez por CADA ventana que existe.
        # Devolver True = "sigue con la siguiente".
        if not user32.IsWindowVisible(hwnd):
            return True
        if user32.GetWindowTextLengthW(hwnd) == 0:
            return True
        if user32.GetWindow(hwnd, GW_OWNER):          # ventanas "hijas" (diálogos)
            return True
        if user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW:   # paletas, popups
            return True
        if _oculta_por_dwm(hwnd):
            return True
        if _clase(hwnd) in CLASES_IGNORADAS:
            return True
        pid = pid_de(hwnd)
        if pid == mi_pid:
            return True
        resultado.append(Ventana(hwnd, _titulo(hwnd), ruta_exe(pid), pid))
        return True

    user32.EnumWindows(WNDENUMPROC(revisar), 0)
    return resultado


def ventana_activa():
    """La ventana que está al frente ahora mismo."""
    if not ES_WINDOWS:
        return None
    return user32.GetForegroundWindow()


def esta_minimizada(hwnd):
    return ES_WINDOWS and bool(user32.IsIconic(hwnd))


def activar(hwnd):
    """Trae una ventana al frente (y la restaura si estaba minimizada)."""
    if not ES_WINDOWS:
        return
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    if not user32.SetForegroundWindow(hwnd) or user32.GetForegroundWindow() != hwnd:
        # Windows a veces no deja que otro programa cambie la ventana activa.
        # Truco conocido: "tocar" la tecla Alt y volver a intentarlo.
        user32.keybd_event(VK_MENU, 0, 0, 0)
        user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
        user32.SetForegroundWindow(hwnd)


def minimizar(hwnd):
    if ES_WINDOWS:
        user32.ShowWindow(hwnd, SW_MINIMIZE)


def cerrar(hwnd):
    """Le pide a la ventana que se cierre (como apretar la X; la app puede preguntar si guardar)."""
    if ES_WINDOWS:
        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)


def presionar_teclas(*codigos):
    """Simula apretar teclas juntas, por ejemplo presionar_teclas(VK_LWIN, VK_D) = Windows+D."""
    if not ES_WINDOWS:
        return
    for c in codigos:                     # bajar todas
        bandera = KEYEVENTF_EXTENDEDKEY if c in _TECLAS_EXTENDIDAS else 0
        user32.keybd_event(c, 0, bandera, 0)
    for c in reversed(codigos):           # soltarlas al revés
        bandera = KEYEVENTF_EXTENDEDKEY if c in _TECLAS_EXTENDIDAS else 0
        user32.keybd_event(c, 0, bandera | KEYEVENTF_KEYUP, 0)


def hay_pantalla_completa():
    """
    ¿Hay algo en pantalla completa? (video de YouTube, juego, presentación...)

    Usamos dos métodos:
      1. Le preguntamos a Windows directamente (SHQueryUserNotificationState).
         Es lo mismo que usa Windows para no mostrar notificaciones mientras ves un video.
      2. Revisamos si la ventana del frente tapa TODO el monitor.
    """
    if not ES_WINDOWS:
        return False

    # Método 1
    estado = ctypes.c_int(0)
    if shell32.SHQueryUserNotificationState(ctypes.byref(estado)) == 0:
        if estado.value in (QUNS_BUSY, QUNS_RUNNING_D3D_FULL_SCREEN, QUNS_PRESENTATION_MODE):
            hwnd = user32.GetForegroundWindow()
            if hwnd and not es_mia(hwnd) and _clase(hwnd) not in CLASES_IGNORADAS:
                return True

    # Método 2
    hwnd = user32.GetForegroundWindow()
    if not hwnd or _clase(hwnd) in CLASES_IGNORADAS or es_mia(hwnd):
        return False
    # Ojo: un navegador en pantalla completa puede seguir marcado como "maximizado".
    # La diferencia es que una ventana maximizada NORMAL tiene barra de título (WS_CAPTION).
    estilo_ventana = user32.GetWindowLongW(hwnd, GWL_STYLE)
    if user32.IsZoomed(hwnd) and (estilo_ventana & WS_CAPTION) == WS_CAPTION:
        return False
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    monitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        return False
    m = info.rcMonitor
    return r.left <= m.left and r.top <= m.top and r.right >= m.right and r.bottom >= m.bottom


# ----------------------------------------------------------------------------
# Aspecto: vidrio borroso y esquinas redondeadas
# ----------------------------------------------------------------------------
def aplicar_vidrio(hwnd, alfa=0x99, r=20, g=20, b=26):
    """Pone fondo 'acrílico' (borroso) detrás de la ventana. Devuelve True si funcionó."""
    if not ES_WINDOWS or _SetWindowCompositionAttribute is None:
        return False
    acento = ACCENTPOLICY()
    acento.AccentState = 4                       # 4 = acrílico borroso
    acento.GradientColor = (alfa << 24) | (b << 16) | (g << 8) | r   # el color va al revés: AABBGGRR
    datos = WINCOMPATTRDATA()
    datos.Attribute = 19                         # 19 = "política de acento"
    datos.Data = ctypes.addressof(acento)
    datos.SizeOfData = ctypes.sizeof(acento)
    return bool(_SetWindowCompositionAttribute(hwnd, ctypes.byref(datos)))


def quitar_vidrio(hwnd):
    """Vuelve al fondo normal (sin borroso)."""
    if not ES_WINDOWS or _SetWindowCompositionAttribute is None:
        return
    acento = ACCENTPOLICY()
    acento.AccentState = 0                       # 0 = desactivado
    datos = WINCOMPATTRDATA()
    datos.Attribute = 19
    datos.Data = ctypes.addressof(acento)
    datos.SizeOfData = ctypes.sizeof(acento)
    _SetWindowCompositionAttribute(hwnd, ctypes.byref(datos))


def redondear_esquinas(hwnd):
    """En Windows 11, pide esquinas redondeadas para la ventana."""
    if es_windows_11():
        valor = ctypes.c_int(DWMWCP_ROUND)
        dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
                                     ctypes.byref(valor), ctypes.sizeof(valor))


# ----------------------------------------------------------------------------
# La barra de tareas de Windows: esconderla y devolverla
# ----------------------------------------------------------------------------
class BarraWindows:
    """
    Para esconder la barra de Windows hacemos dos cosas:
      1. La ponemos en "ocultar automáticamente" (así deja de ocupar espacio).
      2. La escondemos del todo (así no aparece al tocar el borde).
    Antes de tocarla guardamos cómo estaba, en un archivo, para dejarla IGUAL al salir
    (incluso si mibarra se cerró mal: para eso está restaurar_barra.bat).
    """

    def __init__(self):
        self.oculta = False     # ¿la escondimos nosotros?
        self.pausada = False    # ¿el usuario pidió verla un rato (botón bandeja)?
        self._estado_original = None

    @staticmethod
    def _ventanas():
        if not ES_WINDOWS:
            return []
        lista = []
        principal = user32.FindWindowW("Shell_TrayWnd", None)
        if principal:
            lista.append(principal)
        siguiente = None   # barras de otros monitores
        while True:
            siguiente = user32.FindWindowExW(None, siguiente, "Shell_SecondaryTrayWnd", None)
            if not siguiente:
                break
            lista.append(siguiente)
        return lista

    @staticmethod
    def _leer_estado():
        datos = APPBARDATA()
        datos.cbSize = ctypes.sizeof(APPBARDATA)
        return int(shell32.SHAppBarMessage(ABM_GETSTATE, ctypes.byref(datos)))

    @staticmethod
    def _poner_estado(estado):
        datos = APPBARDATA()
        datos.cbSize = ctypes.sizeof(APPBARDATA)
        datos.hWnd = user32.FindWindowW("Shell_TrayWnd", None)
        datos.lParam = estado
        shell32.SHAppBarMessage(ABM_SETSTATE, ctypes.byref(datos))

    def ocultar(self):
        if not ES_WINDOWS:
            return
        if self._estado_original is None:
            # Si quedó un archivo de una vez anterior (mibarra se cerró mal), ese es el estado real
            try:
                self._estado_original = json.loads(ARCHIVO_ESTADO.read_text())["estado_original"]
            except (OSError, ValueError, KeyError):
                self._estado_original = self._leer_estado()
                try:
                    ARCHIVO_ESTADO.write_text(json.dumps({"estado_original": self._estado_original}))
                except OSError:
                    pass
        self._poner_estado(ABS_AUTOHIDE)
        for h in self._ventanas():
            user32.ShowWindow(h, SW_HIDE)
        self.oculta = True
        self.pausada = False

    def vigilar(self):
        """Windows a veces vuelve a mostrar su barra (por ejemplo al apretar la tecla Windows)."""
        if ES_WINDOWS and self.oculta and not self.pausada:
            for h in self._ventanas():
                if user32.IsWindowVisible(h):
                    user32.ShowWindow(h, SW_HIDE)

    def mostrar_un_rato(self):
        if ES_WINDOWS and self.oculta:
            self.pausada = True
            for h in self._ventanas():
                user32.ShowWindow(h, SW_SHOW)

    def volver_a_ocultar(self):
        if ES_WINDOWS and self.oculta:
            self.pausada = False
            for h in self._ventanas():
                user32.ShowWindow(h, SW_HIDE)

    def restaurar(self):
        """Deja la barra de Windows exactamente como estaba."""
        if not ES_WINDOWS:
            return
        for h in self._ventanas():
            user32.ShowWindow(h, SW_SHOW)
        if self._estado_original is not None:
            self._poner_estado(self._estado_original)
            self._estado_original = None
        try:
            ARCHIVO_ESTADO.unlink()
        except OSError:
            pass
        self.oculta = False
        self.pausada = False

    @classmethod
    def restaurar_desde_archivo(cls):
        """Para restaurar_barra.bat: arregla la barra aunque mibarra no esté abierta."""
        barra = cls()
        try:
            barra._estado_original = json.loads(ARCHIVO_ESTADO.read_text())["estado_original"]
        except (OSError, ValueError, KeyError):
            barra._estado_original = ABS_ALWAYSONTOP   # = barra normal, siempre visible
        barra.restaurar()


# ----------------------------------------------------------------------------
# Reservar espacio (registrarse como AppBar)
# ----------------------------------------------------------------------------
class EspacioReservado:
    """Le avisa a Windows: 'esta franja de la pantalla es mía, no pongas ventanas maximizadas aquí'."""

    def __init__(self, hwnd):
        self.hwnd = hwnd
        self.activo = False

    def _datos(self):
        d = APPBARDATA()
        d.cbSize = ctypes.sizeof(APPBARDATA)
        d.hWnd = self.hwnd
        d.uCallbackMessage = WM_USER + 1
        return d

    def reservar(self, abajo, pantalla, grosor):
        """
        pantalla = (izq, arriba, der, abajo) en píxeles REALES de la pantalla.
        Devuelve la franja que Windows nos dio, o None si no estamos en Windows.
        """
        if not ES_WINDOWS:
            return None
        d = self._datos()
        if not self.activo:
            shell32.SHAppBarMessage(ABM_NEW, ctypes.byref(d))
            self.activo = True
        d.uEdge = ABE_BOTTOM if abajo else ABE_TOP
        d.rc.left, d.rc.top, d.rc.right, d.rc.bottom = pantalla
        # 1) Preguntamos: "¿dónde puedo ponerme?" (Windows corrige si hay otra barra)
        shell32.SHAppBarMessage(ABM_QUERYPOS, ctypes.byref(d))
        # 2) Ajustamos el grosor y confirmamos
        if abajo:
            d.rc.top = d.rc.bottom - grosor
        else:
            d.rc.bottom = d.rc.top + grosor
        shell32.SHAppBarMessage(ABM_SETPOS, ctypes.byref(d))
        return (d.rc.left, d.rc.top, d.rc.right, d.rc.bottom)

    def liberar(self):
        if ES_WINDOWS and self.activo:
            d = self._datos()
            shell32.SHAppBarMessage(ABM_REMOVE, ctypes.byref(d))
            self.activo = False


# ----------------------------------------------------------------------------
# Iniciar con Windows (se guarda en el registro del usuario, no necesita permisos de admin)
# ----------------------------------------------------------------------------
_RUTA_RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
_NOMBRE_INICIO = "mibarra"


def inicio_automatico_activo():
    if not ES_WINDOWS:
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUTA_RUN) as clave:
            winreg.QueryValueEx(clave, _NOMBRE_INICIO)
            return True
    except OSError:
        return False


def poner_inicio_automatico(activar_inicio, comando):
    if not ES_WINDOWS:
        return
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUTA_RUN, 0, winreg.KEY_SET_VALUE) as clave:
        if activar_inicio:
            winreg.SetValueEx(clave, _NOMBRE_INICIO, 0, winreg.REG_SZ, comando)
        else:
            try:
                winreg.DeleteValue(clave, _NOMBRE_INICIO)
            except FileNotFoundError:
                pass


# ----------------------------------------------------------------------------
# Tema claro / oscuro de Windows (se guarda en el registro del usuario)
# ----------------------------------------------------------------------------
_RUTA_TEMA = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"


def windows_usa_tema_claro():
    if not ES_WINDOWS:
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUTA_TEMA) as clave:
            valor, _ = winreg.QueryValueEx(clave, "AppsUseLightTheme")
            return bool(valor)
    except OSError:
        return False


def poner_tema_windows(claro):
    """Cambia Windows entero a modo claro u oscuro (apps y barra de sistema)."""
    if not ES_WINDOWS:
        return
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUTA_TEMA, 0, winreg.KEY_SET_VALUE) as clave:
        winreg.SetValueEx(clave, "AppsUseLightTheme", 0, winreg.REG_DWORD, int(claro))
        winreg.SetValueEx(clave, "SystemUsesLightTheme", 0, winreg.REG_DWORD, int(claro))
    # Avisarle a todas las ventanas que el tema cambió
    texto = ctypes.c_wchar_p("ImmersiveColorSet")
    user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, ctypes.cast(texto, ctypes.c_void_p).value,
                               0x0002, 200, None)


# ----------------------------------------------------------------------------
# Wi-Fi: nombre de la red conectada (usa el comando "netsh" de Windows)
# ----------------------------------------------------------------------------
def red_wifi():
    """Devuelve el nombre (SSID) de la red Wi-Fi conectada, o "" si no hay."""
    if not ES_WINDOWS:
        return ""
    import subprocess
    try:
        salida = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True,
                                timeout=5, creationflags=0x08000000).stdout   # 0x08000000 = sin ventana negra
    except (OSError, subprocess.TimeoutExpired):
        return ""
    for linea in salida.decode("cp850", errors="ignore").splitlines():
        linea = linea.strip()
        if linea.startswith("SSID") and ":" in linea:     # ojo: no confundir con "BSSID"
            return linea.split(":", 1)[1].strip()
    return ""

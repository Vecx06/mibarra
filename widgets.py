"""
widgets.py — las "cajitas" que van dentro de la barra.

Todas se construyen a partir de dos clases base:
  - Caja: un rectángulo redondeado que se ilumina con el mouse y avisa cuando le haces clic.
  - Tile: una Caja con un título chico arriba, un valor grande abajo y (opcional) una barrita de progreso.

Cada widget tiene un método actualizar(), que la barra llama una vez por segundo.
Los que necesitan internet o tardan (clima, música) trabajan en un HILO aparte
para no congelar la barra mientras esperan.
"""

import asyncio
import json
import os
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime

import psutil
from PyQt6.QtCore import QDate, QLocale, QObject, QPoint, QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFontMetrics, QPainter, QPolygonF, QTextCharFormat
from PyQt6.QtWidgets import (QApplication, QCalendarWidget, QFrame, QLabel, QMenu,
                             QVBoxLayout, QWidget, QHBoxLayout)

import estilo
import sistema_windows as sw

# La info de "qué canción suena" necesita un paquete extra (winrt). Si no está, igual
# funcionan los botones de música; solo no se ve el nombre de la canción.
try:
    import winrt.windows.foundation  # noqa: F401  (necesario para poder "esperar" respuestas de Windows)
    from winrt.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager as GestorMedios)
    HAY_INFO_MUSICA = True
except Exception:
    GestorMedios = None
    HAY_INFO_MUSICA = False

DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
DIAS_LARGOS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
MESES_LARGOS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
                "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
LIMITE_ALERTA = 85


# =============================================================================
# Utilidades
# =============================================================================
def crear_menu(padre=None):
    """Un menú de clic derecho con esquinas redondeadas."""
    menu = QMenu(padre)
    menu.setWindowFlags(menu.windowFlags() | Qt.WindowType.FramelessWindowHint
                        | Qt.WindowType.NoDropShadowWindowHint)
    menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    return menu


def recortar(texto, fuente, ancho):
    """Si el texto no cabe, lo corta y le pone '…' al final."""
    return QFontMetrics(fuente).elidedText(texto, Qt.TextElideMode.ElideRight, max(0, int(ancho)))


def abrir(ruta):
    """Abre un programa, archivo o enlace como si le hicieras doble clic."""
    try:
        os.startfile(ruta)   # solo existe en Windows
    except Exception as error:
        print(f"[mibarra] No pude abrir {ruta}: {error}")


class TrabajoRepetido(QObject):
    """
    Ejecuta una función cada X segundos en un HILO aparte y entrega el resultado con una señal.
    (Una "señal" de Qt es un aviso; Qt se encarga de pasarlo de forma segura al hilo de la barra.)
    """
    resultado = pyqtSignal(object)

    def __init__(self, funcion, cada, cada_si_falla=None):
        super().__init__()
        self.funcion = funcion
        self.cada = cada
        self.cada_si_falla = cada_si_falla or cada
        self.activo = True

    def detener(self):
        self.activo = False

    def empezar(self):
        threading.Thread(target=self._bucle, daemon=True).start()

    def _bucle(self):
        while self.activo:
            try:
                dato = self.funcion()
                espera = self.cada
            except Exception:
                dato = None
                espera = self.cada_si_falla
            try:
                self.resultado.emit(dato)
            except RuntimeError:     # la barra ya se cerró
                return
            # Dormir de a poquito, para poder detenernos rápido si nos lo piden
            fin = time.monotonic() + espera
            while self.activo and time.monotonic() < fin:
                time.sleep(0.25)


# =============================================================================
# Clases base
# =============================================================================
class Caja(QWidget):
    clic = pyqtSignal()
    clic_derecho = pyqtSignal(QPoint)

    def __init__(self, radio=10):
        super().__init__()
        self.radio = radio
        self._hover = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # El mouse entra / sale -> cambiamos el color de fondo
    def enterEvent(self, evento):
        self._hover = True
        self.update()
        super().enterEvent(evento)

    def leaveEvent(self, evento):
        self._hover = False
        self.update()
        super().leaveEvent(evento)

    def mouseReleaseEvent(self, evento):
        if (evento.button() == Qt.MouseButton.LeftButton
                and self.rect().contains(evento.position().toPoint())):
            self.clic.emit()

    def contextMenuEvent(self, evento):
        self.clic_derecho.emit(evento.globalPos())
        evento.accept()   # "ya lo manejé yo": así no sale también el menú de la barra

    def paintEvent(self, evento):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.pintar_fondo(p)
        self.pintar(p)
        p.end()

    def pintar_fondo(self, p):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(estilo.CAJA_HOVER if self._hover else estilo.CAJA)
        p.drawRoundedRect(QRectF(self.rect()), self.radio, self.radio)

    def pintar(self, p):
        """Cada widget dibuja aquí su contenido."""


class Tile(Caja):
    def __init__(self, ancho, alto, titulo="", valor="", centrado=False):
        super().__init__()
        self.titulo = titulo
        self.valor = valor
        self.progreso = None
        self.alerta = False
        self.centrado = centrado
        self.setFixedSize(ancho, alto)

    def poner(self, titulo=None, valor=None, progreso=None, alerta=False):
        if titulo is not None:
            self.titulo = titulo
        if valor is not None:
            self.valor = valor
        self.progreso = progreso
        self.alerta = alerta
        self.update()   # "vuelve a dibujarte"

    def pintar(self, p):
        ancho = self.width() - 20
        horizontal = Qt.AlignmentFlag.AlignHCenter if self.centrado else Qt.AlignmentFlag.AlignLeft
        color_valor = estilo.ROJO if self.alerta else estilo.TEXTO

        if not self.titulo:   # solo un símbolo grande al centro (volumen, bandeja)
            p.setFont(estilo.fuente(17))
            p.setPen(color_valor)
            p.drawText(QRectF(self.rect()), Qt.AlignmentFlag.AlignCenter, self.valor)
            return

        hay_barra = self.progreso is not None
        alto_total = 13 + 18 + (6 if hay_barra else 0)
        y = (self.height() - alto_total) / 2

        f_titulo = estilo.fuente(10)
        p.setFont(f_titulo)
        p.setPen(estilo.TEXTO_SUAVE)
        p.drawText(QRectF(10, y, ancho, 13), horizontal | Qt.AlignmentFlag.AlignVCenter,
                   recortar(self.titulo, f_titulo, ancho))
        y += 13

        f_valor = estilo.fuente(13, negrita=True)
        p.setFont(f_valor)
        p.setPen(color_valor)
        p.drawText(QRectF(10, y, ancho, 18), horizontal | Qt.AlignmentFlag.AlignVCenter,
                   recortar(self.valor, f_valor, ancho))
        y += 21

        if hay_barra:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 28))
            p.drawRoundedRect(QRectF(10, y, ancho, 3), 1.5, 1.5)
            lleno = ancho * max(0.0, min(100.0, self.progreso)) / 100
            p.setBrush(estilo.ROJO if self.alerta else estilo.ACENTO)
            p.drawRoundedRect(QRectF(10, y, lleno, 3), 1.5, 1.5)


# =============================================================================
# Widgets de datos del sistema
# =============================================================================
def abrir_administrador_tareas():
    abrir("taskmgr.exe")


class CpuTile(Tile):
    def __init__(self, alto):
        super().__init__(70, alto, "CPU", "—")
        psutil.cpu_percent(interval=None)   # primera medición "de calentamiento"
        self.setToolTip(f"Procesador · {psutil.cpu_count()} núcleos\nClic: Administrador de tareas")
        self.clic.connect(abrir_administrador_tareas)

    def actualizar(self):
        uso = psutil.cpu_percent(interval=None)
        self.poner(valor=f"{uso:.0f}%", progreso=uso, alerta=uso >= LIMITE_ALERTA)


class RamTile(Tile):
    def __init__(self, alto):
        super().__init__(70, alto, "RAM", "—")
        self.clic.connect(abrir_administrador_tareas)

    def actualizar(self):
        m = psutil.virtual_memory()
        gb = 1024 ** 3
        self.poner(valor=f"{m.percent:.0f}%", progreso=m.percent, alerta=m.percent >= LIMITE_ALERTA)
        self.setToolTip(f"Memoria: {m.used / gb:.1f} de {m.total / gb:.1f} GB\nClic: Administrador de tareas")


def _velocidad(bytes_por_segundo):
    b = max(0.0, bytes_por_segundo)
    if b < 1024:
        return f"{b:.0f} B/s"
    if b < 1024 ** 2:
        return f"{b / 1024:.0f} KB/s"
    return f"{b / 1024 ** 2:.1f} MB/s"


class RedTile(Tile):
    def __init__(self, alto):
        super().__init__(116, alto, "Red", "—")
        self._antes = None
        self.setToolTip("Velocidad de internet ahora mismo\n↓ bajada   ↑ subida")

    def actualizar(self):
        ahora = time.monotonic()
        c = psutil.net_io_counters()
        if self._antes:
            t0, recibidos, enviados = self._antes
            segundos = max(0.001, ahora - t0)
            baja = (c.bytes_recv - recibidos) / segundos
            sube = (c.bytes_sent - enviados) / segundos
            self.poner(titulo=f"Red · ↑ {_velocidad(sube)}", valor=f"↓ {_velocidad(baja)}")
        self._antes = (ahora, c.bytes_recv, c.bytes_sent)


class BateriaTile(Tile):
    def __init__(self, alto):
        super().__init__(78, alto, "Batería", "—")

    def actualizar(self):
        b = psutil.sensors_battery()
        if b is None:           # PC de escritorio: no tiene batería
            self.hide()
            return
        self.show()
        enchufado = bool(b.power_plugged)
        self.poner(valor=f"{b.percent:.0f}%{' ⚡' if enchufado else ''}",
                   progreso=b.percent, alerta=b.percent <= 20 and not enchufado)
        if enchufado:
            self.setToolTip("Cargando" if b.percent < 100 else "Carga completa")
        elif b.secsleft and b.secsleft > 0:
            h, m = divmod(int(b.secsleft) // 60, 60)
            self.setToolTip(f"Quedan aprox. {h} h {m} min")


# =============================================================================
# Reloj + calendario
# =============================================================================
class Calendario(QWidget):
    """Ventanita que aparece al hacer clic en el reloj."""

    def __init__(self):
        super().__init__(None, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.cerrado_en = 0.0

        fondo = QFrame(self)
        fondo.setObjectName("popup")
        capa_exterior = QVBoxLayout(self)
        capa_exterior.setContentsMargins(0, 0, 0, 0)
        capa_exterior.addWidget(fondo)

        capa = QVBoxLayout(fondo)
        capa.setContentsMargins(16, 14, 16, 12)
        self.fecha = QLabel()
        self.fecha.setFont(estilo.fuente(15, negrita=True))
        capa.addWidget(self.fecha)

        self.cal = QCalendarWidget()
        self.cal.setLocale(QLocale(QLocale.Language.Spanish, QLocale.Country.Chile))
        self.cal.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
        self.cal.setGridVisible(False)
        self.cal.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.cal.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.ShortDayNames)
        formato = QTextCharFormat()
        formato.setForeground(estilo.TEXTO)
        for dia in (Qt.DayOfWeek.Saturday, Qt.DayOfWeek.Sunday):   # sin fin de semana en rojo
            self.cal.setWeekdayTextFormat(dia, formato)
        self.cal.setMinimumSize(300, 220)
        capa.addWidget(self.cal)

    def mostrar_cerca_de(self, widget, hacia_arriba):
        hoy = datetime.now()
        self.fecha.setText(f"{DIAS_LARGOS[hoy.weekday()].capitalize()}, "
                           f"{hoy.day} de {MESES_LARGOS[hoy.month - 1]} de {hoy.year}")
        self.cal.setSelectedDate(QDate.currentDate())
        self.adjustSize()
        esquina = widget.mapToGlobal(QPoint(0, 0))
        x = esquina.x() + widget.width() - self.width()
        y = esquina.y() - self.height() - 12 if hacia_arriba else esquina.y() + widget.height() + 12
        pantalla = widget.screen().geometry()
        x = max(pantalla.left() + 8, min(x, pantalla.right() - self.width() - 8))
        self.move(x, y)
        self.show()

    def hideEvent(self, evento):
        self.cerrado_en = time.monotonic()
        super().hideEvent(evento)


class RelojTile(Tile):
    def __init__(self, alto, hacia_arriba=True):
        super().__init__(96, alto, centrado=True)
        self.hacia_arriba = hacia_arriba
        self.calendario = None
        self.clic.connect(self._alternar_calendario)

    def actualizar(self):
        ahora = datetime.now()
        self.poner(titulo=f"{DIAS[ahora.weekday()]} {ahora.day} {MESES[ahora.month - 1]}",
                   valor=f"{ahora:%H:%M}")
        self.setToolTip(f"{DIAS_LARGOS[ahora.weekday()].capitalize()}, {ahora.day} de "
                        f"{MESES_LARGOS[ahora.month - 1]} de {ahora.year}\nClic: calendario")

    def _alternar_calendario(self):
        if self.calendario is None:
            self.calendario = Calendario()
        # Si se acaba de cerrar (porque hiciste clic aquí mismo), no lo volvemos a abrir
        if time.monotonic() - self.calendario.cerrado_en < 0.3:
            return
        self.calendario.mostrar_cerca_de(self, self.hacia_arriba)


# =============================================================================
# Clima (Open-Meteo: gratis y sin registrarse)
# =============================================================================
def _describir_clima(codigo):
    if codigo == 0:
        return "☀", "Despejado"
    if codigo in (1, 2):
        return "⛅", "Parcialmente nublado"
    if codigo == 3:
        return "☁", "Nublado"
    if codigo in (45, 48):
        return "🌫", "Neblina"
    if 51 <= codigo <= 67 or 80 <= codigo <= 82:
        return "🌧", "Lluvia"
    if 71 <= codigo <= 77 or codigo in (85, 86):
        return "❄", "Nieve"
    if codigo >= 95:
        return "⛈", "Tormenta"
    return "🌡", "—"


class ClimaTile(Tile):
    def __init__(self, alto, ajustes):
        self.ciudad = ajustes.get("ciudad", "Santiago")
        self.lat = ajustes.get("latitud", -33.45)
        self.lon = ajustes.get("longitud", -70.66)
        super().__init__(92, alto, self.ciudad, "…")
        self.setToolTip("Cargando el clima…")
        self.clic.connect(lambda: webbrowser.open(
            "https://www.google.com/search?q=" + urllib.parse.quote(f"clima {self.ciudad}")))
        self.trabajo = TrabajoRepetido(self._consultar, cada=15 * 60, cada_si_falla=120)
        self.trabajo.resultado.connect(self._mostrar)
        self.trabajo.empezar()

    def _consultar(self):
        # Esto corre en el hilo aparte: puede tardar sin congelar la barra
        url = ("https://api.open-meteo.com/v1/forecast"
               f"?latitude={self.lat}&longitude={self.lon}"
               "&current=temperature_2m,weather_code&timezone=auto")
        with urllib.request.urlopen(url, timeout=10) as respuesta:
            datos = json.load(respuesta)
        actual = datos["current"]
        return actual["temperature_2m"], int(actual["weather_code"])

    def _mostrar(self, dato):
        if dato is None:
            if self.valor == "…":
                self.poner(valor="sin red")
            return
        temperatura, codigo = dato
        icono, texto = _describir_clima(codigo)
        self.poner(valor=f"{icono} {round(temperatura)}°")
        self.setToolTip(f"{self.ciudad}: {texto}, {temperatura:.1f} °C\nClic: pronóstico")

    def actualizar(self):
        pass   # el clima se actualiza solo, cada 15 minutos

    def detener(self):
        self.trabajo.detener()


# =============================================================================
# Música
# =============================================================================
async def _leer_musica():
    gestor = await GestorMedios.request_async()
    sesion = gestor.get_current_session()
    if sesion is None:
        return None
    propiedades = await sesion.try_get_media_properties_async()
    estado = sesion.get_playback_info().playback_status
    return {
        "titulo": propiedades.title or "",
        "artista": propiedades.artist or "",
        "sonando": int(estado) == 4,      # 4 = "reproduciendo"
    }


def _leer_musica_ahora():
    return asyncio.run(_leer_musica())


class BotonMedia(Caja):
    """Botón dibujado a mano: anterior, play/pausa o siguiente."""

    def __init__(self, tipo, lado):
        super().__init__(radio=8)
        self.tipo = tipo
        self.sonando = False
        self.setFixedSize(lado, lado)

    def pintar_fondo(self, p):
        if self._hover:
            super().pintar_fondo(p)

    def pintar(self, p):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(estilo.TEXTO)
        cx, cy = self.width() / 2, self.height() / 2
        s = self.height() * 0.2

        def triangulo(hacia_derecha, desplazamiento=0.0):
            x0 = cx + desplazamiento
            if hacia_derecha:
                puntos = [QPointF(x0 - s * 0.6, cy - s), QPointF(x0 - s * 0.6, cy + s), QPointF(x0 + s * 0.8, cy)]
            else:
                puntos = [QPointF(x0 + s * 0.6, cy - s), QPointF(x0 + s * 0.6, cy + s), QPointF(x0 - s * 0.8, cy)]
            p.drawPolygon(QPolygonF(puntos))

        if self.tipo == "play":
            if self.sonando:   # dibujar "pausa" = dos barritas
                p.drawRoundedRect(QRectF(cx - s * 0.75, cy - s, s * 0.5, s * 2), 1, 1)
                p.drawRoundedRect(QRectF(cx + s * 0.25, cy - s, s * 0.5, s * 2), 1, 1)
            else:
                triangulo(True)
        elif self.tipo == "next":
            triangulo(True, -s * 0.3)
            p.drawRect(QRectF(cx + s * 0.6, cy - s, s * 0.3, s * 2))
        else:  # prev
            triangulo(False, s * 0.3)
            p.drawRect(QRectF(cx - s * 0.9, cy - s, s * 0.3, s * 2))


class MusicaWidget(Caja):
    def __init__(self, alto):
        super().__init__()
        self.setFixedSize(232, alto)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.titulo = "Música"
        self.artista = "Nada sonando" if HAY_INFO_MUSICA else "Controles de reproducción"

        lado = alto - 12
        self.b_prev = BotonMedia("prev", lado)
        self.b_play = BotonMedia("play", lado)
        self.b_next = BotonMedia("next", lado)
        self.b_prev.clic.connect(lambda: self._tecla(sw.VK_MEDIA_PREV))
        self.b_play.clic.connect(lambda: self._tecla(sw.VK_MEDIA_PLAY_PAUSE))
        self.b_next.clic.connect(lambda: self._tecla(sw.VK_MEDIA_NEXT))

        capa = QHBoxLayout(self)
        capa.setContentsMargins(10, 6, 6, 6)
        capa.setSpacing(0)
        capa.addStretch()   # el texto se dibuja a mano en el espacio de la izquierda
        for b in (self.b_prev, self.b_play, self.b_next):
            capa.addWidget(b)

        if HAY_INFO_MUSICA:
            self.trabajo = TrabajoRepetido(_leer_musica_ahora, cada=1.5, cada_si_falla=3)
            self.trabajo.resultado.connect(self._mostrar)
            self.trabajo.empezar()

    def _tecla(self, codigo):
        sw.presionar_teclas(codigo)
        if codigo == sw.VK_MEDIA_PLAY_PAUSE:   # respuesta inmediata en pantalla
            self.b_play.sonando = not self.b_play.sonando
            self.b_play.update()

    def _mostrar(self, info):
        if not info or not info["titulo"]:
            self.titulo, self.artista = "Música", "Nada sonando"
            self.b_play.sonando = False
        else:
            self.titulo = info["titulo"]
            self.artista = info["artista"] or " "
            self.b_play.sonando = info["sonando"]
        self.setToolTip(f"{self.titulo}\n{self.artista}")
        self.b_play.update()
        self.update()

    def detener(self):
        if HAY_INFO_MUSICA:
            self.trabajo.detener()

    def pintar(self, p):
        ancho = self.b_prev.x() - 14
        f1 = estilo.fuente(12, negrita=True)
        f2 = estilo.fuente(10)
        alto_texto = 16 + 13
        y = (self.height() - alto_texto) / 2
        p.setFont(f1)
        p.setPen(estilo.TEXTO)
        p.drawText(QRectF(10, y, ancho, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   recortar(self.titulo, f1, ancho))
        p.setFont(f2)
        p.setPen(estilo.TEXTO_SUAVE)
        p.drawText(QRectF(10, y + 16, ancho, 13), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   recortar(self.artista, f2, ancho))

    def actualizar(self):
        pass


# =============================================================================
# Volumen y bandeja
# =============================================================================
class VolumenTile(Tile):
    def __init__(self, alto):
        super().__init__(alto, alto, "", "🔊")
        self.silenciado = False
        self.setToolTip("Rueda del mouse: subir / bajar volumen\nClic: silenciar")
        self.clic.connect(self._silenciar)

    def _silenciar(self):
        sw.presionar_teclas(sw.VK_VOLUME_MUTE)
        self.silenciado = not self.silenciado
        self.poner(valor="🔇" if self.silenciado else "🔊")

    def wheelEvent(self, evento):
        muescas = evento.angleDelta().y() // 120 or (1 if evento.angleDelta().y() > 0 else -1)
        tecla = sw.VK_VOLUME_UP if muescas > 0 else sw.VK_VOLUME_DOWN
        for _ in range(abs(muescas) * 2):    # cada pulsación = 2 %
            sw.presionar_teclas(tecla)
        if self.silenciado:
            self.silenciado = False
            self.poner(valor="🔊")

    def actualizar(self):
        pass


class BandejaTile(Tile):
    """Muestra un rato la barra de Windows (para los íconos ocultos: wifi, Discord, Steam...)."""

    def __init__(self, alto):
        super().__init__(alto, alto, "", "⌃")
        self.setToolTip("Mostrar / ocultar la barra de Windows\n(íconos ocultos, wifi, notificaciones)")

    def actualizar(self):
        pass


# =============================================================================
# Widgets extra: disco, progreso del año, enfoque
# =============================================================================
class DiscoTile(Tile):
    def __init__(self, alto):
        super().__init__(80, alto, "Disco C:", "—")
        self.unidad = "C:\\" if sw.ES_WINDOWS else "/"
        self._contador = 0
        self.clic.connect(lambda: abrir(self.unidad))

    def actualizar(self):
        # El disco cambia lento: lo revisamos cada 30 segundos, no cada segundo
        if self._contador % 30 == 0:
            uso = psutil.disk_usage(self.unidad)
            gb = 1024 ** 3
            self.poner(valor=f"{uso.percent:.0f}%", progreso=uso.percent, alerta=uso.percent >= 90)
            self.setToolTip(f"{uso.free / gb:.0f} GB libres de {uso.total / gb:.0f} GB\nClic: abrir el disco")
        self._contador += 1


class AnioTile(Tile):
    def __init__(self, alto):
        super().__init__(96, alto, "Año", "—")

    def actualizar(self):
        ahora = datetime.now()
        inicio = datetime(ahora.year, 1, 1)
        fin = datetime(ahora.year + 1, 1, 1)
        avance = (ahora - inicio) / (fin - inicio) * 100
        self.poner(titulo=f"Año {ahora.year}", valor=f"{avance:.0f}%", progreso=avance)
        dia = ahora.timetuple().tm_yday
        total = (fin - inicio).days
        self.setToolTip(f"Día {dia} de {total} · faltan {total - dia} días")


class EnfoqueTile(Tile):
    """Temporizador para estudiar (técnica Pomodoro: 25 minutos de concentración)."""
    MINUTOS = 25

    def __init__(self, alto):
        super().__init__(92, alto, "Enfoque", f"{self.MINUTOS}:00")
        self.total = self.MINUTOS * 60
        self.restante = self.total
        self.corriendo = False
        self._fin = 0.0
        self.setToolTip("Clic: empezar / pausar\nClic derecho: reiniciar")
        self.clic.connect(self.alternar)
        self.clic_derecho.connect(lambda _: self.reiniciar())

    def alternar(self):
        if self.corriendo:
            self.restante = max(0.0, self._fin - time.monotonic())
            self.corriendo = False
        else:
            if self.restante <= 0:
                self.restante = self.total
            self._fin = time.monotonic() + self.restante
            self.corriendo = True
        self.actualizar()

    def reiniciar(self):
        self.corriendo = False
        self.restante = self.total
        self.actualizar()

    def actualizar(self):
        if self.corriendo:
            self.restante = max(0.0, self._fin - time.monotonic())
            if self.restante <= 0:
                self.corriendo = False
                QApplication.beep()
                self.poner(titulo="¡Terminaste!", valor="00:00", progreso=100)
                return
        minutos, segundos = divmod(int(round(self.restante)), 60)
        if self.corriendo:
            titulo = "Enfoque ▶"
        elif self.restante < self.total:
            titulo = "En pausa"
        else:
            titulo = "Enfoque"
        avance = 100 * (1 - self.restante / self.total)
        self.poner(titulo=titulo, valor=f"{minutos:02d}:{segundos:02d}",
                   progreso=avance if self.restante < self.total else None)


# =============================================================================
# Modo edición: el círculo rojo con "−" para quitar un widget de la barra
# =============================================================================
class InsigniaQuitar(QWidget):
    def __init__(self, padre, al_quitar):
        super().__init__(padre)
        self.al_quitar = al_quitar
        self.setFixedSize(18, 18)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Quitar de la barra")
        self.move(padre.width() - 19, 1)
        self.raise_()
        self.show()

    def mousePressEvent(self, evento):
        evento.accept()

    def mouseReleaseEvent(self, evento):
        evento.accept()
        self.al_quitar()

    def paintEvent(self, evento):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#ff3b30"))
        p.drawEllipse(QRectF(1, 1, 16, 16))
        p.setBrush(QColor("white"))
        p.drawRoundedRect(QRectF(5, 8, 8, 2), 1, 1)
        p.end()

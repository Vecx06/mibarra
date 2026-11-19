"""
ajustes.py — la ventana de Ajustes de mibarra (estilo Apple).

Se abre con clic derecho en un espacio vacío de la barra -> "Ajustes de mibarra…".
Todo lo que cambies aquí se guarda solo en config.json y se aplica al tiro en la barra.

Está armada así:
  ┌────────────┬──────────────────────────────────────┐
  │ [Buscar]   │  Título de la sección          [✕]   │
  │ Widgets    │                                      │
  │ Apps       │  (contenido de la sección, con       │
  │ Apariencia │   tarjetas blancas redondeadas)      │
  │ ...        │                                      │
  └────────────┴──────────────────────────────────────┘
"""

import json
import os
import webbrowser
from pathlib import Path
import threading
import urllib.parse
import urllib.request

from PyQt6.QtCore import QObject, QRectF, Qt, QTimer, QVariantAnimation, pyqtSignal
from PyQt6.QtGui import QColor, QFontMetrics, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (QFileDialog, QMessageBox, QFrame, QGraphicsDropShadowEffect, QGridLayout,
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QSlider,
                             QStackedWidget, QVBoxLayout, QWidget, QApplication)

import config as configuracion
import rutas
import estilo
import sistema_windows as sw
import mas_widgets
from version import VERSION
from widgets import Tile, abrir

AZUL = "#0a84ff"
VERDE = "#34c759"
ROJO = "#ff3b30"
TEXTO = "#1d1d1f"
TEXTO_SUAVE = "#6e6e73"

# -----------------------------------------------------------------------------
# Catálogo de widgets: id, nombre, descripción, categoría y cómo se ve de ejemplo
# (título, valor, ancho, progreso, centrado)
# -----------------------------------------------------------------------------
CATALOGO = [
    ("reloj", "Reloj", "Hora y fecha. Clic: calendario.", "Reloj y fecha",
     ("dom 15 nov", "19:30", 96, None, True)),
    ("anio", "Progreso del año", "Cuánto del año ya pasó.", "Reloj y fecha",
     ("Año 2026", "87%", 96, 87, False)),
    ("enfoque", "Enfoque", "Temporizador de 25 min para estudiar.", "Productividad",
     ("Enfoque", "25:00", 92, None, False)),
    ("cpu", "CPU", "Uso del procesador.", "Sistema", ("CPU", "12%", 70, 12, False)),
    ("ram", "RAM", "Memoria en uso.", "Sistema", ("RAM", "54%", 70, 54, False)),
    ("disco", "Disco", "Espacio usado en C:.", "Sistema", ("Disco C:", "61%", 80, 61, False)),
    ("red", "Red", "Velocidad de internet.", "Sistema", ("Red · ↑ 34 KB/s", "↓ 2.4 MB/s", 116, None, False)),
    ("bateria", "Batería", "Carga (solo en notebooks).", "Sistema", ("Batería", "85% ⚡", 78, 85, False)),
    ("bandeja", "Bandeja", "Muestra un rato la barra de Windows.", "Sistema", ("", "⌃", 40, None, True)),
    ("musica", "Música", "Canción actual y controles.", "Multimedia",
     ("The Weeknd", "Blinding Lights", 170, None, False)),
    ("volumen", "Volumen", "Rueda: subir y bajar. Clic: silenciar.", "Multimedia", ("", "🔊", 40, None, True)),
    ("clima", "Clima", "Temperatura de tu ciudad.", "Clima", ("Santiago", "⛅ 23°", 92, None, False)),
    ("comando", "Comando", "Abre programas, páginas, busca en Google o calcula (=2+2).", "Productividad",
     "comando"),
    ("notas", "Notas", "Una nota rápida que se guarda sola.", "Productividad", "notas"),
    ("conexiones", "Conexiones", "Wi-Fi, Bluetooth y modo avión.", "Controles", "conexiones"),
    ("tema", "Claro / oscuro", "Cambia Windows entre modo claro y oscuro.", "Controles", "tema"),
    ("capturas", "Capturas", "Recortar, capturar la pantalla y abrir la carpeta.", "Controles", "capturas"),
    ("bateria_anillo", "Anillo de batería", "La batería como un anillo (solo notebooks).", "Sistema",
     "bateria_anillo"),
    ("cpu_anillo", "Anillo de CPU", "El procesador como un anillo.", "Sistema", "cpu_anillo"),
    ("almacenamiento", "Almacenamiento", "Espacio libre en el disco.", "Sistema", "almacenamiento"),
    ("moneda", "Moneda", "Conversor de moneda (ej. dólar a peso chileno).", "Finanzas", "moneda"),
]
ORDEN_CATEGORIAS = ["Productividad", "Controles", "Reloj y fecha", "Sistema", "Multimedia", "Clima", "Finanzas"]
NOMBRES = {c[0]: c[1] for c in CATALOGO}

COLORES_ACENTO = ["#0a84ff", "#bf5af2", "#ff375f", "#ff9f0a", "#30d158", "#64d2ff", "#8e8e93"]

HOJA = f"""
QWidget {{ color: {TEXTO}; }}
#ventana {{
    background: rgba(246, 246, 248, 252);
    border: 1px solid rgba(0, 0, 0, 28);
    border-radius: 18px;
}}
#lateral {{
    background: rgba(234, 234, 239, 255);
    border-top-left-radius: 18px;
    border-bottom-left-radius: 18px;
    border-right: 1px solid rgba(0, 0, 0, 16);
}}
QLineEdit#buscar {{
    background: rgba(0, 0, 0, 13); border: none; border-radius: 10px;
    padding: 8px 10px 8px 12px; font-size: 13px;
}}
QLineEdit#campo {{
    background: white; border: 1px solid rgba(0, 0, 0, 30); border-radius: 8px;
    padding: 7px 10px; font-size: 13px;
}}
QLineEdit#campo:focus {{ border: 2px solid {AZUL}; padding: 6px 9px; }}
QPushButton#nav {{
    text-align: left; padding: 7px 10px; border: none; border-radius: 8px;
    font-size: 13px; background: transparent; color: {TEXTO};
}}
QPushButton#nav:hover {{ background: rgba(0, 0, 0, 12); }}
QPushButton#nav:checked {{ background: {AZUL}; color: white; }}
QLabel#titulo {{ font-size: 22px; font-weight: 700; }}
QLabel#seccion {{ font-size: 13px; font-weight: 600; color: {TEXTO_SUAVE}; }}
QLabel#insignia {{
    background: rgba(0, 0, 0, 13); color: {TEXTO_SUAVE};
    border-radius: 10px; padding: 2px 10px; font-size: 12px; min-height: 16px;
}}
QLabel#suave {{ color: {TEXTO_SUAVE}; font-size: 12px; }}
QLabel#negrita {{ font-size: 13px; font-weight: 600; }}
QFrame#tarjeta {{
    background: white; border: 1px solid rgba(0, 0, 0, 14); border-radius: 14px;
}}
QFrame#tarjetaActiva {{
    background: white; border: 2px solid {AZUL}; border-radius: 14px;
}}
QFrame#ficha {{
    background: rgba(0, 0, 0, 7); border: 1px solid rgba(0, 0, 0, 12); border-radius: 10px;
}}
QFrame#linea {{ background: rgba(0, 0, 0, 14); max-height: 1px; border: none; }}
QPushButton#pill {{
    border: none; border-radius: 12px; padding: 4px 14px; min-height: 18px; font-size: 12px; font-weight: 600;
    background: #ececf0; color: {TEXTO};
}}
QPushButton#pill:hover {{ background: #e0e0e6; }}
QPushButton#pillAzul {{
    border: none; border-radius: 12px; padding: 4px 14px; min-height: 18px; font-size: 12px; font-weight: 600;
    background: {AZUL}; color: white;
}}
QPushButton#pillAzul:hover {{ background: #0071e3; }}
QPushButton#pillRojo {{
    border: none; border-radius: 12px; padding: 4px 14px; min-height: 18px; font-size: 12px; font-weight: 600;
    background: #ffecea; color: {ROJO};
}}
QPushButton#pillRojo:hover {{ background: #ffd9d6; }}
QPushButton#mini {{
    border: none; border-radius: 7px; background: #efeff3;
    font-size: 12px; padding: 0px; min-width: 24px; min-height: 22px;
}}
QPushButton#mini:hover {{ background: #e2e2e8; }}
QPushButton#mini:disabled {{ color: #c7c7cc; background: transparent; }}
QPushButton#cerrar {{
    border: none; border-radius: 14px; background: rgba(0, 0, 0, 12);
    color: #3a3a3c; font-size: 13px; min-width: 28px; min-height: 28px;
}}
QPushButton#cerrar:hover {{ background: rgba(0, 0, 0, 24); }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px; }}
QScrollBar::handle:vertical {{ background: rgba(0, 0, 0, 45); border-radius: 3px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QSlider::groove:horizontal {{ height: 4px; background: rgba(0, 0, 0, 25); border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {AZUL}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    background: white; width: 20px; height: 20px; margin: -8px 0;
    border-radius: 10px; border: 1px solid rgba(0, 0, 0, 40);
}}
"""


# =============================================================================
# Controles estilo Apple, dibujados a mano
# =============================================================================
class Interruptor(QWidget):
    """El switch verde de iPhone."""
    cambiado = pyqtSignal(bool)

    def __init__(self, activo=False):
        super().__init__()
        self.setFixedSize(46, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._activo = activo
        self._pos = 1.0 if activo else 0.0      # 0 = izquierda (apagado), 1 = derecha (encendido)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(160)
        self._anim.valueChanged.connect(self._mover)

    def _mover(self, valor):
        self._pos = float(valor)
        self.update()

    def poner(self, activo):
        self._activo = activo
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if activo else 0.0)
        self._anim.start()

    def mouseReleaseEvent(self, evento):
        self.poner(not self._activo)
        self.cambiado.emit(self._activo)

    def paintEvent(self, evento):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        apagado, encendido = QColor(0, 0, 0, 38), QColor(VERDE)
        t = self._pos
        color = QColor(int(apagado.red() + (encendido.red() - apagado.red()) * t),
                       int(apagado.green() + (encendido.green() - apagado.green()) * t),
                       int(apagado.blue() + (encendido.blue() - apagado.blue()) * t),
                       int(apagado.alpha() + (encendido.alpha() - apagado.alpha()) * t))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawRoundedRect(QRectF(0, 0, 46, 28), 14, 14)
        x = 2 + t * 18
        p.setBrush(QColor(0, 0, 0, 30))
        p.drawEllipse(QRectF(x, 2.8, 24, 24))      # sombrita
        p.setBrush(QColor("white"))
        p.drawEllipse(QRectF(x, 2, 24, 24))
        p.end()


class Segmentado(QWidget):
    """Botones pegados, como [ Abajo | Arriba ] en macOS."""
    cambiado = pyqtSignal(str)

    def __init__(self, opciones, actual):
        super().__init__()
        self.opciones = opciones        # lista de (valor, texto)
        self.actual = actual
        medidor = QFontMetrics(estilo.fuente(12, negrita=True))
        ancho_opcion = max(96, max(medidor.horizontalAdvance(t) for _, t in opciones) + 28)
        self.setFixedSize(ancho_opcion * len(opciones), 30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, evento):
        indice = int(evento.position().x() // (self.width() / len(self.opciones)))
        indice = max(0, min(indice, len(self.opciones) - 1))
        valor = self.opciones[indice][0]
        if valor != self.actual:
            self.actual = valor
            self.update()
            self.cambiado.emit(valor)

    def paintEvent(self, evento):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 16))
        p.drawRoundedRect(QRectF(self.rect()), 8, 8)
        ancho = self.width() / len(self.opciones)
        p.setFont(estilo.fuente(12, negrita=True))
        for i, (valor, texto) in enumerate(self.opciones):
            zona = QRectF(i * ancho + 2, 2, ancho - 4, self.height() - 4)
            if valor == self.actual:
                p.setPen(QPen(QColor(0, 0, 0, 22), 1))
                p.setBrush(QColor("white"))
                p.drawRoundedRect(zona, 6, 6)
            p.setPen(QColor(TEXTO))
            p.drawText(zona, Qt.AlignmentFlag.AlignCenter, texto)
        p.end()


class MuestraColor(QWidget):
    elegido = pyqtSignal(str)

    def __init__(self, color, seleccionado):
        super().__init__()
        self.color = color
        self.seleccionado = seleccionado
        self.setFixedSize(30, 30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, evento):
        self.elegido.emit(self.color)

    def paintEvent(self, evento):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.seleccionado:
            p.setPen(QPen(QColor(0, 0, 0, 70), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(1, 1, 28, 28))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(self.color))
        p.drawEllipse(QRectF(5, 5, 20, 20))
        p.end()


class VistaPrevia(QWidget):
    """Un pedacito de barra con el widget de ejemplo adentro."""

    def __init__(self, ejemplo, config=None):
        super().__init__()
        self.setFixedHeight(64)
        capa = QHBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.addStretch()
        if isinstance(ejemplo, str):
            # Un widget de verdad, en "modo demo" (datos de ejemplo, sin conectarse a nada)
            widget = mas_widgets.CREADORES[ejemplo](40, dict(config or {}), demo=True)
            widget.actualizar()
        else:
            titulo, valor, ancho, progreso, centrado = ejemplo
            widget = Tile(ancho, 40, titulo, valor, centrado)
            widget.progreso = progreso
        widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        for hijo in widget.findChildren(QWidget):
            hijo.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        capa.addWidget(widget)
        capa.addStretch()

    def paintEvent(self, evento):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        fondo = QColor(estilo.FONDO_SOLIDO)
        fondo.setAlpha(255)
        p.setBrush(fondo)
        p.drawRoundedRect(QRectF(self.rect()), 12, 12)
        p.end()


def icono_lateral(color, simbolo):
    """Cuadradito de color con un símbolo blanco (como los íconos de Ajustes del iPhone)."""
    pixmap = QPixmap(44, 44)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    p.drawRoundedRect(QRectF(0, 0, 44, 44), 10, 10)
    p.setPen(QColor("white"))
    p.setFont(estilo.fuente(24, negrita=True))
    p.drawText(QRectF(0, 0, 44, 44), Qt.AlignmentFlag.AlignCenter, simbolo)
    p.end()
    return QIcon(pixmap)


def etiqueta(texto, nombre_objeto=None):
    e = QLabel(texto)
    if nombre_objeto:
        e.setObjectName(nombre_objeto)
    e.setWordWrap(True)
    return e


def boton(texto, tipo="pill"):
    b = QPushButton(texto)
    b.setObjectName(tipo)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


def linea():
    raya = QFrame()
    raya.setObjectName("linea")
    raya.setFrameShape(QFrame.Shape.HLine)
    return raya


def tarjeta():
    t = QFrame()
    t.setObjectName("tarjeta")
    capa = QVBoxLayout(t)
    capa.setContentsMargins(16, 12, 16, 12)
    capa.setSpacing(10)
    return t, capa


def fila(titulo, descripcion, control):
    """Una fila de ajustes: texto a la izquierda, control a la derecha."""
    w = QWidget()
    capa = QHBoxLayout(w)
    capa.setContentsMargins(0, 2, 0, 2)
    textos = QVBoxLayout()
    textos.setSpacing(1)
    textos.addWidget(etiqueta(titulo, "negrita"))
    if descripcion:
        textos.addWidget(etiqueta(descripcion, "suave"))
    capa.addLayout(textos, 1)
    capa.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)
    return w


class Buscador(QObject):
    """Busca ciudades en internet (en un hilo aparte, para no congelar la ventana)."""
    listo = pyqtSignal(object)

    def buscar(self, texto):
        def trabajo():
            try:
                url = ("https://geocoding-api.open-meteo.com/v1/search?count=6&language=es&format=json&name="
                       + urllib.parse.quote(texto))
                with urllib.request.urlopen(url, timeout=10) as r:
                    datos = json.load(r)
                self.listo.emit(datos.get("results", []))
            except Exception:
                self.listo.emit(None)
        threading.Thread(target=trabajo, daemon=True).start()


# =============================================================================
# La ventana
# =============================================================================
class Ajustes(QWidget):
    PAGINAS = [
        ("widgets", "Widgets", "#0a84ff", "▦"),
        ("apps", "Apps fijadas", "#ff9f0a", "★"),
        ("apariencia", "Apariencia", "#bf5af2", "◐"),
        ("comportamiento", "Comportamiento", "#8e8e93", "⚙"),
        ("clima", "Clima", "#64d2ff", "☀"),
        ("moneda", "Moneda", "#ffcc00", "$"),
        ("acerca", "Acerca de", "#30d158", "i"),
    ]

    def __init__(self, dock):
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.dock = dock
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("Ajustes de mibarra")
        self.setStyleSheet(HOJA)
        self.resize(940, 640)
        self.pagina_actual = "widgets"
        self.buscador = Buscador()
        self.buscador.listo.connect(self._ciudades_encontradas)
        self._temporizador_alto = QTimer(self)
        self._temporizador_alto.setSingleShot(True)
        self._temporizador_alto.timeout.connect(lambda: self.dock.aplicar_config("todo"))

        # Margen transparente alrededor para que se vea la sombra
        exterior = QVBoxLayout(self)
        exterior.setContentsMargins(24, 24, 24, 24)
        self.ventana = QFrame()
        self.ventana.setObjectName("ventana")
        sombra = QGraphicsDropShadowEffect(self)
        sombra.setBlurRadius(40)
        sombra.setOffset(0, 10)
        sombra.setColor(QColor(0, 0, 0, 70))
        self.ventana.setGraphicsEffect(sombra)
        exterior.addWidget(self.ventana)

        principal = QHBoxLayout(self.ventana)
        principal.setContentsMargins(0, 0, 0, 0)
        principal.setSpacing(0)

        # --- Barra lateral ---
        lateral = QFrame()
        lateral.setObjectName("lateral")
        lateral.setFixedWidth(230)
        capa_lateral = QVBoxLayout(lateral)
        capa_lateral.setContentsMargins(14, 18, 14, 14)
        capa_lateral.setSpacing(4)
        self.campo_buscar = QLineEdit()
        self.campo_buscar.setObjectName("buscar")
        self.campo_buscar.setPlaceholderText("🔍  Buscar widgets")
        self.campo_buscar.textChanged.connect(self._al_buscar)
        capa_lateral.addWidget(self.campo_buscar)
        capa_lateral.addSpacing(10)
        self.botones_nav = {}
        for clave, texto, color, simbolo in self.PAGINAS:
            b = QPushButton(f"  {texto}")
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setIcon(icono_lateral(color, simbolo))
            b.setIconSize(b.iconSize().scaled(22, 22, Qt.AspectRatioMode.KeepAspectRatio))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _, c=clave: self.ir_a(c))
            capa_lateral.addWidget(b)
            self.botones_nav[clave] = b
        capa_lateral.addStretch()
        capa_lateral.addWidget(etiqueta(f"mibarra {VERSION}", "suave"))
        principal.addWidget(lateral)

        # --- Contenido ---
        derecha = QVBoxLayout()
        derecha.setContentsMargins(28, 20, 18, 0)
        derecha.setSpacing(12)
        cabecera = QHBoxLayout()
        self.titulo = etiqueta("", "titulo")
        self.insignia = etiqueta("", "insignia")
        self.insignia.setWordWrap(False)
        cerrar = boton("✕", "cerrar")
        cerrar.clicked.connect(self.close)
        cabecera.addWidget(self.titulo)
        cabecera.addWidget(self.insignia, 0, Qt.AlignmentFlag.AlignVCenter)
        cabecera.addStretch()
        cabecera.addWidget(cerrar)
        derecha.addLayout(cabecera)

        self.paginas = QStackedWidget()
        self.contenidos = {}
        for clave, *_ in self.PAGINAS:
            area = QScrollArea()
            area.setWidgetResizable(True)
            area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            contenido = QWidget()
            capa = QVBoxLayout(contenido)
            capa.setContentsMargins(0, 0, 10, 20)
            capa.setSpacing(12)
            area.setWidget(contenido)
            self.paginas.addWidget(area)
            self.contenidos[clave] = (area, capa)
        derecha.addWidget(self.paginas, 1)
        principal.addLayout(derecha, 1)

    # -------------------------------------------------------------------------
    # Navegación
    # -------------------------------------------------------------------------
    def mostrar(self, pagina=None):
        self.ir_a(pagina or self.pagina_actual)
        pantalla = QApplication.primaryScreen().availableGeometry()
        self.move(pantalla.center().x() - self.width() // 2,
                  max(pantalla.top() + 10, pantalla.center().y() - self.height() // 2 - 40))
        self.show()
        self.raise_()
        self.activateWindow()

    def ir_a(self, clave):
        self.pagina_actual = clave
        for c, b in self.botones_nav.items():
            b.setChecked(c == clave)
        indice = [p[0] for p in self.PAGINAS].index(clave)
        self.paginas.setCurrentIndex(indice)
        self.refrescar()

    def refrescar(self):
        """Vuelve a dibujar la página actual con los datos de ahora."""
        clave = self.pagina_actual
        area, capa = self.contenidos[clave]
        self._vaciar(capa)
        nombre_pagina = dict((p[0], p[1]) for p in self.PAGINAS)[clave]
        self.titulo.setText(nombre_pagina)
        self.insignia.hide()
        getattr(self, f"_pagina_{clave}")(capa)
        capa.addStretch()

    @staticmethod
    def _vaciar(capa):
        while capa.count():
            item = capa.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                Ajustes._vaciar(item.layout())

    def _al_buscar(self, _texto):
        if self.pagina_actual != "widgets":
            self.ir_a("widgets")
        else:
            self.refrescar()

    # Mover la ventana arrastrando cualquier parte vacía
    def mousePressEvent(self, evento):
        if evento.button() == Qt.MouseButton.LeftButton and self.windowHandle():
            self.windowHandle().startSystemMove()

    def keyPressEvent(self, evento):
        if evento.key() == Qt.Key.Key_Escape:
            self.close()

    def showEvent(self, evento):
        self.dock.modo_edicion(True)
        super().showEvent(evento)

    def hideEvent(self, evento):
        self.dock.modo_edicion(False)
        super().hideEvent(evento)

    def _guardar(self, que):
        self.dock.aplicar_config(que)

    # -------------------------------------------------------------------------
    # Página: Widgets
    # -------------------------------------------------------------------------
    def _pagina_widgets(self, capa):
        activos = self.dock.config.setdefault("widgets", [])
        self.insignia.setText(f"{len(activos)} en la barra")
        self.insignia.show()

        # Aviso si la barra no alcanza a mostrar todos
        if self.dock.widgets_sin_espacio:
            nombres = ", ".join(NOMBRES.get(w, w) for w in self.dock.widgets_sin_espacio)
            aviso = etiqueta(f"⚠️  No caben todos en tu pantalla, así que se escondieron: <b>{nombres}</b>. "
                             "Quita alguno, achica la barra (Apariencia › Tamaño) o muévelos más a la derecha.")
            aviso.setStyleSheet("background: #fff4d6; border: 1px solid #f5d77a; border-radius: 10px; "
                                "padding: 10px 12px; color: #6b4e00;")
            capa.addWidget(aviso)

        # 1) Orden actual en la barra: "fichas" en filas de 3, con ‹ › para mover y ✕ para quitar
        capa.addWidget(etiqueta("En tu barra (de izquierda a derecha)", "seccion"))
        t, c = tarjeta()
        if not activos:
            c.addWidget(etiqueta("No tienes widgets en la barra. Agrega alguno de abajo.", "suave"))
        grilla_fichas = QGridLayout()
        grilla_fichas.setSpacing(8)
        for i, id_widget in enumerate(activos):
            ficha = QFrame()
            ficha.setObjectName("ficha")
            h = QHBoxLayout(ficha)
            h.setContentsMargins(10, 4, 4, 4)
            h.setSpacing(2)
            h.addWidget(etiqueta(NOMBRES.get(id_widget, id_widget), "negrita"), 1)
            izquierda, derecha, quitar = boton("‹", "mini"), boton("›", "mini"), boton("✕", "mini")
            izquierda.setEnabled(i > 0)
            derecha.setEnabled(i < len(activos) - 1)
            izquierda.setToolTip("Mover a la izquierda")
            derecha.setToolTip("Mover a la derecha")
            quitar.setToolTip("Quitar de la barra")
            izquierda.clicked.connect(lambda _, n=i: self._mover_widget(n, -1))
            derecha.clicked.connect(lambda _, n=i: self._mover_widget(n, +1))
            quitar.clicked.connect(lambda _, w=id_widget: self._alternar_widget(w))
            for b in (izquierda, derecha, quitar):
                h.addWidget(b)
            grilla_fichas.addWidget(ficha, i // 3, i % 3)
        for columna in range(3):
            grilla_fichas.setColumnStretch(columna, 1)
        c.addLayout(grilla_fichas)
        capa.addWidget(t)

        # 2) Galería por categoría (filtrada por el buscador)
        filtro = self.campo_buscar.text().strip().lower()
        categorias = list(ORDEN_CATEGORIAS)
        hubo_alguno = False
        for categoria in categorias:
            items = [it for it in CATALOGO if it[3] == categoria
                     and (not filtro or filtro in it[1].lower() or filtro in it[2].lower())]
            if not items:
                continue
            hubo_alguno = True
            capa.addWidget(etiqueta(categoria, "seccion"))
            grilla = QGridLayout()
            grilla.setSpacing(12)
            for n, (id_widget, nombre, descripcion, _, ejemplo) in enumerate(items):
                grilla.addWidget(self._tarjeta_widget(id_widget, nombre, descripcion, ejemplo,
                                                      id_widget in activos), n // 2, n % 2)
            for columna in range(2):
                grilla.setColumnStretch(columna, 1)
            capa.addLayout(grilla)
        if not hubo_alguno:
            capa.addWidget(etiqueta(f"No encontré widgets con “{filtro}”.", "suave"))

    def _tarjeta_widget(self, id_widget, nombre, descripcion, ejemplo, activo):
        t = QFrame()
        t.setObjectName("tarjetaActiva" if activo else "tarjeta")
        c = QVBoxLayout(t)
        c.setContentsMargins(12, 12, 12, 12)
        c.setSpacing(6)
        c.addWidget(VistaPrevia(ejemplo, self.dock.config))
        c.addWidget(etiqueta(nombre, "negrita"))
        c.addWidget(etiqueta(descripcion, "suave"))
        b = boton("✓ En la barra" if activo else "＋ Agregar", "pill" if activo else "pillAzul")
        b.clicked.connect(lambda: self._alternar_widget(id_widget))
        c.addWidget(b, 0, Qt.AlignmentFlag.AlignLeft)
        return t

    def _alternar_widget(self, id_widget):
        activos = self.dock.config.setdefault("widgets", [])
        if id_widget in activos:
            activos.remove(id_widget)
        else:
            # Los widgets nuevos entran justo antes del reloj (si hay reloj)
            posicion = activos.index("reloj") if "reloj" in activos else len(activos)
            activos.insert(posicion, id_widget)
        self._guardar("widgets")
        self.refrescar()

    def _mover_widget(self, indice, direccion):
        activos = self.dock.config["widgets"]
        nuevo = indice + direccion
        if 0 <= nuevo < len(activos):
            activos[indice], activos[nuevo] = activos[nuevo], activos[indice]
            self._guardar("widgets")
            self.refrescar()

    # -------------------------------------------------------------------------
    # Página: Apps fijadas
    # -------------------------------------------------------------------------
    def _pagina_apps(self, capa):
        from dock import icono_de   # aquí para evitar importaciones circulares
        apps = self.dock.config.setdefault("apps_fijadas", [])
        self.insignia.setText(f"{len(apps)} fijadas")
        self.insignia.show()

        capa.addWidget(etiqueta("Fijadas en la barra", "seccion"))
        t, c = tarjeta()
        if not apps:
            c.addWidget(etiqueta("No tienes apps fijadas.", "suave"))
        for i, app in enumerate(apps):
            ruta = os.path.expandvars(app.get("ruta", ""))
            renglon = QHBoxLayout()
            icono = QLabel()
            ic = icono_de(ruta)
            if not ic.isNull():
                icono.setPixmap(ic.pixmap(28, 28))
            else:
                icono.setText(app.get("emoji") or "▢")
                icono.setStyleSheet("font-size: 20px;")
            icono.setFixedWidth(34)
            renglon.addWidget(icono)
            textos = QVBoxLayout()
            textos.setSpacing(0)
            textos.addWidget(etiqueta(app.get("nombre", "App"), "negrita"))
            textos.addWidget(etiqueta(ruta, "suave"))
            renglon.addLayout(textos, 1)
            subir, bajar, quitar = boton("↑", "mini"), boton("↓", "mini"), boton("Quitar", "pillRojo")
            subir.setEnabled(i > 0)
            bajar.setEnabled(i < len(apps) - 1)
            subir.clicked.connect(lambda _, n=i: self._mover_app(n, -1))
            bajar.clicked.connect(lambda _, n=i: self._mover_app(n, +1))
            quitar.clicked.connect(lambda _, n=i: self._quitar_app(n))
            for b in (subir, bajar, quitar):
                renglon.addWidget(b)
            c.addLayout(renglon)
            if i < len(apps) - 1:
                c.addWidget(linea())
        capa.addWidget(t)

        agregar = boton("＋ Agregar un programa…", "pillAzul")
        agregar.clicked.connect(self._agregar_app)
        capa.addWidget(agregar, 0, Qt.AlignmentFlag.AlignLeft)

        # Apps abiertas que todavía no están fijadas
        abiertas = [b for b in self.dock.botones.values() if not b.fijada and b.ruta]
        if abiertas:
            capa.addSpacing(6)
            capa.addWidget(etiqueta("Abiertas ahora", "seccion"))
            t2, c2 = tarjeta()
            for n, b in enumerate(abiertas):
                renglon = QHBoxLayout()
                icono = QLabel()
                if not b.icono.isNull():
                    icono.setPixmap(b.icono.pixmap(28, 28))
                icono.setFixedWidth(34)
                renglon.addWidget(icono)
                renglon.addWidget(etiqueta(b.nombre, "negrita"), 1)
                fijar = boton("Fijar", "pill")
                fijar.clicked.connect(lambda _, nombre=b.nombre, ruta=b.ruta: self._fijar(nombre, ruta))
                renglon.addWidget(fijar)
                c2.addLayout(renglon)
                if n < len(abiertas) - 1:
                    c2.addWidget(linea())
            capa.addWidget(t2)

    def _mover_app(self, indice, direccion):
        apps = self.dock.config["apps_fijadas"]
        nuevo = indice + direccion
        if 0 <= nuevo < len(apps):
            apps[indice], apps[nuevo] = apps[nuevo], apps[indice]
            self._guardar("apps")
            self.refrescar()

    def _quitar_app(self, indice):
        del self.dock.config["apps_fijadas"][indice]
        self._guardar("apps")
        self.refrescar()

    def _fijar(self, nombre, ruta):
        self.dock.config["apps_fijadas"].append({"nombre": nombre, "ruta": ruta})
        self._guardar("apps")
        self.refrescar()

    def _agregar_app(self):
        inicio = os.path.expandvars(r"%ProgramFiles%") if sw.ES_WINDOWS else os.path.expanduser("~")
        ruta, _ = QFileDialog.getOpenFileName(self, "Elige un programa", inicio, "Programas (*.exe)")
        if ruta:
            ruta = os.path.normpath(ruta)
            nombre = os.path.splitext(os.path.basename(ruta))[0]
            self._fijar(nombre[:1].upper() + nombre[1:], ruta)

    # -------------------------------------------------------------------------
    # Página: Apariencia
    # -------------------------------------------------------------------------
    def _pagina_apariencia(self, capa):
        cfg = self.dock.config
        t, c = tarjeta()

        posicion = Segmentado([("abajo", "Abajo"), ("arriba", "Arriba")], cfg.get("posicion", "abajo"))
        posicion.cambiado.connect(lambda v: self._poner("posicion", v, "todo"))
        c.addWidget(fila("Posición", "En qué borde de la pantalla va la barra.", posicion))
        c.addWidget(linea())

        forma = Segmentado([("centro", "Centrada"), ("completa", "Ancho completo")],
                           cfg.get("alineacion", "centro"))
        forma.cambiado.connect(lambda v: self._poner("alineacion", v, "todo"))
        c.addWidget(fila("Forma", "Centrada = mide justo lo necesario, como en Windows 11.", forma))
        c.addWidget(linea())

        tema = Segmentado([("oscuro", "Oscuro"), ("claro", "Claro"), ("auto", "Automático")],
                          cfg.get("tema", "oscuro"))
        tema.cambiado.connect(lambda v: self._poner("tema", v, "todo", refrescar=True))
        c.addWidget(fila("Tema de la barra", "Automático = igual que Windows.", tema))
        c.addWidget(linea())

        fondo = Segmentado([("vidrio", "Vidrio"), ("solido", "Sólido")], cfg.get("estilo", "vidrio"))
        fondo.cambiado.connect(lambda v: self._poner("estilo", v, "todo"))
        c.addWidget(fila("Fondo", "Vidrio = borroso y transparente, como en macOS.", fondo))
        c.addWidget(linea())

        contenedor = QWidget()
        h = QHBoxLayout(contenedor)
        h.setContentsMargins(0, 0, 0, 0)
        deslizador = QSlider(Qt.Orientation.Horizontal)
        deslizador.setRange(44, 76)
        deslizador.setValue(int(cfg.get("alto", 56)))
        deslizador.setFixedWidth(200)
        valor = etiqueta(f"{deslizador.value()} px", "suave")
        valor.setFixedWidth(46)
        deslizador.valueChanged.connect(lambda v: self._cambiar_alto(v, valor))
        h.addWidget(deslizador)
        h.addWidget(valor)
        c.addWidget(fila("Tamaño", "Alto de la barra.", contenedor))
        c.addWidget(linea())

        colores = QWidget()
        hc = QHBoxLayout(colores)
        hc.setContentsMargins(0, 0, 0, 0)
        hc.setSpacing(2)
        actual = cfg.get("color_acento", "#0a84ff").lower()
        for color in COLORES_ACENTO:
            m = MuestraColor(color, color.lower() == actual)
            m.elegido.connect(lambda col: self._poner("color_acento", col, "todo", refrescar=True))
            hc.addWidget(m)
        c.addWidget(fila("Color de acento", "Puntitos de apps abiertas, barras de progreso, inicio.", colores))
        capa.addWidget(t)

    def _cambiar_alto(self, valor, etiqueta_valor):
        etiqueta_valor.setText(f"{valor} px")
        self.dock.config["alto"] = valor
        self._temporizador_alto.start(250)   # espera a que sueltes el deslizador

    def _poner(self, clave, valor, que, refrescar=False):
        self.dock.config[clave] = valor
        self._guardar(que)
        if refrescar:
            self.refrescar()

    # -------------------------------------------------------------------------
    # Página: Comportamiento
    # -------------------------------------------------------------------------
    def _pagina_comportamiento(self, capa):
        cfg = self.dock.config
        t, c = tarjeta()
        opciones = [
            ("ocultar_barra_windows", "Ocultar la barra de Windows",
             "Mientras mibarra esté abierta. Al cerrarla vuelve sola."),
            ("reservar_espacio", "Reservar espacio",
             "Las ventanas maximizadas no quedan debajo de la barra."),
            ("esconder_en_pantalla_completa", "Esconder en pantalla completa",
             "Con videos, juegos o presentaciones."),
        ]
        for clave, titulo, descripcion in opciones:
            interruptor = Interruptor(bool(cfg.get(clave, True)))
            interruptor.cambiado.connect(lambda v, k=clave: self._poner(k, v, "todo"))
            c.addWidget(fila(titulo, descripcion, interruptor))
            c.addWidget(linea())
        inicio = Interruptor(sw.inicio_automatico_activo())
        inicio.setEnabled(sw.ES_WINDOWS)
        inicio.cambiado.connect(
            lambda v: sw.poner_inicio_automatico(v, self.dock._comando_inicio()))
        c.addWidget(fila("Abrir al iniciar Windows", "mibarra se abre sola cuando prendes el PC.", inicio))
        capa.addWidget(t)

    # -------------------------------------------------------------------------
    # Página: Clima
    # -------------------------------------------------------------------------
    def _pagina_clima(self, capa):
        clima = self.dock.config.setdefault("clima", {})
        t, c = tarjeta()
        c.addWidget(etiqueta("Ciudad actual", "suave"))
        c.addWidget(etiqueta(clima.get("ciudad", "Santiago"), "titulo"))
        c.addWidget(etiqueta(f"Latitud {clima.get('latitud', -33.45)} · Longitud {clima.get('longitud', -70.66)}",
                             "suave"))
        capa.addWidget(t)

        capa.addWidget(etiqueta("Cambiar ciudad", "seccion"))
        t2, c2 = tarjeta()
        renglon = QHBoxLayout()
        self.campo_ciudad = QLineEdit()
        self.campo_ciudad.setObjectName("campo")
        self.campo_ciudad.setPlaceholderText("Escribe una ciudad, por ejemplo Puente Alto")
        buscar = boton("Buscar", "pillAzul")
        buscar.clicked.connect(self._buscar_ciudad)
        self.campo_ciudad.returnPressed.connect(self._buscar_ciudad)
        renglon.addWidget(self.campo_ciudad, 1)
        renglon.addWidget(buscar)
        c2.addLayout(renglon)
        self.resultados_ciudad = QVBoxLayout()
        self.resultados_ciudad.setSpacing(6)
        c2.addLayout(self.resultados_ciudad)
        capa.addWidget(t2)

    def _buscar_ciudad(self):
        texto = self.campo_ciudad.text().strip()
        if not texto:
            return
        self._vaciar(self.resultados_ciudad)
        self.resultados_ciudad.addWidget(etiqueta("Buscando…", "suave"))
        self.buscador.buscar(texto)

    def _ciudades_encontradas(self, resultados):
        try:
            self._mostrar_ciudades(resultados)
        except RuntimeError:
            pass   # la página se rearmó mientras buscábamos: no importa

    def _mostrar_ciudades(self, resultados):
        if self.pagina_actual != "clima":
            return
        self._vaciar(self.resultados_ciudad)
        if resultados is None:
            self.resultados_ciudad.addWidget(etiqueta("No pude conectarme. Revisa tu internet.", "suave"))
            return
        if not resultados:
            self.resultados_ciudad.addWidget(etiqueta("No encontré esa ciudad.", "suave"))
            return
        for r in resultados:
            partes = [r.get("name"), r.get("admin1"), r.get("country")]
            texto = ", ".join(x for x in partes if x)
            b = boton(texto, "pill")
            b.clicked.connect(lambda _, r=r: self._elegir_ciudad(r))
            self.resultados_ciudad.addWidget(b, 0, Qt.AlignmentFlag.AlignLeft)

    def _elegir_ciudad(self, r):
        self.dock.config["clima"] = {"ciudad": r.get("name", "Ciudad"),
                                     "latitud": round(r["latitude"], 4),
                                     "longitud": round(r["longitude"], 4)}
        self._guardar("widgets")
        self.refrescar()

    # -------------------------------------------------------------------------
    # Página: Moneda
    # -------------------------------------------------------------------------
    MONEDAS = [("CLP", "Peso chileno"), ("USD", "Dólar"), ("EUR", "Euro"), ("ARS", "Peso argentino"),
               ("PEN", "Sol peruano"), ("MXN", "Peso mexicano"), ("BRL", "Real"), ("JPY", "Yen")]

    def _pagina_moneda(self, capa):
        m = self.dock.config.setdefault("moneda", {"cantidad": 1, "desde": "USD", "hacia": "CLP"})
        if "moneda" not in self.dock.config.get("widgets", []):
            aviso, ca = tarjeta()
            renglon = QHBoxLayout()
            renglon.addWidget(etiqueta("El widget Moneda no está en tu barra.", "suave"), 1)
            agregar = boton("＋ Agregar a la barra", "pillAzul")
            agregar.clicked.connect(lambda: self._alternar_widget("moneda"))
            renglon.addWidget(agregar)
            ca.addLayout(renglon)
            capa.addWidget(aviso)

        t, c = tarjeta()
        self.campo_cantidad = QLineEdit(f"{float(m.get('cantidad', 1)):g}")
        self.campo_desde = QLineEdit(m.get("desde", "USD"))
        self.campo_hacia = QLineEdit(m.get("hacia", "CLP"))
        for campo, ancho in ((self.campo_cantidad, 100), (self.campo_desde, 80), (self.campo_hacia, 80)):
            campo.setObjectName("campo")
            campo.setFixedWidth(ancho)
        self.campo_desde.setMaxLength(3)
        self.campo_hacia.setMaxLength(3)
        c.addWidget(fila("Cantidad", "Cuánto quieres convertir.", self.campo_cantidad))
        c.addWidget(linea())
        c.addWidget(fila("Desde", "Código de 3 letras, ej. USD.", self.campo_desde))
        c.addWidget(linea())
        c.addWidget(fila("Hacia", "Código de 3 letras, ej. CLP.", self.campo_hacia))
        capa.addWidget(t)

        capa.addWidget(etiqueta("Monedas comunes (clic para usar como destino)", "seccion"))
        t2, c2 = tarjeta()
        grilla = QGridLayout()
        grilla.setSpacing(8)
        for n, (codigo, nombre) in enumerate(self.MONEDAS):
            b = boton(f"{codigo} · {nombre}", "pill")
            b.clicked.connect(lambda _, cod=codigo: self.campo_hacia.setText(cod))
            grilla.addWidget(b, n // 4, n % 4)
        c2.addLayout(grilla)
        capa.addWidget(t2)

        guardar = boton("Guardar", "pillAzul")
        guardar.clicked.connect(self._guardar_moneda)
        capa.addWidget(guardar, 0, Qt.AlignmentFlag.AlignLeft)

    def _guardar_moneda(self):
        try:
            cantidad = float(self.campo_cantidad.text().replace(",", "."))
        except ValueError:
            cantidad = 1
        self.dock.config["moneda"] = {
            "cantidad": cantidad,
            "desde": (self.campo_desde.text().strip().upper() or "USD")[:3],
            "hacia": (self.campo_hacia.text().strip().upper() or "CLP")[:3],
        }
        self._guardar("widgets")
        self.refrescar()

    # -------------------------------------------------------------------------
    # Página: Acerca de
    # -------------------------------------------------------------------------
    def _pagina_acerca(self, capa):
        from logo import dibujar_logo
        from version import REPOSITORIO

        # --- Cabecera con logo, versión y actualizaciones ---
        t, c = tarjeta()
        renglon = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(dibujar_logo(128).scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio,
                                                 Qt.TransformationMode.SmoothTransformation))
        renglon.addWidget(logo)
        renglon.addSpacing(8)
        textos = QVBoxLayout()
        textos.setSpacing(2)
        textos.addWidget(etiqueta("mibarra", "titulo"))
        textos.addWidget(etiqueta(f"Versión {VERSION} · Licencia MIT · Hecha en Python con PyQt6", "suave"))
        self.estado_actualizacion = etiqueta("", "suave")
        textos.addWidget(self.estado_actualizacion)
        renglon.addLayout(textos, 1)
        buscar = boton("Buscar actualizaciones", "pill")
        buscar.clicked.connect(self._buscar_actualizacion)
        renglon.addWidget(buscar, 0, Qt.AlignmentFlag.AlignVCenter)
        c.addLayout(renglon)
        c.addWidget(linea())
        avisar = Interruptor(bool(self.dock.config.get("buscar_actualizaciones", True)))
        avisar.cambiado.connect(lambda v: self._poner("buscar_actualizaciones", v, "apps"))
        c.addWidget(fila("Avisarme cuando haya una versión nueva", "Revisa GitHub al abrir mibarra.", avisar))
        capa.addWidget(t)

        # --- Tus ajustes ---
        capa.addWidget(etiqueta("Tus ajustes", "seccion"))
        t2, c2 = tarjeta()
        exportar = boton("Exportar…", "pill")
        exportar.clicked.connect(self._exportar)
        c2.addWidget(fila("Respaldar", "Guarda tus ajustes en un archivo (para otro PC o por si acaso).", exportar))
        c2.addWidget(linea())
        importar = boton("Importar…", "pill")
        importar.clicked.connect(self._importar)
        c2.addWidget(fila("Recuperar", "Carga ajustes desde un respaldo.", importar))
        c2.addWidget(linea())
        restablecer = boton("Restablecer", "pillRojo")
        restablecer.clicked.connect(self._restablecer)
        c2.addWidget(fila("Valores de fábrica", "Vuelve todo a como venía. Tus notas no se borran.", restablecer))
        capa.addWidget(t2)

        # --- Ayuda ---
        capa.addWidget(etiqueta("Ayuda", "seccion"))
        t3, c3 = tarjeta()
        carpeta = boton("Abrir carpeta", "pill")
        carpeta.clicked.connect(lambda: abrir(str(rutas.CARPETA_DATOS)))
        c3.addWidget(fila("Carpeta de datos", "Donde están tus ajustes, notas y el registro de errores.", carpeta))
        c3.addWidget(linea())
        registro_b = boton("Ver registro", "pill")
        registro_b.clicked.connect(lambda: abrir(str(rutas.ARCHIVO_REGISTRO)))
        c3.addWidget(fila("Registro de errores", "Si algo falla, adjunta este archivo al reportarlo.", registro_b))
        c3.addWidget(linea())
        reportar = boton("Reportar un problema", "pill")
        reportar.clicked.connect(lambda: webbrowser.open(f"https://github.com/{REPOSITORIO}/issues/new/choose"))
        c3.addWidget(fila("¿Encontraste un error o tienes una idea?", "Cuéntalo en GitHub.", reportar))
        c3.addWidget(linea())
        pagina = boton("Abrir GitHub", "pill")
        pagina.clicked.connect(lambda: webbrowser.open(f"https://github.com/{REPOSITORIO}"))
        c3.addWidget(fila("Página del proyecto", "Código, novedades y descargas.", pagina))
        capa.addWidget(t3)

        # --- Privacidad ---
        capa.addWidget(etiqueta("Privacidad", "seccion"))
        t4, c4 = tarjeta()
        c4.addWidget(etiqueta(
            "mibarra no tiene cuentas ni envía datos tuyos a ningún servidor propio. Solo se conecta a "
            "internet para: el clima (Open-Meteo, con la ciudad que elijas), la moneda (open.er-api.com, "
            "con las monedas que elijas) y revisar si hay versiones nuevas (GitHub). Tus notas y ajustes "
            "se quedan en tu PC.", "suave"))
        capa.addWidget(t4)

        # --- Barra ---
        t5, c5 = tarjeta()
        recargar = boton("Recargar mibarra", "pill")
        recargar.clicked.connect(self.dock.reiniciar)
        c5.addWidget(fila("Recargar", "Cierra y vuelve a abrir la barra.", recargar))
        c5.addWidget(linea())
        salir = boton("Cerrar mibarra", "pillRojo")
        salir.clicked.connect(QApplication.quit)
        c5.addWidget(fila("Salir", "La barra de Windows vuelve a la normalidad.", salir))
        capa.addWidget(t5)

    def _buscar_actualizacion(self):
        self.estado_actualizacion.setText("Buscando…")

        def listo(ok, info):
            try:
                if not ok:
                    self.estado_actualizacion.setText("No pude conectarme a GitHub. Revisa tu internet.")
                elif info:
                    self.estado_actualizacion.setText(
                        f"<b>Hay una versión nueva: {info['version']}</b> · "
                        f"<a href=\"{info['url']}\">Descargar</a>")
                    self.estado_actualizacion.setOpenExternalLinks(True)
                else:
                    self.estado_actualizacion.setText("✓ Tienes la última versión.")
            except RuntimeError:
                pass   # la página se cerró mientras buscábamos

        self.dock.revisar_actualizaciones(al_terminar=listo)

    def _exportar(self):
        destino, _ = QFileDialog.getSaveFileName(self, "Guardar respaldo de ajustes",
                                                 str(Path.home() / "mibarra-ajustes.json"), "Ajustes (*.json)")
        if destino:
            Path(destino).write_text(json.dumps(self.dock.config, ensure_ascii=False, indent=2), encoding="utf-8")

    def _importar(self):
        origen, _ = QFileDialog.getOpenFileName(self, "Cargar respaldo de ajustes", str(Path.home()),
                                                "Ajustes (*.json)")
        if not origen:
            return
        try:
            datos = json.loads(Path(origen).read_text(encoding="utf-8"))
            if not isinstance(datos, dict):
                raise ValueError
        except (OSError, ValueError):
            QMessageBox.warning(self, "No se pudo importar", "Ese archivo no es un respaldo de mibarra válido.")
            return
        nuevo = dict(configuracion.por_defecto())
        nuevo.update(datos)
        self._reemplazar_config(configuracion.validar(nuevo))

    def _restablecer(self):
        respuesta = QMessageBox.question(
            self, "Restablecer mibarra",
            "¿Volver todos los ajustes a como venían? Tus notas no se borran.\n\n"
            "Consejo: antes puedes usar «Exportar…» para guardar un respaldo.")
        if respuesta == QMessageBox.StandardButton.Yes:
            self._reemplazar_config(configuracion.por_defecto())

    def _reemplazar_config(self, nuevo):
        # Cambiamos el CONTENIDO del diccionario (no el diccionario), porque los widgets
        # guardan una referencia a él.
        self.dock.config.clear()
        self.dock.config.update(nuevo)
        self._guardar("todo")
        self.refrescar()

"""
bienvenida.py — la pantalla que aparece la PRIMERA vez que abres mibarra,
y el "aviso" flotante (por ejemplo, cuando hay una versión nueva).
"""

import webbrowser

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QApplication, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
                             QVBoxLayout, QWidget)

from ajustes import (COLORES_ACENTO, HOJA, MuestraColor, Segmentado, boton, etiqueta, fila, linea,
                     tarjeta)
from logo import dibujar_logo


class VentanaFlotante(QWidget):
    """Base: ventana sin bordes, con esquinas redondeadas, sombra y que se arrastra."""

    def __init__(self, ancho, alto, flags=Qt.WindowType.Window):
        super().__init__(None, flags | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(HOJA)
        self.resize(ancho, alto)
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

    def mousePressEvent(self, evento):
        if evento.button() == Qt.MouseButton.LeftButton and self.windowHandle():
            self.windowHandle().startSystemMove()


class Bienvenida(VentanaFlotante):
    def __init__(self, dock):
        super().__init__(600, 640)
        self.dock = dock
        self.setWindowTitle("Bienvenido a mibarra")
        capa = QVBoxLayout(self.ventana)
        capa.setContentsMargins(36, 30, 36, 26)
        capa.setSpacing(12)

        logo = QLabel()
        logo.setPixmap(dibujar_logo(144).scaled(72, 72, Qt.AspectRatioMode.KeepAspectRatio,
                                                 Qt.TransformationMode.SmoothTransformation))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        capa.addWidget(logo)
        titulo = etiqueta("Bienvenido a mibarra", "titulo")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        capa.addWidget(titulo)
        subtitulo = etiqueta("Tu nueva barra para Windows. Elige cómo quieres que se vea; "
                             "puedes cambiarlo cuando quieras en Ajustes.", "suave")
        subtitulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        capa.addWidget(subtitulo)
        capa.addSpacing(6)

        cfg = dock.config
        t, c = tarjeta()
        tema = Segmentado([("oscuro", "Oscuro"), ("claro", "Claro"), ("auto", "Automático")], cfg["tema"])
        tema.cambiado.connect(lambda v: self._poner("tema", v))
        c.addWidget(fila("Tema", None, tema))
        c.addWidget(linea())
        forma = Segmentado([("centro", "Centrada"), ("completa", "Ancho completo")], cfg["alineacion"])
        forma.cambiado.connect(lambda v: self._poner("alineacion", v))
        c.addWidget(fila("Forma", None, forma))
        c.addWidget(linea())
        self.colores = QWidget()
        self._armar_colores()
        c.addWidget(fila("Color", None, self.colores))
        capa.addWidget(t)

        t2, c2 = tarjeta()
        consejos = [
            ("#0a84ff", "Clic derecho en un espacio vacío de la barra", "para abrir los Ajustes y agregar widgets."),
            ("#30d158", "Pasa el mouse sobre cualquier cosa", "y te explica qué hace."),
            ("#ff9f0a", "Tranquilo si algo falla", "la barra de Windows vuelve sola al cerrar mibarra."),
        ]
        for i, (color, fuerte, resto) in enumerate(consejos):
            renglon = QHBoxLayout()
            punto = QLabel()
            punto.setFixedSize(10, 10)
            punto.setStyleSheet(f"background: {color}; border-radius: 5px;")
            renglon.addWidget(punto, 0, Qt.AlignmentFlag.AlignTop)
            renglon.addSpacing(6)
            texto = etiqueta(f"<b>{fuerte}</b> {resto}")
            renglon.addWidget(texto, 1)
            c2.addLayout(renglon)
            if i < len(consejos) - 1:
                c2.addWidget(linea())
        capa.addWidget(t2)
        capa.addStretch()

        empezar = boton("Empezar", "pillAzul")
        empezar.setMinimumHeight(36)
        empezar.setStyleSheet("font-size: 14px;")
        empezar.clicked.connect(self.close)
        capa.addWidget(empezar)

    def _armar_colores(self):
        capa = self.colores.layout() or QHBoxLayout(self.colores)
        while capa.count():
            capa.takeAt(0).widget().deleteLater()
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(2)
        for color in COLORES_ACENTO:
            m = MuestraColor(color, color.lower() == self.dock.config["color_acento"].lower())
            m.elegido.connect(lambda col: (self._poner("color_acento", col), self._armar_colores()))
            capa.addWidget(m)

    def _poner(self, clave, valor):
        self.dock.config[clave] = valor
        self.dock.aplicar_config("todo")

    def mostrar(self):
        pantalla = QApplication.primaryScreen().availableGeometry()
        self.move(pantalla.center().x() - self.width() // 2,
                  max(pantalla.top() + 10, pantalla.center().y() - self.height() // 2 - 40))
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, evento):
        self.dock.config["bienvenida_vista"] = True
        self.dock.aplicar_config("apps")   # solo guarda
        super().closeEvent(evento)


class Aviso(VentanaFlotante):
    """Un cartelito sobre la barra, que se cierra solo después de un rato."""

    def __init__(self, titulo, texto, boton_texto=None, url=None, segundos=15):
        super().__init__(430, 130, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        capa = QHBoxLayout(self.ventana)
        capa.setContentsMargins(16, 12, 12, 12)
        capa.setSpacing(12)
        logo = QLabel()
        logo.setPixmap(dibujar_logo(80).scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio,
                                                Qt.TransformationMode.SmoothTransformation))
        capa.addWidget(logo, 0, Qt.AlignmentFlag.AlignVCenter)
        textos = QVBoxLayout()
        textos.setSpacing(2)
        textos.addWidget(etiqueta(titulo, "negrita"))
        textos.addWidget(etiqueta(texto, "suave"))
        capa.addLayout(textos, 1)
        if boton_texto and url:
            b = boton(boton_texto, "pillAzul")
            b.clicked.connect(lambda: (webbrowser.open(url), self.close()))
            capa.addWidget(b, 0, Qt.AlignmentFlag.AlignVCenter)
        cerrar = boton("✕", "cerrar")
        cerrar.clicked.connect(self.close)
        capa.addWidget(cerrar, 0, Qt.AlignmentFlag.AlignTop)
        QTimer.singleShot(segundos * 1000, self.close)

    def mostrar_sobre(self, dock):
        g = dock.geometry()
        pantalla = QApplication.primaryScreen().availableGeometry()
        if getattr(dock, "_oculta_auto", False) or not dock.isVisible():
            # La barra está escondida: el aviso va pegado al borde de la pantalla
            y = pantalla.bottom() - self.height() if dock.abajo else pantalla.top()
            x = pantalla.center().x() - self.width() // 2
        else:
            y = g.top() - self.height() + 14 if dock.abajo else g.bottom() - 14
            x = g.center().x() - self.width() // 2
        self.move(x, y)
        self.show()
        self.raise_()

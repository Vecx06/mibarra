"""
dock.py — la barra en sí: botón de inicio, apps y widgets.

Orden de izquierda a derecha:
  [Inicio] | [apps fijadas] | [apps abiertas no fijadas] ....... [widgets] [mostrar escritorio]

Cada 0,7 s la barra pregunta a Windows qué ventanas hay abiertas y actualiza los íconos.
Cada 1 s actualiza los widgets (hora, CPU, RAM...).
"""

import os
import time
from pathlib import Path

from PyQt6.QtCore import (QEasingCurve, QFileInfo, QPoint, QProcess, QPropertyAnimation, QRect,
                          QRectF, QSize, Qt, QTimer, QVariantAnimation)
from PyQt6.QtGui import QColor, QCursor, QIcon, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QFileIconProvider, QHBoxLayout, QWidget

import config as configuracion
import mas_widgets
import widgets as modulo_widgets
from atajos import Atajos
import rutas
from registro import log
import estilo
import sistema_windows as sw
from widgets import (AnioTile, BandejaTile, BateriaTile, Caja, ClimaTile, CpuTile, DiscoTile,
                     EnfoqueTile, InsigniaQuitar, MusicaWidget, RamTile, RedTile, RelojTile,
                     VolumenTile, abrir, aplicar_visibilidad, crear_menu, recortar)

# =============================================================================
# Íconos de programas
# =============================================================================
_proveedor = None
_iconos = {}


def icono_de(ruta):
    """Saca el ícono de un .exe (Windows ya lo tiene guardado dentro del archivo)."""
    global _proveedor
    if not ruta or not os.path.exists(ruta):
        return QIcon()
    if ruta not in _iconos:
        if _proveedor is None:
            _proveedor = QFileIconProvider()
        _iconos[ruta] = _proveedor.icon(QFileInfo(ruta))
    return _iconos[ruta]


def nombre_desde_ruta(ruta):
    """C:\\...\\spotify.exe -> 'Spotify'"""
    nombre = Path(ruta).stem
    return nombre[:1].upper() + nombre[1:]


# Colores para los íconos "de letra" (apps sin ícono)
_COLORES_LETRA = ["#5b8def", "#e5734a", "#4cb782", "#b765d8", "#e2b93b", "#e0567a", "#3fb6c6"]


# =============================================================================
# Piezas pequeñas
# =============================================================================
class Separador(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedWidth(11)

    def paintEvent(self, evento):
        p = QPainter(self)
        p.setPen(QPen(estilo.BORDE, 1))
        x = self.width() // 2
        margen = int(self.height() * 0.25)
        p.drawLine(x, margen, x, self.height() - margen)
        p.end()


class BotonInicio(Caja):
    def __init__(self, lado, dock):
        super().__init__()
        self.setFixedSize(lado, lado)
        if dock.config.get("boton_inicio") == "buscador":
            self.setToolTip("Buscar programas, carpetas y más\nClic derecho: menú rápido de Windows")
            self.clic.connect(dock.abrir_buscador)
        else:
            self.setToolTip("Inicio\nClic derecho: menú rápido (apagar, ajustes...)")
            self.clic.connect(lambda: sw.presionar_teclas(sw.VK_LWIN))
        self.clic_derecho.connect(lambda _: sw.presionar_teclas(sw.VK_LWIN, sw.VK_X))

    def pintar_fondo(self, p):
        if self._hover:
            super().pintar_fondo(p)

    def pintar(self, p):
        # Cuatro cuadraditos redondeados en el color de acento
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(estilo.ACENTO)
        t = self.width() * 0.19
        hueco = t * 0.22
        x0 = (self.width() - (2 * t + hueco)) / 2
        y0 = (self.height() - (2 * t + hueco)) / 2
        for fila in range(2):
            for columna in range(2):
                p.drawRoundedRect(QRectF(x0 + columna * (t + hueco), y0 + fila * (t + hueco), t, t), 2.5, 2.5)


class BotonEscritorio(Caja):
    """La franjita del extremo derecho: muestra el escritorio (Windows + D)."""

    def __init__(self, alto):
        super().__init__(radio=4)
        self.setFixedSize(8, alto)
        self.setToolTip("Mostrar escritorio")
        self.clic.connect(lambda: sw.presionar_teclas(sw.VK_LWIN, sw.VK_D))

    def pintar_fondo(self, p):
        if self._hover:
            super().pintar_fondo(p)

    def pintar(self, p):
        p.setPen(QPen(estilo.BORDE, 1))
        p.drawLine(1, int(self.height() * 0.2), 1, int(self.height() * 0.8))


class BotonApp(Caja):
    """Un ícono de app. Crece un poquito al pasar el mouse y muestra un punto si está abierta."""

    def __init__(self, dock, clave, nombre, ruta, emoji=None, fijada=False):
        super().__init__(radio=10)
        self.dock = dock
        self.clave = clave
        self.nombre = nombre
        self.ruta = ruta
        self.emoji = emoji
        self.fijada = fijada
        self.ventanas = []
        self.activa = False
        self.icono = icono_de(ruta)
        self._escala = 1.0

        lado = dock.lado_boton
        self.setFixedSize(lado, lado)
        self.setToolTip(nombre)

        # Animación: va cambiando self._escala de a poco (en 140 ms)
        self.animacion = QVariantAnimation(self)
        self.animacion.setDuration(140)
        self.animacion.valueChanged.connect(self._nueva_escala)

        self.clic.connect(lambda: dock.clic_app(self))
        self.clic_derecho.connect(lambda pos: dock.menu_app(self, pos))

    def mouseReleaseEvent(self, evento):
        if evento.button() == Qt.MouseButton.MiddleButton and self.ruta:
            abrir(self.ruta)                  # clic con la rueda = abrir otra ventana
            return
        super().mouseReleaseEvent(evento)

    def wheelEvent(self, evento):
        # Girar la rueda sobre el ícono = pasar de una ventana a otra de esa app
        if self.ventanas:
            self.dock.ciclar_ventanas(self, 1 if evento.angleDelta().y() < 0 else -1)

    def _animar(self, hacia):
        self.animacion.stop()
        self.animacion.setStartValue(self._escala)
        self.animacion.setEndValue(hacia)
        self.animacion.start()

    def _nueva_escala(self, valor):
        self._escala = float(valor)
        self.update()

    def enterEvent(self, evento):
        super().enterEvent(evento)
        self._animar(1.15)

    def leaveEvent(self, evento):
        super().leaveEvent(evento)
        self._animar(1.0)

    def actualizar_estado(self, ventanas, activa):
        cambio = (len(ventanas) != len(self.ventanas) or activa != self.activa
                  or [v.titulo for v in ventanas] != [v.titulo for v in self.ventanas])
        self.ventanas = ventanas
        self.activa = activa
        if cambio:
            if ventanas:
                titulos = [v.titulo for v in ventanas[:6]]
                self.setToolTip("\n".join(titulos) if len(ventanas) > 1 or not self.fijada
                                else f"{self.nombre} — {titulos[0]}")
            else:
                self.setToolTip(self.nombre)
            self.update()

    def pintar_fondo(self, p):
        if self._hover or self.activa:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(estilo.CAJA_HOVER if self._hover else estilo.CAJA)
            p.drawRoundedRect(QRectF(self.rect()), self.radio, self.radio)

    def pintar(self, p):
        lado = self.width() * 0.6 * self._escala
        cx, cy = self.width() / 2, self.height() / 2 - 2
        zona = QRectF(cx - lado / 2, cy - lado / 2, lado, lado)

        if not self.icono.isNull():
            pixmap = self.icono.pixmap(QSize(64, 64))
            p.drawPixmap(zona.toRect(), pixmap)
        elif self.emoji:
            p.setFont(estilo.fuente(int(lado * 0.8)))
            p.setPen(estilo.TEXTO)
            p.drawText(zona, Qt.AlignmentFlag.AlignCenter, self.emoji)
        else:
            # Sin ícono: un cuadrado de color con la primera letra del nombre
            color = QColor(_COLORES_LETRA[sum(map(ord, self.nombre)) % len(_COLORES_LETRA)])
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            p.drawRoundedRect(zona, lado * 0.25, lado * 0.25)
            p.setPen(QColor("white"))
            p.setFont(estilo.fuente(int(lado * 0.5), negrita=True))
            p.drawText(zona, Qt.AlignmentFlag.AlignCenter, (self.nombre or "?")[:1].upper())

        # Indicador abajo: punto = abierta, rayita de color = es la ventana activa
        if self.ventanas:
            ancho = 14 if self.activa else 5
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(estilo.ACENTO if self.activa else estilo.TEXTO_SUAVE)
            p.drawRoundedRect(QRectF(cx - ancho / 2, self.height() - 5, ancho, 3), 1.5, 1.5)


# =============================================================================
# La barra
# =============================================================================
class Dock(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.abajo = config.get("posicion", "abajo") != "arriba"
        self.alto = int(config.get("alto", 56))
        self.margen = int(config.get("margen", 8))
        self.vidrio = config.get("estilo") == "vidrio" and sw.ES_WINDOWS
        self.lado_boton = self.alto - 16

        estilo.poner_tema(self._tema_resuelto())
        self.setWindowTitle("mibarra")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.WindowStaysOnTopHint
                            | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.barra_windows = sw.BarraWindows()
        self.espacio = None
        self.ultima_activa = None
        self.botones = {}
        self.widgets = []
        self._firma = None
        self._escondida = False
        self._limpio = False
        self._modo_edicion = False
        self.ventana_ajustes = None
        self.widgets_sin_espacio = []
        self.buscador = None
        self.atajos = None
        self._oculta_auto = False          # escondida por "ocultar automáticamente"
        self._oculta_usuario = False       # escondida con el atajo de teclado
        self._ultimo_dentro = time.monotonic()
        modulo_widgets.avisar = self.mostrar_aviso

        # La fila principal. Su contenido se arma en _armar_todo() (y se puede rearmar en vivo)
        self.capa = QHBoxLayout(self)
        self.capa.setContentsMargins(10, 8, 6, 8)
        self.capa.setSpacing(6)
        self._armar_todo()

        # --- Relojes internos (timers) ---
        self._timer(1000, self._actualizar_widgets)
        self._timer(700, self._refrescar_apps)
        self._timer(400, self._vigilar)      # rápido, para esconderse apenas pongas pantalla completa
        self._timer(120, self._vigilar_auto_ocultar)

        self._refrescar_apps()
        self._actualizar_widgets()

    # -------------------------------------------------------------------------
    # Armar (y rearmar) el contenido de la barra
    # -------------------------------------------------------------------------
    @staticmethod
    def _vaciar(capa):
        """Saca y borra todo lo que hay dentro de una capa (layout)."""
        while capa.count():
            item = capa.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _detener_widgets(self):
        for w in self.widgets:
            if hasattr(w, "detener"):
                w.detener()     # que los hilos (clima, música) dejen de trabajar
        self.widgets = []

    def _armar_todo(self):
        """[Inicio] | [apps] ...espacio... [widgets] [escritorio]"""
        self._detener_widgets()
        self._vaciar(self.capa)

        self.capa.addWidget(BotonInicio(self.lado_boton, self))
        self.capa.addWidget(Separador())

        self.zona_apps = QWidget()
        self.capa_apps = QHBoxLayout(self.zona_apps)
        self.capa_apps.setContentsMargins(0, 0, 0, 0)
        self.capa_apps.setSpacing(4)
        self.capa.addWidget(self.zona_apps)
        if self._centrada():
            self.capa.addWidget(Separador())   # centrada: sin espacio vacío, solo una rayita
        else:
            self.capa.addStretch()             # ancho completo: un "resorte" empuja los widgets a la derecha

        self.zona_widgets = QWidget()
        self.capa_widgets = QHBoxLayout(self.zona_widgets)
        self.capa_widgets.setContentsMargins(0, 0, 0, 0)
        self.capa_widgets.setSpacing(6)
        self.capa.addWidget(self.zona_widgets)

        self.capa.addWidget(BotonEscritorio(self.lado_boton))

        self.botones = {}
        self._firma = None
        self._armar_widgets()

    def _armar_widgets(self):
        self._detener_widgets()
        self._vaciar(self.capa_widgets)
        for nombre in self.config.get("widgets", []):
            w = self._crear_widget(nombre)
            if w is not None:
                w.id_widget = nombre
                self.capa_widgets.addWidget(w)
                self.widgets.append(w)
        if self._modo_edicion:
            self._poner_insignias()
        self._actualizar_widgets()
        QTimer.singleShot(0, self._ajustar_ancho)

    # -------------------------------------------------------------------------
    # Aplicar cambios hechos en la ventana de Ajustes (sin reiniciar)
    # -------------------------------------------------------------------------
    def aplicar_config(self, que="todo"):
        """que = "apps" | "widgets" | "atajos" | "todo" """
        configuracion.guardar(self.config)
        if que == "atajos":
            self._configurar_atajos()
            return
        if que == "apps":
            self._firma = None
            self._refrescar_apps()
            return
        if que == "widgets":
            self._armar_widgets()
            return

        c = self.config
        self.abajo = c.get("posicion", "abajo") != "arriba"
        self.alto = int(c.get("alto", 56))
        self.margen = int(c.get("margen", 8))
        self.lado_boton = self.alto - 16
        estilo.poner_acento(c.get("color_acento", "#7aa2ff"))
        QApplication.instance().setStyleSheet(estilo.hoja_global())

        hwnd = int(self.winId())
        quiere_vidrio = c.get("estilo") == "vidrio" and sw.ES_WINDOWS
        estilo.poner_tema(self._tema_resuelto())
        if quiere_vidrio:
            if sw.aplicar_vidrio(hwnd, 0x99, *estilo.TINTE_VIDRIO):
                sw.redondear_esquinas(hwnd)
                self.vidrio = True
        elif not quiere_vidrio and self.vidrio:
            sw.quitar_vidrio(hwnd)
            self.vidrio = False

        if c.get("ocultar_barra_windows", True) and not self.barra_windows.oculta:
            self.barra_windows.ocultar()
        elif not c.get("ocultar_barra_windows", True) and self.barra_windows.oculta:
            self.barra_windows.restaurar()
        if not c.get("reservar_espacio", True) and self.espacio is not None:
            self.espacio.liberar()
        if que == "todo":
            self._configurar_atajos()

        self._armar_todo()
        self._refrescar_apps()
        self.ubicar()
        self.update()

    # -------------------------------------------------------------------------
    # Modo edición (mientras los Ajustes están abiertos)
    # -------------------------------------------------------------------------
    def modo_edicion(self, activo):
        self._modo_edicion = activo
        if activo:
            self._poner_insignias()
        else:
            for w in self.widgets:
                for insignia in w.findChildren(InsigniaQuitar):
                    insignia.deleteLater()

    def _poner_insignias(self):
        for w in self.widgets:
            if not w.findChildren(InsigniaQuitar):
                InsigniaQuitar(w, lambda nombre=w.id_widget: self.quitar_widget(nombre))

    def quitar_widget(self, nombre):
        if nombre in self.config.get("widgets", []):
            self.config["widgets"].remove(nombre)
            self.aplicar_config("widgets")
            if self.ventana_ajustes is not None:
                self.ventana_ajustes.refrescar()

    # -------------------------------------------------------------------------
    # Bienvenida y actualizaciones
    # -------------------------------------------------------------------------
    def mostrar_bienvenida(self):
        from bienvenida import Bienvenida
        self._bienvenida = Bienvenida(self)
        self._bienvenida.mostrar()

    def revisar_actualizaciones(self, al_terminar=None):
        """
        Pregunta a GitHub (en otro hilo) si hay versión nueva.
        Sin al_terminar: si hay una, muestra un aviso sobre la barra.
        Con al_terminar: le entrega el resultado a esa función (la usan los Ajustes).
        """
        import actualizaciones
        from widgets import TrabajoUnaVez

        def recibir(respuesta):
            ok, info = respuesta
            if al_terminar is not None:
                al_terminar(ok, info)
            elif ok and info:
                from bienvenida import Aviso
                self._aviso = Aviso(f"mibarra {info['version']} ya está disponible",
                                    "Trae mejoras y arreglos. Tus ajustes se mantienen al actualizar.",
                                    "Ver novedades", info["url"])
                self._aviso.mostrar_sobre(self)
            if not ok:
                log.info("No pude revisar actualizaciones: %s", info)

        self._trabajo_actualizacion = TrabajoUnaVez(actualizaciones.consultar)
        self._trabajo_actualizacion.listo.connect(recibir)
        self._trabajo_actualizacion.empezar()

    def abrir_ajustes(self, pagina=None):
        from ajustes import Ajustes   # se importa aquí para no cargarlo si nunca se usa
        if self.ventana_ajustes is None:
            self.ventana_ajustes = Ajustes(self)
        self.ventana_ajustes.mostrar(pagina)

    def _tema_resuelto(self):
        tema = self.config.get("tema", "oscuro")
        if tema == "auto":
            return "claro" if sw.windows_usa_tema_claro() else "oscuro"
        return tema if tema in ("oscuro", "claro") else "oscuro"

    def _aplicar_tema(self):
        estilo.poner_tema(self._tema_resuelto())
        if self.vidrio:
            sw.aplicar_vidrio(int(self.winId()), 0x99, *estilo.TINTE_VIDRIO)
        self.update()
        for hijo in self.findChildren(QWidget):
            hijo.update()

    def _timer(self, cada_ms, funcion):
        t = QTimer(self)
        t.timeout.connect(funcion)
        t.start(cada_ms)
        return t

    def _crear_widget(self, nombre):
        alto = self.lado_boton
        if nombre in mas_widgets.CREADORES:
            return mas_widgets.CREADORES[nombre](alto, self.config, arriba=self.abajo)
        if nombre == "reloj":
            return RelojTile(alto, hacia_arriba=self.abajo)
        if nombre == "cpu":
            return CpuTile(alto)
        if nombre == "ram":
            return RamTile(alto)
        if nombre == "red":
            return RedTile(alto)
        if nombre == "bateria":
            return BateriaTile(alto)
        if nombre == "clima":
            return ClimaTile(alto, self.config.get("clima", {}))
        if nombre == "musica":
            return MusicaWidget(alto)
        if nombre == "volumen":
            return VolumenTile(alto)
        if nombre == "disco":
            return DiscoTile(alto)
        if nombre == "anio":
            return AnioTile(alto)
        if nombre == "enfoque":
            return EnfoqueTile(alto, self.config)
        if nombre == "bandeja":
            if not self.config.get("ocultar_barra_windows", True):
                return None   # si la barra de Windows queda visible, este botón no hace falta
            b = BandejaTile(alto)
            b.clic.connect(self._alternar_bandeja)
            return b
        log.warning("Widget desconocido en config.json: %r", nombre)
        return None

    # -------------------------------------------------------------------------
    # Arranque y ubicación
    # -------------------------------------------------------------------------
    def iniciar(self):
        """Se llama justo después de mostrar la barra (cuando Windows ya le dio un HWND)."""
        hwnd = int(self.winId())
        if self.vidrio:
            if sw.aplicar_vidrio(hwnd, 0x99, *estilo.TINTE_VIDRIO):
                sw.redondear_esquinas(hwnd)
            else:
                self.vidrio = False
        if self.config.get("ocultar_barra_windows", True):
            self.barra_windows.ocultar()
        self.espacio = sw.EspacioReservado(hwnd)
        self.ubicar()
        # Windows tarda un poquito en "soltar" el espacio de su barra: re-ubicamos al rato
        QTimer.singleShot(400, self.ubicar)
        QApplication.primaryScreen().geometryChanged.connect(lambda _: QTimer.singleShot(500, self.ubicar))
        self.atajos = Atajos()
        self.atajos.activado.connect(self._al_atajo)
        self._configurar_atajos()

    # -------------------------------------------------------------------------
    # Atajos de teclado, buscador y avisos
    # -------------------------------------------------------------------------
    def _configurar_atajos(self):
        if self.atajos is not None:
            self.atajos.empezar({"buscador": self.config.get("atajo_buscador", "alt+espacio"),
                                 "barra": self.config.get("atajo_barra", "ctrl+alt+b")})

    def _al_atajo(self, nombre):
        if nombre == "buscador":
            self.abrir_buscador()
        elif nombre == "barra":
            self.alternar_barra()

    def abrir_buscador(self):
        from buscador import Buscador
        if self.buscador is None:
            self.buscador = Buscador(self)
        self.buscador.alternar()

    def alternar_barra(self):
        """Mostrar / ocultar la barra con el atajo de teclado."""
        if self.config.get("auto_ocultar"):
            self._oculta_auto = not self._oculta_auto
            self._ultimo_dentro = time.monotonic() + 2     # que no se esconda apenas aparece
            self._ajustar_ancho()
        elif self._oculta_usuario:
            self._oculta_usuario = False
            self.show()
        else:
            self._oculta_usuario = True
            self.hide()

    def mostrar_aviso(self, titulo, texto, tipo="general"):
        if tipo == "ia" and not self.config.get("avisar_limite_ia", True):
            return
        from bienvenida import Aviso
        self._aviso_actual = Aviso(titulo, texto, segundos=12)
        self._aviso_actual.mostrar_sobre(self)

    def ciclar_ventanas(self, boton, paso):
        """Activa la siguiente (o anterior) ventana de esa app."""
        ventanas = boton.ventanas
        actual = next((i for i, v in enumerate(ventanas) if v.hwnd == self.ultima_activa), -1)
        siguiente = ventanas[(actual + paso) % len(ventanas)]
        sw.activar(siguiente.hwnd)
        self.ultima_activa = siguiente.hwnd

    # -------------------------------------------------------------------------
    # Ocultar automáticamente
    # -------------------------------------------------------------------------
    def _ocupada(self):
        """¿Hay algo abierto que necesita la barra visible? (menús, ajustes, escribiendo en Comando…)"""
        if QApplication.activePopupWidget() is not None:
            return True
        if self.ventana_ajustes is not None and self.ventana_ajustes.isVisible():
            return True
        foco = QApplication.focusWidget()
        return foco is not None and self.isAncestorOf(foco)

    def _vigilar_auto_ocultar(self):
        if not self.config.get("auto_ocultar"):
            if self._oculta_auto:
                self._oculta_auto = False
                self._ajustar_ancho()
            return
        if not self.isVisible():
            return
        cursor = QCursor.pos()
        pantalla = QApplication.primaryScreen().geometry()
        ahora = time.monotonic()
        if self._oculta_auto:
            en_borde = cursor.y() >= pantalla.bottom() - 1 if self.abajo else cursor.y() <= pantalla.top()
            if en_borde and self.x() - 60 <= cursor.x() <= self.x() + self.width() + 60:
                self._oculta_auto = False
                self._ultimo_dentro = ahora
                self._ajustar_ancho()
        else:
            cerca = self.geometry().adjusted(-16, -30, 16, 30).contains(cursor)
            if cerca or self._ocupada():
                self._ultimo_dentro = ahora
            elif ahora - self._ultimo_dentro > 1.0:
                self._oculta_auto = True
                self._ajustar_ancho()

    def ubicar(self):
        pantalla = QApplication.primaryScreen()
        escala = pantalla.devicePixelRatio()      # ej. 1.25 si Windows está al 125 %
        g = pantalla.geometry()
        grosor = self.alto + 2 * self.margen

        zona = None
        reservar = self.config.get("reservar_espacio", True) and not self.config.get("auto_ocultar")
        if not reservar and self.espacio is not None:
            self.espacio.liberar()
        if reservar and self.espacio is not None:
            # Windows trabaja en píxeles reales; Qt en píxeles "lógicos". Convertimos.
            real = (round(g.x() * escala), round(g.y() * escala),
                    round((g.x() + g.width()) * escala), round((g.y() + g.height()) * escala))
            r = self.espacio.reservar(self.abajo, real, round(grosor * escala))
            if r:
                zona = (r[0] / escala, r[1] / escala, (r[2] - r[0]) / escala)

        if zona is None:
            base = g if self.barra_windows.oculta else pantalla.availableGeometry()
            y = base.y() + base.height() - grosor if self.abajo else base.y()
            zona = (base.x(), y, base.width())

        self._zona = zona
        self._ajustar_ancho(animar=False)

    def _centrada(self):
        return self.config.get("alineacion", "centro") == "centro"

    def _medir(self):
        """Cuánto mide el contenido de la barra AHORA (recalculando las capas de adentro hacia afuera)."""
        for capa in (self.capa_apps, self.capa_widgets, self.capa):
            capa.invalidate()
            capa.activate()
        return self.capa.sizeHint().width()

    def _acomodar_desborde(self, disponible):
        """
        Si no caben todos los widgets, escondemos los de más a la izquierda
        (el reloj nunca se esconde) hasta que la barra quepa en la pantalla.
        """
        for w in self.widgets:
            if getattr(w, "sin_espacio", False):
                w.sin_espacio = False
                aplicar_visibilidad(w)
        candidatos = [w for w in self.widgets if w.id_widget != "reloj" and w.isVisibleTo(self)]
        while self._medir() > disponible and candidatos:
            w = candidatos.pop(0)
            w.sin_espacio = True
            aplicar_visibilidad(w)
        sin_espacio = [w.id_widget for w in self.widgets if getattr(w, "sin_espacio", False)]
        if sin_espacio != self.widgets_sin_espacio:
            self.widgets_sin_espacio = sin_espacio
            if sin_espacio:
                log.info("No caben todos los widgets; escondidos por espacio: %s", ", ".join(sin_espacio))

    def _ajustar_ancho(self, animar=True):
        """
        Centrada: la barra mide JUSTO lo que ocupa su contenido y queda al medio,
        como en Windows 11. Si abres o cierras apps, crece o se achica con una animación.
        Ancho completo: ocupa todo el borde de la pantalla.
        """
        if not hasattr(self, "_zona"):
            return
        x, y, ancho = self._zona
        disponible = ancho - 2 * self.margen
        self._acomodar_desborde(disponible)
        if self._centrada():
            medida = min(self._medir(), disponible)
            izquierda = x + self.margen + (disponible - medida) / 2
        else:
            medida, izquierda = disponible, x + self.margen
        y_visible = y + self.margen
        if self._oculta_auto:
            # Fuera de la pantalla (solo vuelve cuando el mouse toca el borde)
            y_visible = y + self.alto + 2 * self.margen + 2 if self.abajo else y - self.alto - 2
        destino = QRect(int(izquierda), int(y_visible), int(medida), self.alto)

        animacion = getattr(self, "_animacion", None)
        if not animar or not self.isVisible():
            if animacion is not None:
                animacion.stop()
            if destino != self.geometry():
                self.setGeometry(destino)
            return
        if animacion is not None and animacion.state() == QPropertyAnimation.State.Running:
            if animacion.endValue() == destino:
                return
            animacion.stop()
        elif destino == self.geometry():
            return
        self._animacion = QPropertyAnimation(self, b"geometry", self)
        self._animacion.setDuration(180)
        self._animacion.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animacion.setStartValue(self.geometry())
        self._animacion.setEndValue(destino)
        self._animacion.start()

    # -------------------------------------------------------------------------
    # Dibujo del fondo
    # -------------------------------------------------------------------------
    def paintEvent(self, evento):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.vidrio:
            radio = 8 if sw.es_windows_11() else 0   # Windows 11 redondea el vidrio ~8 px
            relleno = estilo.FONDO_VIDRIO
        else:
            radio = 16
            relleno = estilo.FONDO_SOLIDO
        p.setPen(QPen(estilo.BORDE, 1))
        p.setBrush(relleno)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), radio, radio)
        p.end()

    # -------------------------------------------------------------------------
    # Actualizaciones periódicas
    # -------------------------------------------------------------------------
    def _actualizar_widgets(self):
        for w in self.widgets:
            w.actualizar()
        self._ajustar_ancho()   # por si un widget apareció o desapareció (ej. batería)

    def _vigilar(self):
        self.barra_windows.vigilar()
        # En tema "auto", cada ~2 s revisamos si Windows cambió entre claro y oscuro
        self._vueltas = getattr(self, "_vueltas", 0) + 1
        if self.config.get("tema") == "auto" and self._vueltas % 5 == 0:
            if (self._tema_resuelto() == "claro") != estilo.ES_CLARO:
                self._aplicar_tema()
        if self.config.get("esconder_en_pantalla_completa", True):
            completa = sw.hay_pantalla_completa()
            if completa and self.isVisible():
                self.hide()
                self._escondida = True
            elif not completa and self._escondida:
                self.show()
                self._escondida = False

    def _refrescar_apps(self):
        ventanas = sw.listar_ventanas()
        activa = sw.ventana_activa()
        if activa and not sw.es_mia(activa):
            self.ultima_activa = activa

        # 1) Agrupar: una entrada por programa (todas las ventanas de Chrome juntas, etc.)
        grupos = {}
        for app in self.config.get("apps_fijadas", []):
            ruta = os.path.expandvars(app.get("ruta", ""))
            grupos[ruta.lower()] = {"nombre": app.get("nombre") or nombre_desde_ruta(ruta),
                                    "ruta": ruta, "emoji": app.get("emoji"),
                                    "fijada": True, "ventanas": []}
        for v in ventanas:
            exe = v.exe
            # Las apps de la Microsoft Store viven todas dentro de "ApplicationFrameHost":
            # a esas las mostramos una por ventana.
            if not exe or os.path.basename(exe).lower() == "applicationframehost.exe":
                clave, ruta, nombre = f"ventana:{v.hwnd}", "", v.titulo
            else:
                clave, ruta, nombre = exe.lower(), exe, nombre_desde_ruta(exe)
            if clave not in grupos:
                grupos[clave] = {"nombre": nombre, "ruta": ruta, "emoji": None,
                                 "fijada": False, "ventanas": []}
            grupos[clave]["ventanas"].append(v)

        # 2) Si cambió QUÉ botones hay, rehacerlos; si no, solo actualizar sus puntitos
        firma = tuple((clave, g["fijada"]) for clave, g in grupos.items())
        if firma != self._firma:
            self._reconstruir(grupos)
            self._firma = firma
        for clave, g in grupos.items():
            es_activa = any(v.hwnd == self.ultima_activa for v in g["ventanas"])
            self.botones[clave].actualizar_estado(g["ventanas"], es_activa)

    def _reconstruir(self, grupos):
        while self.capa_apps.count():
            item = self.capa_apps.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.botones = {}
        fijadas = [(c, g) for c, g in grupos.items() if g["fijada"]]
        abiertas = [(c, g) for c, g in grupos.items() if not g["fijada"]]
        for clave, g in fijadas:
            self._agregar_boton(clave, g)
        if fijadas and abiertas:
            self.capa_apps.addWidget(Separador())
        for clave, g in abiertas:
            self._agregar_boton(clave, g)
        QTimer.singleShot(0, self._ajustar_ancho)

    def _agregar_boton(self, clave, g):
        b = BotonApp(self, clave, g["nombre"], g["ruta"], g["emoji"], g["fijada"])
        self.capa_apps.addWidget(b)
        self.botones[clave] = b

    # -------------------------------------------------------------------------
    # Clics en las apps
    # -------------------------------------------------------------------------
    def clic_app(self, boton):
        if not boton.ventanas:                       # no está abierta -> abrirla
            if boton.ruta:
                abrir(boton.ruta)
            return
        if len(boton.ventanas) == 1:
            h = boton.ventanas[0].hwnd
            if h == self.ultima_activa and not sw.esta_minimizada(h):
                sw.minimizar(h)                     # ya estaba al frente -> minimizar
                self.ultima_activa = None
            else:
                sw.activar(h)                       # traerla al frente
                self.ultima_activa = h
            return
        # Varias ventanas del mismo programa -> menú para elegir
        menu = crear_menu(self)
        fuente = menu.font()
        for v in boton.ventanas:
            accion = menu.addAction(recortar(v.titulo, fuente, 360))
            accion.setData(v.hwnd)
        menu.addSeparator()
        nueva = menu.addAction("Abrir nueva ventana") if boton.ruta else None
        elegida = self._mostrar_menu(menu, boton)
        if elegida is None:
            return
        if elegida is nueva:
            abrir(boton.ruta)
        elif elegida.data():
            sw.activar(elegida.data())
            self.ultima_activa = elegida.data()

    def menu_app(self, boton, _posicion):
        menu = crear_menu(self)
        nueva = menu.addAction("Abrir nueva ventana") if boton.ruta else None
        cerrar = None
        if boton.ventanas:
            n = len(boton.ventanas)
            cerrar = menu.addAction("Cerrar ventana" if n == 1 else f"Cerrar las {n} ventanas")
        menu.addSeparator()
        fijar = quitar = None
        if boton.fijada:
            quitar = menu.addAction("Quitar del dock")
        elif boton.ruta:
            fijar = menu.addAction("Fijar al dock")

        elegida = self._mostrar_menu(menu, boton)
        if elegida is None:
            return
        if elegida is nueva:
            abrir(boton.ruta)
        elif elegida is cerrar:
            for v in boton.ventanas:
                sw.cerrar(v.hwnd)
        elif elegida is fijar:
            self.config["apps_fijadas"].append({"nombre": boton.nombre, "ruta": boton.ruta})
            self._guardar_y_refrescar()
        elif elegida is quitar:
            self.config["apps_fijadas"] = [
                a for a in self.config["apps_fijadas"]
                if os.path.expandvars(a.get("ruta", "")).lower() != boton.clave]
            self._guardar_y_refrescar()

    def _guardar_y_refrescar(self):
        configuracion.guardar(self.config)
        self._firma = None
        self._refrescar_apps()

    def _mostrar_menu(self, menu, widget):
        """Muestra un menú justo encima (o debajo) de un widget de la barra."""
        tamano = menu.sizeHint()
        esquina = widget.mapToGlobal(QPoint(0, 0))
        x = esquina.x()
        y = esquina.y() - tamano.height() - 8 if self.abajo else esquina.y() + widget.height() + 8
        return menu.exec(QPoint(x, y))

    # -------------------------------------------------------------------------
    # Menú de la barra (clic derecho en un espacio vacío)
    # -------------------------------------------------------------------------
    def contextMenuEvent(self, evento):
        menu = crear_menu(self)
        buscar = menu.addAction(f"Buscar…    {self.config.get('atajo_buscador', '').title()}")
        ajustes = menu.addAction("Ajustes de mibarra…")
        editar = menu.addAction("Editar widgets…")
        menu.addSeparator()
        recargar = menu.addAction("Recargar mibarra")
        salir = menu.addAction("Cerrar mibarra")

        elegida = menu.exec(evento.globalPos())
        if elegida is buscar:
            self.abrir_buscador()
        elif elegida is ajustes:
            self.abrir_ajustes()
        elif elegida is editar:
            self.abrir_ajustes("widgets")
        elif elegida is recargar:
            self.reiniciar()
        elif elegida is salir:
            QApplication.quit()

    def _comando_inicio(self):
        programa, argumentos = rutas.comando_propio()
        return " ".join(f'"{x}"' for x in [programa, *argumentos])

    def _alternar_bandeja(self):
        if self.barra_windows.pausada:
            self.barra_windows.volver_a_ocultar()
        else:
            self.barra_windows.mostrar_un_rato()

    # -------------------------------------------------------------------------
    # Salir limpio
    # -------------------------------------------------------------------------
    def limpiar(self):
        """Devuelve todo a como estaba: espacio reservado y barra de Windows."""
        if self._limpio:
            return
        self._limpio = True
        if self.atajos is not None:
            self.atajos.detener()
        if self.espacio is not None:
            self.espacio.liberar()
        self.barra_windows.restaurar()

    def reiniciar(self):
        self.limpiar()
        candado = getattr(QApplication.instance(), "candado", None)
        if candado is not None:
            candado.unlock()
        programa, argumentos = rutas.comando_propio()
        QProcess.startDetached(programa, argumentos)
        QApplication.quit()

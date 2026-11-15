"""
dock.py — la barra en sí: botón de inicio, apps y widgets.

Orden de izquierda a derecha:
  [Inicio] | [apps fijadas] | [apps abiertas no fijadas] ....... [widgets] [mostrar escritorio]

Cada 0,7 s la barra pregunta a Windows qué ventanas hay abiertas y actualiza los íconos.
Cada 1 s actualiza los widgets (hora, CPU, RAM...).
"""

import os
import sys
from pathlib import Path

from PyQt6.QtCore import (QEasingCurve, QFileInfo, QPoint, QProcess, QPropertyAnimation, QRect,
                          QRectF, QSize, Qt, QTimer, QVariantAnimation)
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QFileIconProvider, QHBoxLayout, QWidget

import config as configuracion
import mas_widgets
import estilo
import sistema_windows as sw
from widgets import (AnioTile, BandejaTile, BateriaTile, Caja, ClimaTile, CpuTile, DiscoTile,
                     EnfoqueTile, InsigniaQuitar, MusicaWidget, RamTile, RedTile, RelojTile,
                     VolumenTile, abrir, crear_menu, recortar)

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
    def __init__(self, lado):
        super().__init__()
        self.setFixedSize(lado, lado)
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

        # La fila principal. Su contenido se arma en _armar_todo() (y se puede rearmar en vivo)
        self.capa = QHBoxLayout(self)
        self.capa.setContentsMargins(10, 8, 6, 8)
        self.capa.setSpacing(6)
        self._armar_todo()

        # --- Relojes internos (timers) ---
        self._timer(1000, self._actualizar_widgets)
        self._timer(700, self._refrescar_apps)
        self._timer(400, self._vigilar)      # rápido, para esconderse apenas pongas pantalla completa

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

        self.capa.addWidget(BotonInicio(self.lado_boton))
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
        """que = "apps" | "widgets" | "todo" """
        configuracion.guardar(self.config)
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
            return EnfoqueTile(alto)
        if nombre == "bandeja":
            if not self.config.get("ocultar_barra_windows", True):
                return None   # si la barra de Windows queda visible, este botón no hace falta
            b = BandejaTile(alto)
            b.clic.connect(self._alternar_bandeja)
            return b
        print(f"[mibarra] Widget desconocido en config.json: {nombre!r}")
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

    def ubicar(self):
        pantalla = QApplication.primaryScreen()
        escala = pantalla.devicePixelRatio()      # ej. 1.25 si Windows está al 125 %
        g = pantalla.geometry()
        grosor = self.alto + 2 * self.margen

        zona = None
        if self.config.get("reservar_espacio", True) and self.espacio is not None:
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
        if self._centrada():
            self.capa.activate()                       # que la capa recalcule cuánto mide
            medida = min(self.capa.sizeHint().width(), disponible)
            izquierda = x + self.margen + (disponible - medida) / 2
        else:
            medida, izquierda = disponible, x + self.margen
        destino = QRect(int(izquierda), int(y + self.margen), int(medida), self.alto)

        animacion = getattr(self, "_animacion", None)
        if animacion is not None and animacion.state() == QPropertyAnimation.State.Running:
            if animacion.endValue() == destino:
                return
            animacion.stop()
        elif destino == self.geometry():
            return

        if animar and self.isVisible():
            self._animacion = QPropertyAnimation(self, b"geometry", self)
            self._animacion.setDuration(180)
            self._animacion.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._animacion.setStartValue(self.geometry())
            self._animacion.setEndValue(destino)
            self._animacion.start()
        else:
            self.setGeometry(destino)

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
        ajustes = menu.addAction("Ajustes de mibarra…")
        editar = menu.addAction("Editar widgets…")
        menu.addSeparator()
        recargar = menu.addAction("Recargar mibarra")
        salir = menu.addAction("Cerrar mibarra")

        elegida = menu.exec(evento.globalPos())
        if elegida is ajustes:
            self.abrir_ajustes()
        elif elegida is editar:
            self.abrir_ajustes("widgets")
        elif elegida is recargar:
            self.reiniciar()
        elif elegida is salir:
            QApplication.quit()

    def _comando_inicio(self):
        python = Path(sys.executable)
        sin_consola = python.with_name("pythonw.exe")   # pythonw = Python sin ventana negra
        if sin_consola.exists():
            python = sin_consola
        principal = Path(__file__).resolve().parent / "main.py"
        return f'"{python}" "{principal}"'

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
        if self.espacio is not None:
            self.espacio.liberar()
        self.barra_windows.restaurar()

    def reiniciar(self):
        self.limpiar()
        candado = getattr(QApplication.instance(), "candado", None)
        if candado is not None:
            candado.unlock()
        principal = str(Path(__file__).resolve().parent / "main.py")
        QProcess.startDetached(sys.executable, [principal])
        QApplication.quit()

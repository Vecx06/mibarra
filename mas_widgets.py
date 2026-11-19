"""
mas_widgets.py — los widgets de la versión 1.2.

  comando          escribe un programa, una página web, una búsqueda o una cuenta (=2+2)
  notas            una nota rápida que se guarda sola
  conexiones       Wi-Fi, Bluetooth y modo avión
  tema             cambia Windows entre modo claro y oscuro
  capturas         recortar, capturar la pantalla y abrir la carpeta de capturas
  bateria_anillo   la batería como un anillo que se va llenando
  cpu_anillo       el procesador como anillo
  moneda           conversor de moneda (por ejemplo 1 USD -> CLP)
  almacenamiento   espacio libre del disco

Cada clase recibe `demo=True` cuando se usa como vista previa en los Ajustes:
en ese modo muestra datos de ejemplo y no se conecta a nada.
"""

import ast
import asyncio
import json
import operator
import os
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

import psutil
from PyQt6.QtCore import QPoint, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QPalette, QPen
from PyQt6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
                             QVBoxLayout, QWidget)

import config as configuracion
import rutas
import estilo
import sistema_windows as sw
from widgets import Caja, Tile, TrabajoRepetido, abrir, aplicar_visibilidad, recortar

ARCHIVO_NOTAS = rutas.ARCHIVO_NOTAS

# Encender/apagar Wi-Fi y Bluetooth necesita un paquete opcional (winrt).
try:
    import winrt.windows.foundation  # noqa: F401
    from winrt.windows.devices.radios import Radio, RadioState
    HAY_RADIOS = True
except Exception:
    HAY_RADIOS = False

RADIO_WIFI, RADIO_BLUETOOTH = 1, 3      # códigos de Windows para cada tipo de radio


# =============================================================================
# Piezas base
# =============================================================================
class Grupo(Caja):
    """Una caja que solo agrupa botones (no se ilumina entera con el mouse)."""

    def __init__(self, ancho, alto):
        super().__init__(radio=12)
        self.setFixedSize(ancho, alto)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.capa = QHBoxLayout(self)
        self.capa.setContentsMargins(5, 5, 5, 5)
        self.capa.setSpacing(4)

    def pintar_fondo(self, p):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(estilo.CAJA)
        p.drawRoundedRect(QRectF(self.rect()), self.radio, self.radio)

    def actualizar(self):
        pass


class BotonIcono(Caja):
    """Botón redondo con un ícono. Si está 'activo' se pinta con el color de acento."""

    def __init__(self, lado, codigo, respaldo, ayuda=""):
        super().__init__(radio=lado / 2)
        self.codigo = codigo
        self.respaldo = respaldo
        self.activo = False
        self.setFixedSize(lado, lado)
        self.setToolTip(ayuda)

    def pintar_fondo(self, p):
        p.setPen(Qt.PenStyle.NoPen)
        if self.activo:
            p.setBrush(estilo.ACENTO)
        elif self._hover:
            p.setBrush(estilo.CAJA_HOVER)
        else:
            return
        p.drawEllipse(QRectF(self.rect()))

    def pintar(self, p):
        texto, fuente = estilo.icono(self.codigo, self.respaldo, int(self.height() * 0.45))
        p.setFont(fuente)
        p.setPen(QColor("white") if self.activo else estilo.TEXTO)
        p.drawText(QRectF(self.rect()), Qt.AlignmentFlag.AlignCenter, texto)


# =============================================================================
# Comando
# =============================================================================
_OPERACIONES = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
                ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
                ast.FloorDiv: operator.floordiv, ast.USub: operator.neg, ast.UAdd: operator.pos}


def calcular(expresion):
    """
    Calcula cosas como "2+2*3" de forma SEGURA.
    (Nunca uses eval() con texto que escribe alguien: podría ejecutar cualquier código.)
    Aquí revisamos el "árbol" de la expresión y solo aceptamos números y operaciones.
    """
    def evaluar(nodo):
        if isinstance(nodo, ast.Expression):
            return evaluar(nodo.body)
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, (int, float)):
            return nodo.value
        if isinstance(nodo, ast.BinOp) and type(nodo.op) in _OPERACIONES:
            return _OPERACIONES[type(nodo.op)](evaluar(nodo.left), evaluar(nodo.right))
        if isinstance(nodo, ast.UnaryOp) and type(nodo.op) in _OPERACIONES:
            return _OPERACIONES[type(nodo.op)](evaluar(nodo.operand))
        raise ValueError("No es una cuenta válida")

    texto = expresion.replace(",", ".").replace("^", "**").replace("x", "*")
    resultado = evaluar(ast.parse(texto, mode="eval"))
    if isinstance(resultado, float) and resultado.is_integer():
        resultado = int(resultado)
    return resultado


class ComandoWidget(Caja):
    PISTA = "›  programa, web, ?búsqueda o =2+2"

    def __init__(self, alto, demo=False):
        super().__init__(radio=12)
        self.setFixedSize(220, alto)
        self.setCursor(Qt.CursorShape.IBeamCursor)
        self.campo = QLineEdit()
        self.campo.setPlaceholderText(self.PISTA)
        self.campo.setFrame(False)
        self.campo.returnPressed.connect(self._ejecutar)
        self.setToolTip("Escribe y aprieta Enter:\n"
                        "  notepad, calc, cmd…  → abre el programa\n"
                        "  youtube.com          → abre la página\n"
                        "  ?gatos               → busca en Google\n"
                        "  =15*3                → calcula")
        capa = QHBoxLayout(self)
        capa.setContentsMargins(12, 6, 8, 6)
        capa.addWidget(self.campo)
        self._tema = None
        self._estilo_campo()

    def _estilo_campo(self):
        if self._tema == estilo.ES_CLARO:
            return
        self._tema = estilo.ES_CLARO
        texto = estilo.TEXTO.name()
        suave = estilo.TEXTO_SUAVE.name()
        self.campo.setStyleSheet(
            f"QLineEdit {{ background: transparent; border: none; color: {texto}; font-size: 13px; }}")
        paleta = self.campo.palette()
        paleta.setColor(QPalette.ColorRole.PlaceholderText, QColor(suave))
        self.campo.setPalette(paleta)

    def mousePressEvent(self, evento):
        self.campo.setFocus()

    def pintar_fondo(self, p):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(estilo.CAJA_HOVER if (self._hover or self.campo.hasFocus()) else estilo.CAJA)
        p.drawRoundedRect(QRectF(self.rect()), self.radio, self.radio)

    def _ejecutar(self):
        texto = self.campo.text().strip()
        self.campo.clear()
        if not texto:
            return
        if texto.startswith("="):
            try:
                self._mostrar_un_rato(f"= {calcular(texto[1:])}")
            except Exception:
                self._mostrar_un_rato("No entendí la cuenta")
            return
        if texto.startswith("?"):
            webbrowser.open("https://www.google.com/search?q=" + urllib.parse.quote(texto[1:].strip()))
            return
        parece_web = texto.startswith(("http://", "https://")) or (
            "." in texto and " " not in texto and not texto.lower().endswith(".exe")
            and not os.path.exists(texto))
        if parece_web:
            webbrowser.open(texto if texto.startswith("http") else "https://" + texto)
            return
        try:
            os.startfile(texto)          # como el "Ejecutar" de Windows: notepad, calc, cmd, C:\...
        except Exception:
            webbrowser.open("https://www.google.com/search?q=" + urllib.parse.quote(texto))

    def _mostrar_un_rato(self, mensaje):
        self.campo.setPlaceholderText(mensaje)
        QTimer.singleShot(5000, lambda: self.campo.setPlaceholderText(self.PISTA))

    def actualizar(self):
        self._estilo_campo()


# =============================================================================
# Notas
# =============================================================================
class NotasPopup(QWidget):
    """La ventanita para escribir la nota (se guarda sola mientras escribes)."""

    def __init__(self, al_cerrar):
        super().__init__(None, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.NoDropShadowWindowHint)
        self.al_cerrar = al_cerrar
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(360, 320)
        self.setStyleSheet("""
            #hoja { background: #fffdf6; border: 1px solid rgba(0,0,0,30); border-radius: 14px; }
            #franja { background: #ffd60a; border-top-left-radius: 14px; border-top-right-radius: 14px; }
            QLabel { color: #1d1d1f; font-size: 15px; font-weight: 700; }
            QLabel#ayuda { color: #8a8a8e; font-size: 11px; font-weight: 400; }
            QPlainTextEdit { background: transparent; border: none; color: #1d1d1f; font-size: 13px; }
        """)
        hoja = QFrame(self)
        hoja.setObjectName("hoja")
        exterior = QVBoxLayout(self)
        exterior.setContentsMargins(0, 0, 0, 0)
        exterior.addWidget(hoja)
        capa = QVBoxLayout(hoja)
        capa.setContentsMargins(0, 0, 0, 10)
        franja = QFrame()
        franja.setObjectName("franja")
        franja.setFixedHeight(8)
        capa.addWidget(franja)
        cabecera = QHBoxLayout()
        cabecera.setContentsMargins(16, 8, 16, 0)
        cabecera.addWidget(QLabel("Notas"))
        cabecera.addStretch()
        ayuda = QLabel("Se guarda sola")
        ayuda.setObjectName("ayuda")
        cabecera.addWidget(ayuda)
        capa.addLayout(cabecera)
        self.texto = QPlainTextEdit()
        self.texto.setPlaceholderText("Escribe aquí… (la primera línea es el título)")
        capa.addWidget(self.texto)
        self.texto.setViewportMargins(12, 0, 10, 0)
        self._guardado = QTimer(self)
        self._guardado.setSingleShot(True)
        self._guardado.timeout.connect(self.guardar)
        self.texto.textChanged.connect(lambda: self._guardado.start(500))

    def mostrar_cerca_de(self, widget, hacia_arriba):
        try:
            self.texto.setPlainText(ARCHIVO_NOTAS.read_text(encoding="utf-8"))
        except OSError:
            self.texto.setPlainText("")
        esquina = widget.mapToGlobal(QPoint(0, 0))
        x = esquina.x() + widget.width() // 2 - self.width() // 2
        y = esquina.y() - self.height() - 12 if hacia_arriba else esquina.y() + widget.height() + 12
        pantalla = widget.screen().geometry()
        x = max(pantalla.left() + 8, min(x, pantalla.right() - self.width() - 8))
        self.move(x, y)
        self.show()
        self.texto.setFocus()

    def guardar(self):
        try:
            ARCHIVO_NOTAS.write_text(self.texto.toPlainText(), encoding="utf-8")
        except OSError:
            pass

    def hideEvent(self, evento):
        self.guardar()
        self.al_cerrar()
        super().hideEvent(evento)


class NotasWidget(Caja):
    def __init__(self, alto, hacia_arriba=True, demo=False):
        super().__init__(radio=12)
        self.setFixedSize(196, alto)
        self.hacia_arriba = hacia_arriba
        self.demo = demo
        self.titulo, self.detalle = "Notas", "Escribe algo…"
        self.popup = None
        self._cerrado_en = 0.0
        self.setToolTip("Clic: abrir tus notas")
        self.clic.connect(self._abrir)
        if demo:
            self.titulo, self.detalle = "Prueba de cálculo", "Repasar integrales y ejercicios…"
        else:
            self._leer()

    def _leer(self):
        try:
            lineas = [x.strip() for x in ARCHIVO_NOTAS.read_text(encoding="utf-8").splitlines() if x.strip()]
        except OSError:
            lineas = []
        self.titulo = lineas[0] if lineas else "Notas"
        self.detalle = lineas[1] if len(lineas) > 1 else ("Escribe algo…" if not lineas else " ")
        self.update()

    def _abrir(self):
        if time.monotonic() - self._cerrado_en < 0.3:
            return
        if self.popup is None:
            self.popup = NotasPopup(self._al_cerrar)
        self.popup.mostrar_cerca_de(self, self.hacia_arriba)

    def _al_cerrar(self):
        self._cerrado_en = time.monotonic()
        self._leer()

    def pintar(self, p):
        h = self.height()
        # Ícono de libreta: cuadrado blanco con franja amarilla y rayitas
        lado = h - 14
        zona = QRectF(8, 7, lado, lado)
        p.setPen(QPen(QColor(0, 0, 0, 30), 1) if estilo.ES_CLARO else Qt.PenStyle.NoPen)
        p.setBrush(QColor("#ffffff"))
        p.drawRoundedRect(zona, 6, 6)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#ffd60a"))
        p.drawRoundedRect(QRectF(zona.x(), zona.y(), lado, lado * 0.3), 6, 6)
        p.drawRect(QRectF(zona.x(), zona.y() + lado * 0.15, lado, lado * 0.15))
        p.setBrush(QColor(0, 0, 0, 40))
        for i in range(3):
            p.drawRect(QRectF(zona.x() + 5, zona.y() + lado * (0.45 + i * 0.17), lado - 10, 1.2))

        x = zona.right() + 9
        ancho = self.width() - x - 26
        f1, f2 = estilo.fuente(12, negrita=True), estilo.fuente(10)
        p.setFont(f1)
        p.setPen(estilo.TEXTO)
        p.drawText(QRectF(x, h / 2 - 15, ancho, 16), Qt.AlignmentFlag.AlignVCenter, recortar(self.titulo, f1, ancho))
        p.setFont(f2)
        p.setPen(estilo.TEXTO_SUAVE)
        p.drawText(QRectF(x, h / 2 + 1, ancho, 14), Qt.AlignmentFlag.AlignVCenter, recortar(self.detalle, f2, ancho))
        texto, fuente = estilo.icono(0xE70F, "✎", 14)    # lápiz
        p.setFont(fuente)
        p.setPen(estilo.TEXTO)
        p.drawText(QRectF(self.width() - 26, 0, 20, h), Qt.AlignmentFlag.AlignCenter, texto)

    def actualizar(self):
        pass


# =============================================================================
# Conexiones: Wi-Fi, Bluetooth, modo avión
# =============================================================================
async def _leer_radios():
    await Radio.request_access_async()
    estado = {}
    for radio in await Radio.get_radios_async():
        estado[int(radio.kind)] = int(radio.state) == 1      # 1 = encendido
    return estado


async def _cambiar_radio(tipo, encender):
    await Radio.request_access_async()
    for radio in await Radio.get_radios_async():
        if int(radio.kind) == tipo:
            await radio.set_state_async(RadioState(1 if encender else 2))


def _leer_conexiones():
    radios = asyncio.run(_leer_radios()) if HAY_RADIOS else None
    return {"ssid": sw.red_wifi(), "radios": radios}


class PildoraWifi(Caja):
    """[ ícono Wi-Fi  NombreRed | › ]   clic izquierda: encender/apagar · clic en › : ajustes"""

    def __init__(self, alto):
        super().__init__(radio=alto / 2)
        self.setFixedSize(118, alto)
        self.encendido = False
        self.ssid = ""
        self.al_alternar = None

    def mouseReleaseEvent(self, evento):
        if evento.button() != Qt.MouseButton.LeftButton:
            return
        if evento.position().x() > self.width() - 26:
            abrir("ms-settings:network-wifi")
        elif self.al_alternar:
            self.al_alternar()

    def pintar_fondo(self, p):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(estilo.ACENTO if self.encendido else (estilo.CAJA_HOVER if self._hover else estilo.CAJA))
        p.drawRoundedRect(QRectF(self.rect()), self.radio, self.radio)

    def pintar(self, p):
        color = QColor("white") if self.encendido else estilo.TEXTO
        h = self.height()
        texto, fuente = estilo.icono(0xE701, "📶", int(h * 0.42))
        p.setFont(fuente)
        p.setPen(color)
        p.drawText(QRectF(8, 0, 22, h), Qt.AlignmentFlag.AlignCenter, texto)
        f = estilo.fuente(11, negrita=True)
        p.setFont(f)
        nombre = self.ssid or ("Wi-Fi" if self.encendido else "Apagado")
        p.drawText(QRectF(32, 0, self.width() - 62, h), Qt.AlignmentFlag.AlignVCenter,
                   recortar(nombre, f, self.width() - 62))
        p.setPen(QPen(QColor(255, 255, 255, 90) if self.encendido else estilo.BORDE, 1))
        p.drawLine(int(self.width() - 26), int(h * 0.25), int(self.width() - 26), int(h * 0.75))
        texto, fuente = estilo.icono(0xE76C, "›", int(h * 0.32))
        p.setFont(fuente)
        p.setPen(color)
        p.drawText(QRectF(self.width() - 26, 0, 22, h), Qt.AlignmentFlag.AlignCenter, texto)


class ConexionesWidget(Grupo):
    def __init__(self, alto, demo=False):
        lado = alto - 10
        super().__init__(118 + 2 * lado + 18, alto)
        self.wifi = PildoraWifi(lado)
        self.bt = BotonIcono(lado, 0xE702, "ᛒ", "Bluetooth")
        self.avion = BotonIcono(lado, 0xE709, "✈", "Modo avión (abre los ajustes)")
        for w in (self.wifi, self.bt, self.avion):
            self.capa.addWidget(w)
        self.wifi.al_alternar = lambda: self._alternar(RADIO_WIFI, self.wifi.encendido, "ms-settings:network-wifi")
        self.bt.clic.connect(lambda: self._alternar(RADIO_BLUETOOTH, self.bt.activo, "ms-settings:bluetooth"))
        self.avion.clic.connect(lambda: abrir("ms-settings:network-airplanemode"))
        self.wifi.setToolTip("Clic: encender / apagar Wi-Fi\nClic en ›: ajustes de Wi-Fi"
                             if HAY_RADIOS else "Clic: ajustes de Wi-Fi")
        self.bt.setToolTip("Clic: encender / apagar Bluetooth" if HAY_RADIOS else "Clic: ajustes de Bluetooth")
        if demo:
            self._mostrar({"ssid": "Casa", "radios": {RADIO_WIFI: True, RADIO_BLUETOOTH: False}})
        else:
            self.trabajo = TrabajoRepetido(_leer_conexiones, cada=8, cada_si_falla=15)
            self.trabajo.resultado.connect(self._mostrar)
            self.trabajo.empezar()

    def _mostrar(self, datos):
        if not datos:
            return
        radios = datos.get("radios")
        self.wifi.ssid = datos.get("ssid", "")
        self.wifi.encendido = radios.get(RADIO_WIFI, False) if radios else bool(self.wifi.ssid)
        self.bt.activo = bool(radios and radios.get(RADIO_BLUETOOTH, False))
        self.wifi.update()
        self.bt.update()

    def _alternar(self, tipo, esta_encendido, ajustes):
        if not HAY_RADIOS:
            abrir(ajustes)
            return
        # Lo hacemos en otro hilo: Windows tarda un poquito en encender/apagar la radio
        threading.Thread(target=lambda: asyncio.run(_cambiar_radio(tipo, not esta_encendido)),
                         daemon=True).start()
        if tipo == RADIO_WIFI:
            self.wifi.encendido = not esta_encendido
            self.wifi.update()
        else:
            self.bt.activo = not esta_encendido
            self.bt.update()

    def detener(self):
        if hasattr(self, "trabajo"):
            self.trabajo.detener()


# =============================================================================
# Tema claro / oscuro de Windows
# =============================================================================
class TemaWidget(Grupo):
    def __init__(self, alto, demo=False):
        lado = alto - 10
        super().__init__(2 * lado + 14, alto)
        self.sol = BotonIcono(lado, 0xE706, "☀", "Modo claro")
        self.luna = BotonIcono(lado, 0xE708, "☾", "Modo oscuro")
        self.capa.addWidget(self.sol)
        self.capa.addWidget(self.luna)
        self.sol.clic.connect(lambda: self._poner(True))
        self.luna.clic.connect(lambda: self._poner(False))
        self.demo = demo
        self._marcar(False if demo else sw.windows_usa_tema_claro())

    def _marcar(self, claro):
        self.sol.activo, self.luna.activo = claro, not claro
        self.sol.update()
        self.luna.update()

    def _poner(self, claro):
        self._marcar(claro)
        threading.Thread(target=sw.poner_tema_windows, args=(claro,), daemon=True).start()

    def actualizar(self):
        if not self.demo and sw.ES_WINDOWS:
            claro = sw.windows_usa_tema_claro()
            if claro != self.sol.activo:
                self._marcar(claro)


# =============================================================================
# Capturas de pantalla
# =============================================================================
def _carpeta_capturas():
    imagenes = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Pictures"
    for opcion in (imagenes / "Screenshots", imagenes / "Capturas de pantalla", imagenes):
        if opcion.exists():
            return str(opcion)
    return str(Path.home())


class CapturasWidget(Grupo):
    def __init__(self, alto, demo=False):
        lado = alto - 10
        super().__init__(3 * lado + 18, alto)
        recortar_b = BotonIcono(lado, 0xE7A8, "✂", "Recortar un pedazo de la pantalla (Win+Shift+S)")
        completa = BotonIcono(lado, 0xE722, "📷", "Capturar toda la pantalla\n(se guarda en Imágenes › Capturas)")
        carpeta = BotonIcono(lado, 0xE8B7, "📁", "Abrir la carpeta de capturas")
        for b in (recortar_b, completa, carpeta):
            self.capa.addWidget(b)
        recortar_b.clic.connect(lambda: sw.presionar_teclas(sw.VK_LWIN, sw.VK_SHIFT, sw.VK_S))
        completa.clic.connect(lambda: sw.presionar_teclas(sw.VK_LWIN, sw.VK_SNAPSHOT))
        carpeta.clic.connect(lambda: abrir(_carpeta_capturas()))


# =============================================================================
# Anillos (batería y CPU)
# =============================================================================
class AnilloWidget(Caja):
    def __init__(self, alto, tipo, demo=False):
        super().__init__(radio=12)
        self.tipo = tipo
        self.demo = demo
        self.valor = 48 if demo else 0
        self.cargando = demo
        self.setFixedSize(alto, alto)
        if tipo == "cpu":
            psutil.cpu_percent(interval=None)
            self.clic.connect(lambda: abrir("taskmgr.exe"))

    def actualizar(self):
        if self.demo:
            return
        if self.tipo == "bateria":
            b = psutil.sensors_battery()
            self.oculto_propio = b is None
            aplicar_visibilidad(self)
            if b is None:
                return
            self.valor, self.cargando = b.percent, bool(b.power_plugged)
            self.setToolTip(f"Batería {b.percent:.0f}%" + (" · cargando" if self.cargando else ""))
        else:
            self.valor = psutil.cpu_percent(interval=None)
            self.setToolTip(f"Procesador {self.valor:.0f}%\nClic: Administrador de tareas")
        self.update()

    def _color(self):
        if self.tipo == "bateria":
            if self.cargando or self.valor > 50:
                return QColor("#30d158")
            return QColor("#ff9f0a") if self.valor > 20 else QColor("#ff453a")
        return estilo.ROJO if self.valor >= 85 else estilo.ACENTO

    def pintar(self, p):
        margen = 6
        zona = QRectF(margen, margen, self.width() - 2 * margen, self.height() - 2 * margen)
        lapiz = QPen(estilo.PISTA, 3.5)
        lapiz.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(lapiz)
        p.drawArc(zona, 0, 360 * 16)
        lapiz.setColor(self._color())
        p.setPen(lapiz)
        # Qt mide los ángulos en 1/16 de grado; 90° = arriba; negativo = sentido del reloj
        p.drawArc(zona, 90 * 16, int(-360 * 16 * max(0.0, min(100.0, self.valor)) / 100))

        p.setPen(estilo.TEXTO)
        numero = f"{self.valor:.0f}"
        if self.tipo == "bateria" and self.cargando:
            texto, fuente = estilo.icono(0xE945, "⚡", 9)
            p.setFont(fuente)
            p.drawText(QRectF(0, self.height() * 0.24, self.width(), 11), Qt.AlignmentFlag.AlignCenter, texto)
            p.setFont(estilo.fuente(11, negrita=True))
            p.drawText(QRectF(0, self.height() * 0.44, self.width(), 14), Qt.AlignmentFlag.AlignCenter, numero)
        else:
            p.setFont(estilo.fuente(11, negrita=True))
            p.drawText(QRectF(self.rect()), Qt.AlignmentFlag.AlignCenter, numero)


# =============================================================================
# Conversor de moneda (tasas gratis de open.er-api.com)
# =============================================================================
def _formato(numero):
    """37558.734 -> '37.558,73' (como se escribe en Chile)"""
    return f"{numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class MonedaTile(Tile):
    def __init__(self, alto, config, demo=False):
        self.config = config
        super().__init__(150, alto, "", "…")
        self.tasa = None
        self.demo = demo
        self.setToolTip("Clic: invertir las monedas\nSe cambian en Ajustes › Moneda")
        self.clic.connect(self._invertir)
        self._mostrar_titulo()
        if demo:
            self.tasa = 945.3
            self._pintar_valor()
        else:
            self._empezar()

    def _datos(self):
        m = self.config.setdefault("moneda", {"cantidad": 1, "desde": "USD", "hacia": "CLP"})
        return float(m.get("cantidad", 1)), m.get("desde", "USD").upper(), m.get("hacia", "CLP").upper()

    def _mostrar_titulo(self):
        cantidad, desde, hacia = self._datos()
        cant = f"{cantidad:g}"
        self.poner(titulo=f"{cant} {desde} → {hacia}")

    def _empezar(self):
        _, desde, hacia = self._datos()

        def consultar():
            with urllib.request.urlopen(f"https://open.er-api.com/v6/latest/{desde}", timeout=10) as r:
                datos = json.load(r)
            return datos["rates"][hacia]

        self.trabajo = TrabajoRepetido(consultar, cada=3600, cada_si_falla=300)
        self.trabajo.resultado.connect(self._recibir)
        self.trabajo.empezar()

    def _recibir(self, tasa):
        if tasa is None:
            if self.tasa is None:
                self.poner(valor="sin red")
            return
        self.tasa = tasa
        self._pintar_valor()

    def _pintar_valor(self):
        cantidad, desde, hacia = self._datos()
        self.poner(valor=_formato(cantidad * self.tasa))

    def _invertir(self):
        m = self.config["moneda"]
        m["desde"], m["hacia"] = m.get("hacia", "CLP"), m.get("desde", "USD")
        if not self.demo:
            configuracion.guardar(self.config)
            self.detener()
            self._empezar()
        if self.tasa:
            self.tasa = 1 / self.tasa
            self._pintar_valor()
        self._mostrar_titulo()

    def detener(self):
        if hasattr(self, "trabajo"):
            self.trabajo.detener()

    def actualizar(self):
        pass


# =============================================================================
# Almacenamiento
# =============================================================================
class AlmacenamientoTile(Tile):
    def __init__(self, alto, demo=False):
        super().__init__(150, alto, "Almacenamiento", "—")
        self.unidad = "C:\\" if sw.ES_WINDOWS else "/"
        self.demo = demo
        self._contador = 0
        self.clic.connect(lambda: abrir(self.unidad))
        if demo:
            self.poner(titulo="Almacenamiento · 88%", valor="33 GB libres", progreso=88)

    def actualizar(self):
        if self.demo:
            return
        if self._contador % 30 == 0:
            uso = psutil.disk_usage(self.unidad)
            gb = 1024 ** 3
            self.poner(titulo=f"Almacenamiento · {uso.percent:.0f}%", valor=f"{uso.free / gb:.0f} GB libres",
                       progreso=uso.percent, alerta=uso.percent >= 90)
            self.setToolTip(f"{uso.free / gb:.0f} GB libres de {uso.total / gb:.0f} GB\nClic: abrir el disco")
        self._contador += 1


# =============================================================================
# Fábrica: nombre del widget -> cómo crearlo
# =============================================================================
CREADORES = {
    "comando": lambda alto, cfg, demo=False, arriba=True: ComandoWidget(alto, demo),
    "notas": lambda alto, cfg, demo=False, arriba=True: NotasWidget(alto, arriba, demo),
    "conexiones": lambda alto, cfg, demo=False, arriba=True: ConexionesWidget(alto, demo),
    "tema": lambda alto, cfg, demo=False, arriba=True: TemaWidget(alto, demo),
    "capturas": lambda alto, cfg, demo=False, arriba=True: CapturasWidget(alto, demo),
    "bateria_anillo": lambda alto, cfg, demo=False, arriba=True: AnilloWidget(alto, "bateria", demo),
    "cpu_anillo": lambda alto, cfg, demo=False, arriba=True: AnilloWidget(alto, "cpu", demo),
    "moneda": lambda alto, cfg, demo=False, arriba=True: MonedaTile(alto, cfg, demo),
    "almacenamiento": lambda alto, cfg, demo=False, arriba=True: AlmacenamientoTile(alto, demo),
}

# Los widgets de IA viven en su propio archivo
from widgets_ia import CREADORES_IA  # noqa: E402

CREADORES.update(CREADORES_IA)

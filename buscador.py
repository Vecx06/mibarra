"""
buscador.py — el buscador rápido (como Spotlight en Mac).

Se abre con Alt + Espacio (o el atajo que elijas) o con el botón de inicio.
Escribes y aparece:
  - tus programas (los mismos del menú Inicio de Windows)
  - carpetas y ajustes útiles (Descargas, Wi-Fi, Bluetooth...)
  - una cuenta, si escribes algo como 15*3  (Enter la copia)
  - una página, si escribes algo como youtube.com
  - y siempre: "Buscar en Google"
Flechas para moverte, Enter para abrir, Esc para cerrar.
"""

import os
import re
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path

from PyQt6.QtCore import QFileInfo, QObject, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (QApplication, QFileIconProvider, QFrame, QGraphicsDropShadowEffect, QHBoxLayout,
                             QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout, QWidget)

import config as configuracion
import estilo
import sistema_windows as sw
from ajustes import icono_lateral
from widgets import abrir

PALABRAS_IGNORADAS = ("uninstall", "desinstalar", "readme", "léame", "leame", "help", "ayuda", "license",
                      "licencia", "website", "sitio web", "release notes")

LUGARES = [
    ("Descargas", "Carpeta", lambda: str(Path.home() / "Downloads")),
    ("Documentos", "Carpeta", lambda: str(Path.home() / "Documents")),
    ("Escritorio", "Carpeta", lambda: str(Path.home() / "Desktop")),
    ("Imágenes", "Carpeta", lambda: str(Path.home() / "Pictures")),
    ("Papelera de reciclaje", "Carpeta", lambda: "shell:RecycleBinFolder"),
    ("Configuración de Windows", "Ajustes", lambda: "ms-settings:"),
    ("Wi-Fi", "Ajustes", lambda: "ms-settings:network-wifi"),
    ("Bluetooth", "Ajustes", lambda: "ms-settings:bluetooth"),
    ("Pantalla", "Ajustes", lambda: "ms-settings:display"),
    ("Sonido", "Ajustes", lambda: "ms-settings:sound"),
    ("Windows Update", "Ajustes", lambda: "ms-settings:windowsupdate"),
    ("Aplicaciones instaladas", "Ajustes", lambda: "ms-settings:appsfeatures"),
    ("Fondo de pantalla", "Ajustes", lambda: "ms-settings:personalization-background"),
    ("Administrador de tareas", "Sistema", lambda: "taskmgr.exe"),
    ("Panel de control", "Sistema", lambda: "control.exe"),
]


# =============================================================================
# Lógica (sin ventanas): qué hay para buscar y qué tan bien calza
# =============================================================================
def carpetas_menu_inicio():
    carpetas = []
    for variable in ("ProgramData", "APPDATA"):
        base = os.environ.get(variable)
        if base:
            carpetas.append(Path(base) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    return carpetas


def indexar_programas(carpetas=None):
    """Devuelve [{"nombre", "detalle", "ruta"}] con los accesos directos del menú Inicio (sin repetidos)."""
    vistos, programas = set(), []
    for carpeta in carpetas if carpetas is not None else carpetas_menu_inicio():
        if not Path(carpeta).exists():
            continue
        for ruta in Path(carpeta).rglob("*"):
            if ruta.suffix.lower() not in (".lnk", ".url", ".appref-ms"):
                continue
            nombre = ruta.stem
            minusculas = nombre.lower()
            if any(p in minusculas for p in PALABRAS_IGNORADAS) or minusculas in vistos:
                continue
            vistos.add(minusculas)
            programas.append({"nombre": nombre, "detalle": "Programa", "ruta": str(ruta)})
    return programas


def _sin_tildes(texto):
    return texto.lower().translate(str.maketrans("áéíóúüñ", "aeiouun"))


def puntaje(nombre, consulta):
    """
    Qué tan bien calza un nombre con lo que escribiste (0 = nada).
      "Chrome" con "chr"            -> empieza igual: 80
      "Google Chrome" con "chr"     -> una palabra empieza igual: 60
      "Visual Studio Code" con "vsc"-> iniciales: 50
      "Microsoft Edge" con "edg"    -> palabra que empieza igual: 60
      "Notepad++" con "pad"         -> contiene: 30
    """
    n, c = _sin_tildes(nombre), _sin_tildes(consulta.strip())
    if not c:
        return 0
    if n == c:
        return 100
    if n.startswith(c):
        return 80
    palabras = re.split(r"[\s\-_.()]+", n)
    if any(p.startswith(c) for p in palabras if p):
        return 60
    iniciales = "".join(p[0] for p in palabras if p)
    if len(c) >= 2 and iniciales.startswith(c):
        return 50
    if c in n:
        return 30
    return 0


def parece_cuenta(texto):
    t = texto.strip().lstrip("=")
    return bool(re.fullmatch(r"[\d\s.,+\-*/^x()%]+", t)) and any(ch.isdigit() for ch in t) \
        and any(op in t for op in "+-*/^x%")


def parece_web(texto):
    t = texto.strip()
    return t.startswith(("http://", "https://")) or bool(re.fullmatch(r"[\w-]+(\.[\w-]+)+(/\S*)?", t))


def buscar(consulta, programas, uso=None, limite=8):
    """Arma la lista de resultados para una consulta. Cada resultado: dict con nombre, detalle, accion, valor."""
    from mas_widgets import calcular
    uso = uso or {}
    consulta = consulta.strip()
    if not consulta:
        return []
    resultados = []
    if parece_cuenta(consulta):
        try:
            valor = calcular(consulta.lstrip("="))
            resultados.append({"nombre": f"= {valor}", "detalle": "Enter: copiar el resultado",
                               "accion": "copiar", "valor": str(valor), "puntos": 1000})
        except Exception:
            pass
    if parece_web(consulta):
        url = consulta if consulta.startswith("http") else "https://" + consulta
        resultados.append({"nombre": consulta, "detalle": "Abrir la página", "accion": "web", "valor": url,
                           "puntos": 900})
    candidatos = [dict(p, accion="abrir", valor=p["ruta"]) for p in programas]
    candidatos += [{"nombre": n, "detalle": d, "accion": "abrir", "valor": f()} for n, d, f in LUGARES]
    for c in candidatos:
        puntos = puntaje(c["nombre"], consulta)
        if puntos:
            c["puntos"] = puntos + min(uso.get(c["nombre"], 0), 10) * 3   # lo que más usas sube
            resultados.append(c)
    resultados.sort(key=lambda r: (-r["puntos"], r["nombre"].lower()))
    resultados = resultados[:limite]
    resultados.append({"nombre": f"Buscar «{consulta}» en Google", "detalle": "Web", "accion": "web",
                       "valor": "https://www.google.com/search?q=" + urllib.parse.quote(consulta), "puntos": 0})
    return resultados


# =============================================================================
# La ventana
# =============================================================================
class Indexador(QObject):
    listo = pyqtSignal(object)

    def empezar(self):
        threading.Thread(target=lambda: self._emitir(indexar_programas()), daemon=True).start()

    def _emitir(self, datos):
        try:
            self.listo.emit(datos)
        except RuntimeError:
            pass


def _icono_generico(color, letra):
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    p.drawRoundedRect(0, 0, 64, 64, 14, 14)
    p.setPen(QColor("white"))
    p.setFont(estilo.fuente(34, negrita=True))
    p.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, letra)
    p.end()
    return QIcon(pixmap)


class Buscador(QWidget):
    def __init__(self, dock):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.dock = dock
        self.programas = []
        self._indexado_en = 0.0
        self._iconos = {}
        self._proveedor = QFileIconProvider()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(640 + 48)

        exterior = QVBoxLayout(self)
        exterior.setContentsMargins(24, 24, 24, 24)
        self.caja = QFrame()
        self.caja.setObjectName("caja")
        sombra = QGraphicsDropShadowEffect(self)
        sombra.setBlurRadius(50)
        sombra.setOffset(0, 14)
        sombra.setColor(QColor(0, 0, 0, 90))
        self.caja.setGraphicsEffect(sombra)
        exterior.addWidget(self.caja)

        capa = QVBoxLayout(self.caja)
        capa.setContentsMargins(14, 10, 14, 10)
        capa.setSpacing(6)
        fila = QHBoxLayout()
        self.lupa = QLabel()
        fila.addWidget(self.lupa)
        self.campo = QLineEdit()
        self.campo.setObjectName("campo")
        self.campo.setPlaceholderText("Buscar programas, carpetas, ajustes, cuentas o webs…")
        self.campo.textChanged.connect(self._actualizar)
        self.campo.installEventFilter(self)
        fila.addWidget(self.campo, 1)
        capa.addLayout(fila)
        self.lista = QListWidget()
        self.lista.setIconSize(QSize(28, 28))
        self.lista.itemActivated.connect(lambda _: self._ejecutar())
        self.lista.itemClicked.connect(lambda _: self._ejecutar())
        self.lista.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        capa.addWidget(self.lista)
        self.pie = QLabel("↑ ↓ para moverte · Enter para abrir · Esc para cerrar")
        self.pie.setObjectName("pie")
        capa.addWidget(self.pie)

        self.indexador = Indexador()
        self.indexador.listo.connect(self._programas_listos)

    # ---------------- apariencia (sigue el tema de la barra) ----------------
    def _aplicar_estilo(self):
        claro = estilo.ES_CLARO
        fondo = "rgba(248, 248, 250, 250)" if claro else "rgba(30, 30, 36, 250)"
        texto = "#1d1d1f" if claro else "#f2f2f5"
        suave = "#6e6e73" if claro else "#9a9aa8"
        borde = "rgba(0, 0, 0, 30)" if claro else "rgba(255, 255, 255, 30)"
        acento = estilo.ACENTO.name()
        self.setStyleSheet(f"""
            #caja {{ background: {fondo}; border: 1px solid {borde}; border-radius: 18px; }}
            QLineEdit#campo {{ background: transparent; border: none; color: {texto}; font-size: 22px;
                               padding: 8px 4px; }}
            QListWidget {{ background: transparent; border: none; outline: 0; color: {texto}; font-size: 14px; }}
            QListWidget::item {{ padding: 6px 8px; border-radius: 9px; }}
            QListWidget::item:selected {{ background: {acento}; color: white; }}
            QLabel#pie {{ color: {suave}; font-size: 11px; padding: 2px 4px; }}
        """)
        texto_lupa, fuente = estilo.icono(0xE721, "🔍", 20)
        self.lupa.setFont(fuente)
        self.lupa.setText(texto_lupa)
        self.lupa.setStyleSheet(f"color: {suave}; padding-left: 4px;")
        paleta = self.campo.palette()
        paleta.setColor(paleta.ColorRole.PlaceholderText, QColor(suave))
        self.campo.setPalette(paleta)

    # ---------------- abrir / cerrar ----------------
    def alternar(self):
        if self.isVisible():
            self.hide()
        else:
            self.mostrar()

    def mostrar(self):
        if time.monotonic() - self._indexado_en > 600:     # re-leer el menú Inicio cada 10 minutos
            self._indexado_en = time.monotonic()
            self.indexador.empezar()
        self._aplicar_estilo()
        self.campo.clear()
        self._actualizar("")
        pantalla = QApplication.primaryScreen().availableGeometry()
        self.move(pantalla.center().x() - self.width() // 2, pantalla.top() + int(pantalla.height() * 0.18))
        self.show()
        self.raise_()
        self.activateWindow()
        sw.activar(int(self.winId()))
        self.campo.setFocus()

    def _programas_listos(self, programas):
        self.programas = programas
        if self.isVisible():
            self._actualizar(self.campo.text())

    def changeEvent(self, evento):
        # Si haces clic en otra parte, el buscador se cierra (como Spotlight)
        if evento.type() == evento.Type.ActivationChange and not self.isActiveWindow() and self.isVisible():
            self.hide()
        super().changeEvent(evento)

    # ---------------- teclado ----------------
    def eventFilter(self, objeto, evento):
        if objeto is self.campo and evento.type() == evento.Type.KeyPress:
            tecla = evento.key()
            fila = self.lista.currentRow()
            if tecla == Qt.Key.Key_Down:
                self.lista.setCurrentRow(min(fila + 1, self.lista.count() - 1))
                return True
            if tecla == Qt.Key.Key_Up:
                self.lista.setCurrentRow(max(fila - 1, 0))
                return True
            if tecla in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._ejecutar()
                return True
            if tecla == Qt.Key.Key_Escape:
                self.hide()
                return True
        return super().eventFilter(objeto, evento)

    # ---------------- resultados ----------------
    def _icono(self, r):
        clave = r["valor"]
        if clave not in self._iconos:
            if r["accion"] == "abrir" and os.path.exists(r["valor"]):
                self._iconos[clave] = self._proveedor.icon(QFileInfo(r["valor"]))
            elif r["accion"] == "copiar":
                self._iconos[clave] = icono_lateral("#ff9f0a", 0xE8EF, "=")        # calculadora
            elif r["accion"] == "web":
                self._iconos[clave] = icono_lateral("#0a84ff", 0xE774, "↗")       # globo
            elif str(r["valor"]).startswith("ms-settings:"):
                self._iconos[clave] = icono_lateral("#8e8e93", 0xE713, "⚙")       # engranaje
            elif str(r["valor"]).startswith("shell:"):
                self._iconos[clave] = icono_lateral("#0a84ff", 0xE8B7, "📁")      # carpeta
            elif r["detalle"] == "Sistema":
                self._iconos[clave] = icono_lateral("#5e5ce6", 0xE7EF, "⚙")
            else:
                self._iconos[clave] = _icono_generico("#8e8e93", r["nombre"][:1].upper())
        return self._iconos[clave]

    def _actualizar(self, texto):
        self.lista.clear()
        uso = self.dock.config.get("buscador_uso", {})
        self.resultados = buscar(texto, self.programas, uso)
        for r in self.resultados:
            item = QListWidgetItem(self._icono(r), f"{r['nombre']}    ·  {r['detalle']}")
            self.lista.addItem(item)
        if self.resultados:
            self.lista.setCurrentRow(0)
        filas = min(len(self.resultados), 9)
        # Medimos cada fila de verdad (en Windows con zoom al 125 % o 150 % son más altas)
        alto = sum(self.lista.sizeHintForRow(i) for i in range(filas)) + 2 * self.lista.frameWidth() + 4
        self.lista.setFixedHeight(alto if filas else 0)
        self.lista.setVisible(bool(filas))
        self.adjustSize()

    def _ejecutar(self):
        fila = self.lista.currentRow()
        if not (0 <= fila < len(self.resultados)):
            return
        r = self.resultados[fila]
        self.hide()
        if r["accion"] == "copiar":
            QApplication.clipboard().setText(r["valor"])
            return
        if r["accion"] == "web":
            webbrowser.open(r["valor"])
            return
        abrir(r["valor"])
        uso = self.dock.config.setdefault("buscador_uso", {})
        uso[r["nombre"]] = uso.get(r["nombre"], 0) + 1
        if len(uso) > 200:                       # que no crezca para siempre
            for nombre in sorted(uso, key=uso.get)[:50]:
                del uso[nombre]
        configuracion.guardar(self.dock.config)

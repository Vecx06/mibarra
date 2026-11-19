"""
widgets_ia.py — widgets para ver cuánto llevas usado de Claude y de ChatGPT (Codex).

  claude_limites   sesión de 5 horas y semana de tu plan de Claude (con cuándo se renueva)
  claude_tokens    tokens que llevas hoy en Claude Code
  codex_limites    sesión de 5 horas y semana de Codex (ChatGPT)
"""

import webbrowser
from datetime import datetime, timedelta, timezone

from PyQt6.QtCore import QRectF, Qt, QTimer
from PyQt6.QtGui import QColor

import estilo
import ia
from widgets import Caja, Tile, TrabajoRepetido, mostrar_aviso

def color_nivel(porcentaje, normal):
    if porcentaje >= 90:
        return QColor("#ff453a")
    if porcentaje >= 70:
        return QColor("#ff9f0a")
    return QColor(normal)


def _fecha_local(fecha):
    return fecha.astimezone().strftime("%H:%M") if fecha else "—"


class LimitesWidget(Caja):
    """
    [● Nombre ]  5 h  ▬▬▬▬▭▭  42%
                 7 d  ▬▬▭▭▭▭  18%
    """

    def __init__(self, alto, nombre, color, funcion, cada, url, demo=False, datos_demo=None,
                 arreglar=None):
        super().__init__(radio=12)
        self.setFixedSize(206, alto)
        self.nombre, self.color, self.url = nombre, color, url
        self.arreglar = arreglar      # qué hacer al hacer clic cuando hay un problema de sesión
        self.trabajo = None
        self.datos = None
        self.mensaje = "Cargando…"
        self._avisado = set()
        self.clic.connect(self._al_clic)
        if demo:
            self._mostrar(datos_demo)
        else:
            self.trabajo = TrabajoRepetido(funcion, cada=cada, cada_si_falla=max(60, cada // 2))
            self.trabajo.resultado.connect(self._mostrar)
            self.trabajo.empezar()

    def _al_clic(self):
        if self.datos is None and self.arreglar and self.arreglar(self.mensaje):
            self.mensaje = "Renovando…"
            self._armar_ayuda()
            self.update()
            if self.trabajo:
                # Volver a mirar al rato (lo que tarde en abrir Claude Code y renovar)
                for segundos in (15, 40, 90, 180):
                    QTimer.singleShot(segundos * 1000, self.trabajo.despertar)
            return
        webbrowser.open(self.url)

    def _mostrar(self, datos):
        # TrabajoRepetido entrega None si hubo error; los SinDatos llegan como texto (ver _envolver)
        if isinstance(datos, str):
            self.datos, self.mensaje = None, datos
        elif datos is None:
            if self.datos is None:
                self.mensaje = "Sin conexión"
        else:
            self.datos, self.mensaje = datos, ""
            self._revisar_aviso()
        self._armar_ayuda()
        self.update()

    def _revisar_aviso(self):
        sesion = self.datos.get("sesion")
        if not sesion or sesion["porcentaje"] < 90:
            return
        clave = (sesion["renueva"].isoformat() if sesion["renueva"] else "") + str(int(sesion["porcentaje"] // 5))
        if clave in self._avisado:
            return
        self._avisado.add(clave)
        falta = ia.cuanto_falta(sesion["renueva"])
        mostrar_aviso(f"Te queda poco de {self.nombre}",
                      f"Llevas {sesion['porcentaje']:.0f}% de tu sesión de 5 horas."
                      + (f" Se renueva en {falta}." if falta else ""), tipo="ia")

    def _armar_ayuda(self):
        if not self.datos:
            accion = ("abrir Claude Code para renovar" if self.arreglar and self.mensaje in
                      (ia.VENCIDA, "Inicia sesión en Claude Code") else "ver tu uso en la web")
            self.setToolTip(f"{self.nombre}: {self.mensaje}\nClic: {accion}")
            return
        lineas = [self.nombre]
        nombres = {"sesion": "Sesión de 5 horas", "semana": "Semana", "semana_opus": "Semana (Opus)",
                   "semana_sonnet": "Semana (Sonnet)"}
        for clave, titulo in nombres.items():
            v = self.datos.get(clave)
            if v:
                falta = ia.cuanto_falta(v["renueva"])
                lineas.append(f"  {titulo}: {v['porcentaje']:.0f}%" + (f" · se renueva en {falta}" if falta else ""))
        lineas.append("Clic: ver tu uso en la web")
        self.setToolTip("\n".join(lineas))

    def pintar(self, p):
        h, w = self.height(), self.width()
        # Nombre con un puntito de color
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(self.color))
        p.drawEllipse(QRectF(10, h / 2 - 4, 8, 8))
        f_nombre = estilo.fuente(11, negrita=True)
        p.setFont(f_nombre)
        p.setPen(estilo.TEXTO)
        p.drawText(QRectF(22, 0, 52, h), Qt.AlignmentFlag.AlignVCenter, self.nombre)

        x0 = 76
        if not self.datos:
            f = estilo.fuente(10)
            p.setFont(f)
            p.setPen(estilo.TEXTO_SUAVE)
            p.drawText(QRectF(x0, 0, w - x0 - 8, h), Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap,
                       self.mensaje)
            return

        filas = [("5 h", self.datos.get("sesion")), ("7 d", self.datos.get("semana"))]
        alto_fila = 14
        y = (h - 2 * alto_fila) / 2
        f_chica, f_pct = estilo.fuente(9), estilo.fuente(10, negrita=True)
        ancho_barra = w - x0 - 22 - 34
        for etiqueta, v in filas:
            p.setFont(f_chica)
            p.setPen(estilo.TEXTO_SUAVE)
            p.drawText(QRectF(x0, y, 22, alto_fila), Qt.AlignmentFlag.AlignVCenter, etiqueta)
            pct = v["porcentaje"] if v else 0.0
            barra = QRectF(x0 + 22, y + alto_fila / 2 - 2.5, ancho_barra, 5)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(estilo.PISTA)
            p.drawRoundedRect(barra, 2.5, 2.5)
            p.setBrush(color_nivel(pct, self.color))
            p.drawRoundedRect(QRectF(barra.x(), barra.y(), barra.width() * min(pct, 100) / 100, 5), 2.5, 2.5)
            p.setFont(f_pct)
            p.setPen(estilo.TEXTO if v else estilo.TEXTO_SUAVE)
            p.drawText(QRectF(w - 40, y, 32, alto_fila), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                       f"{pct:.0f}%" if v else "—")
            y += alto_fila

    def detener(self):
        if hasattr(self, "trabajo"):
            self.trabajo.detener()

    def actualizar(self):
        pass


def _arreglar_claude(mensaje):
    """Clic en el widget de Claude con la sesión vencida o sin iniciar: abre Claude Code."""
    if mensaje in (ia.VENCIDA, "Inicia sesión en Claude Code"):
        return ia.abrir_claude_code()
    return False


def _envolver(funcion):
    """Si la función dice SinDatos, entregamos su mensaje (texto) en vez de un error."""
    def envuelta():
        try:
            return funcion()
        except ia.SinDatos as aviso:
            return str(aviso)
    return envuelta


class TokensClaudeTile(Tile):
    def __init__(self, alto, demo=False):
        super().__init__(128, alto, "Claude Code hoy", "…")
        self.clic.connect(lambda: webbrowser.open("https://claude.ai/settings/usage"))
        if demo:
            self._mostrar({"total": 1_840_000, "entrada": 12_000, "salida": 48_000, "cache_escritura": 180_000,
                           "cache_lectura": 1_600_000, "mensajes": 214})
        else:
            self.trabajo = TrabajoRepetido(_envolver(ia.tokens_claude_hoy), cada=60, cada_si_falla=120)
            self.trabajo.resultado.connect(self._mostrar)
            self.trabajo.empezar()

    def _mostrar(self, datos):
        if isinstance(datos, str) or datos is None:
            self.poner(valor="—")
            self.setToolTip(f"Tokens de Claude Code hoy\n{datos or 'No pude leerlos'}")
            return
        self.poner(valor=f"{ia.formato_tokens(datos['total'])} tokens")
        self.setToolTip(
            "Tokens de Claude Code hoy (en este PC)\n"
            f"  Respuestas: {datos['mensajes']}\n"
            f"  Entrada: {ia.formato_tokens(datos['entrada'])} · Salida: {ia.formato_tokens(datos['salida'])}\n"
            f"  Caché: {ia.formato_tokens(datos['cache_escritura'])} escritos · "
            f"{ia.formato_tokens(datos['cache_lectura'])} leídos\n"
            "Clic: ver tu uso del plan en claude.ai")

    def detener(self):
        if hasattr(self, "trabajo"):
            self.trabajo.detener()

    def actualizar(self):
        pass


def _demo(sesion, semana):
    ahora = datetime.now(timezone.utc)
    return {"sesion": {"porcentaje": sesion, "renueva": ahora + timedelta(hours=2, minutes=10)},
            "semana": {"porcentaje": semana, "renueva": ahora + timedelta(days=3)}}


CREADORES_IA = {
    "claude_limites": lambda alto, cfg, demo=False, arriba=True: LimitesWidget(
        alto, "Claude", "#d97757", _envolver(ia.limites_claude), 300, "https://claude.ai/settings/usage",
        demo, _demo(42, 18), arreglar=_arreglar_claude),
    "claude_tokens": lambda alto, cfg, demo=False, arriba=True: TokensClaudeTile(alto, demo),
    "codex_limites": lambda alto, cfg, demo=False, arriba=True: LimitesWidget(
        alto, "Codex", "#10a37f", _envolver(ia.limites_codex), 60, "https://chatgpt.com/codex",
        demo, _demo(65, 31)),
}

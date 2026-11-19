"""
logo.py — dibuja el logo de mibarra con código (sin archivos de imagen).

Un cuadrado redondeado con degradado azul-violeta y, abajo, una "barra" blanca
con tres puntitos de colores (como apps en un dock).
"""

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPixmap


def dibujar_logo(tamano=256):
    pixmap = QPixmap(tamano, tamano)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    t = tamano / 256   # todo está pensado para 256 px y se escala

    degradado = QLinearGradient(QPointF(0, 0), QPointF(tamano, tamano))
    degradado.setColorAt(0, QColor("#0a84ff"))
    degradado.setColorAt(1, QColor("#7d5cf0"))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(degradado)
    p.drawRoundedRect(QRectF(8 * t, 8 * t, 240 * t, 240 * t), 56 * t, 56 * t)

    # Brillo suave arriba
    brillo = QLinearGradient(QPointF(0, 8 * t), QPointF(0, 248 * t))
    brillo.setColorAt(0, QColor(255, 255, 255, 70))
    brillo.setColorAt(0.5, QColor(255, 255, 255, 0))
    p.setBrush(brillo)
    p.drawRoundedRect(QRectF(8 * t, 8 * t, 240 * t, 240 * t), 56 * t, 56 * t)

    # La barra
    p.setBrush(QColor(255, 255, 255, 240))
    p.drawRoundedRect(QRectF(40 * t, 150 * t, 176 * t, 58 * t), 29 * t, 29 * t)
    for i, color in enumerate(("#ff9f0a", "#30d158", "#0a84ff")):
        p.setBrush(QColor(color))
        p.drawEllipse(QRectF((66 + i * 46) * t, 164 * t, 30 * t, 30 * t))
    p.end()
    return pixmap

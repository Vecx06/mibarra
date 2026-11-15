"""
estilo.py — colores, letras y la "hoja de estilo" de mibarra.

Cambiar algo aquí cambia cómo se ve TODA la barra.
"""

from PyQt6.QtGui import QColor, QFont

# --- Colores (rojo, verde, azul, transparencia de 0 a 255) ---
ACENTO = QColor("#7aa2ff")                 # se reemplaza con el de config.json
TEXTO = QColor(242, 242, 245)
TEXTO_SUAVE = QColor(165, 165, 180)
ROJO = QColor("#ff6b6b")

CAJA = QColor(255, 255, 255, 14)           # fondo de cada widget
CAJA_HOVER = QColor(255, 255, 255, 34)     # fondo cuando el mouse pasa encima
FONDO_SOLIDO = QColor(18, 18, 24, 238)     # fondo de la barra en estilo "solido"
FONDO_VIDRIO = QColor(18, 18, 24, 70)      # tinte encima del vidrio borroso
BORDE = QColor(255, 255, 255, 30)

# Letras: se usa la primera que exista en el computador
FAMILIAS = ["Segoe UI Variable Text", "Segoe UI", "Inter", "Arial"]


def fuente(tamano, negrita=False):
    """Crea una letra del tamaño pedido (en píxeles)."""
    f = QFont()
    f.setFamilies(FAMILIAS)
    f.setPixelSize(tamano)
    f.setBold(negrita)
    return f


def poner_acento(texto_color):
    """Cambia el color de acento (lo llama main.py con el valor de config.json)."""
    global ACENTO
    color = QColor(texto_color)
    if color.isValid():
        ACENTO = color


def hoja_global():
    """Estilo para menús, tooltips y el calendario (escrito en un lenguaje parecido a CSS)."""
    acento = ACENTO.name()
    return f"""
    QMenu {{
        background: rgba(38, 38, 44, 248);
        color: #f2f2f5;
        border: 1px solid rgba(255, 255, 255, 34);
        border-radius: 12px;
        padding: 5px;
        font-size: 13px;
    }}
    QMenu::item {{ padding: 5px 26px 5px 12px; border-radius: 6px; }}
    QMenu::item:selected {{ background: {acento}; color: white; }}
    QMenu::item:disabled {{ color: #77778a; }}
    QMenu::separator {{ height: 1px; background: rgba(255, 255, 255, 25); margin: 4px 8px; }}
    QMenu::indicator {{ width: 12px; height: 12px; }}

    QToolTip {{
        background: rgb(28, 28, 34);
        color: #f2f2f5;
        border: 1px solid rgba(255, 255, 255, 30);
        padding: 4px 8px;
    }}

    #popup {{
        background: rgba(24, 24, 30, 248);
        border: 1px solid rgba(255, 255, 255, 30);
        border-radius: 14px;
    }}
    #popup QLabel {{ color: #f2f2f5; }}
    QCalendarWidget QWidget {{
        color: #f2f2f5;
        background: transparent;
        alternate-background-color: transparent;
    }}
    QCalendarWidget QToolButton {{
        color: #f2f2f5;
        background: transparent;
        font-weight: bold;
        padding: 4px 8px;
        border-radius: 6px;
    }}
    QCalendarWidget QToolButton:hover {{ background: rgba(255, 255, 255, 30); }}
    QCalendarWidget QToolButton::menu-indicator {{ image: none; }}
    QCalendarWidget QAbstractItemView {{
        selection-background-color: {acento};
        selection-color: #101014;
        outline: 0;
    }}
    QCalendarWidget QAbstractItemView:disabled {{ color: #5a5a66; }}
    QCalendarWidget QSpinBox {{ color: #f2f2f5; background: transparent; border: none; }}
    """

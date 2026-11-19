"""Configuración común de las pruebas."""

import os
import sys
import tempfile
from pathlib import Path

# Datos en una carpeta temporal: las pruebas nunca tocan tu config.json real
os.environ.setdefault("MIBARRA_DATOS", tempfile.mkdtemp(prefix="mibarra-pruebas-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def app():
    from PyQt6.QtWidgets import QApplication
    import estilo
    aplicacion = QApplication.instance() or QApplication([])
    aplicacion.setStyleSheet(estilo.hoja_global())
    return aplicacion

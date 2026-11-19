"""
construir.py — convierte mibarra en un programa .exe que no necesita Python.

    python construir.py

Resultado:
    dist/mibarra/mibarra.exe                 el programa (con todo lo que necesita al lado)
    dist/mibarra-X.Y.Z-portable.zip          la misma carpeta comprimida (versión portátil)

Después, el instalador se arma con Inno Setup:
    iscc /DVersion=X.Y.Z instalador.iss      -> dist/mibarra-X.Y.Z-instalador.exe

Necesitas: pip install pyinstaller  (y para el instalador, Inno Setup: https://jrsoftware.org/isinfo.php)
GitHub hace todo esto solo cada vez que se publica una versión (ver .github/workflows/construir.yml).
"""

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from version import VERSION

RAIZ = Path(__file__).resolve().parent
DIST = RAIZ / "dist"
BUILD = RAIZ / "build"


def info_de_version():
    """Los datos que Windows muestra en Propiedades › Detalles del .exe."""
    numeros = tuple(int(x) for x in VERSION.split(".")) + (0,)
    return f"""
VSVersionInfo(
  ffi=FixedFileInfo(filevers={numeros}, prodvers={numeros}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040A04B0', [
      StringStruct('CompanyName', 'Vecx06'),
      StringStruct('FileDescription', 'mibarra - barra para Windows'),
      StringStruct('FileVersion', '{VERSION}'),
      StringStruct('InternalName', 'mibarra'),
      StringStruct('LegalCopyright', 'MIT License - Vecx06'),
      StringStruct('OriginalFilename', 'mibarra.exe'),
      StringStruct('ProductName', 'mibarra'),
      StringStruct('ProductVersion', '{VERSION}')])]),
    VarFileInfo([VarStruct('Translation', [0x040A, 1200])])
  ]
)
"""


def main():
    BUILD.mkdir(exist_ok=True)
    archivo_version = BUILD / "version_info.txt"
    archivo_version.write_text(info_de_version(), encoding="utf-8")

    comando = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--windowed",                                   # sin ventana negra de consola
        "--name", "mibarra",
        "--icon", str(RAIZ / "recursos" / "mibarra.ico"),
        "--add-data", f"{RAIZ / 'recursos'}{os.pathsep}recursos",
        "--version-file", str(archivo_version),
        "--collect-submodules", "winrt",                # Wi-Fi/Bluetooth y música (si están instalados)
        "--distpath", str(DIST), "--workpath", str(BUILD),
        str(RAIZ / "main.py"),
    ]
    print(" ".join(comando))
    subprocess.run(comando, check=True)

    carpeta = DIST / "mibarra"
    shutil.copy(RAIZ / "LICENSE", carpeta / "LICENSE.txt")
    portable = DIST / f"mibarra-{VERSION}-portable.zip"
    with zipfile.ZipFile(portable, "w", zipfile.ZIP_DEFLATED) as z:
        for archivo in carpeta.rglob("*"):
            z.write(archivo, Path("mibarra") / archivo.relative_to(carpeta))
    print(f"\nListo:\n  {carpeta / 'mibarra.exe'}\n  {portable}")


if __name__ == "__main__":
    main()

# Cómo colaborar con mibarra

¡Gracias por querer ayudar! Cualquier aporte sirve: reportar un error, proponer una idea, mejorar la documentación o escribir código.

## Reportar errores e ideas
Usa la pestaña [Issues](https://github.com/Vecx06/mibarra/issues/new/choose). Para errores, adjunta las últimas líneas del registro
(Ajustes › Acerca de › Ver registro).

## Preparar el proyecto en tu PC
```bat
git clone https://github.com/Vecx06/mibarra
cd mibarra
python -m pip install -r requirements.txt -r requirements-opcional.txt pytest ruff
python main.py
```
Si la barra de Windows queda escondida mientras pruebas: `python main.py --restaurar`.

## Antes de mandar un cambio
```bat
ruff check .
python -m pytest
```
GitHub corre lo mismo automáticamente (en Windows) con cada cambio.

## Cómo está organizado el código
| Archivo | Qué hace |
|---|---|
| `main.py` | Arranque, guardián y `--restaurar` |
| `version.py` | El número de versión (el único lugar donde se cambia) |
| `rutas.py` | Dónde se guardan los archivos |
| `registro.py` | Registro de errores (`mibarra.log`) |
| `config.py` | Leer, revisar y guardar `config.json` |
| `estilo.py` | Colores, temas, letras e íconos |
| `dock.py` | La barra |
| `widgets.py`, `mas_widgets.py` | Los widgets |
| `ajustes.py`, `bienvenida.py` | Ventanas de Ajustes, bienvenida y avisos |
| `actualizaciones.py` | Revisar si hay versión nueva |
| `ia.py`, `widgets_ia.py` | Datos y widgets de Claude y Codex |
| `buscador.py`, `atajos.py` | Buscador rápido y atajos de teclado globales |
| `sistema_windows.py` | Todo lo que habla con Windows (`ctypes`) |
| `logo.py` | Dibuja el logo |
| `construir.py`, `instalador.iss` | Arman el `.exe` y el instalador |

## Agregar un widget nuevo
1. Crea la clase en `mas_widgets.py` (puedes basarte en `Tile` o `Caja`) con un método `actualizar()` y un parámetro `demo`.
2. Agrégala a `CREADORES` en `mas_widgets.py` (o a `CREADORES_IA` en `widgets_ia.py`).
3. Agrega su nombre a `WIDGETS_VALIDOS` en `config.py` y una línea al `CATALOGO` en `ajustes.py`.
4. Corre `python -m pytest`: hay una prueba que revisa que esas tres listas coincidan.

## Publicar una versión (para quien mantiene el proyecto)
1. Cambia el número en `version.py` y `pyproject.toml`, y anota los cambios en `CHANGELOG.md`.
2. Publica una versión en *Releases* con la etiqueta `vX.Y.Z`.
3. GitHub arma el instalador y la versión portátil solo y los agrega a la versión.

# mibarra 2.1

Manual de uso. El historial completo de cambios está en `CHANGELOG.md`.

## Novedades de la 2.1
- **Widgets de IA:** límites de Claude (sesión de 5 h y semana), tokens de Claude Code hoy y límites de Codex.
- **Buscador rápido:** Alt + Espacio. **Mostrar/ocultar la barra:** Ctrl + Alt + B.
- **Ocultar automáticamente**, botón de inicio que abre el buscador, gestos con la rueda en las apps y Enfoque con minutos a elección.

## Novedades de la 2.0
- **Instalador** para Windows: ya no necesitas Python.
- **Guardián:** si mibarra se cierra mal, la barra de Windows vuelve sola.
- **Bienvenida** la primera vez, **aviso de versiones nuevas** y **respaldar / importar / restablecer** ajustes (Ajustes › Acerca de).
- Si no caben todos los widgets, se esconden los que sobran (el reloj siempre queda).
- Registro de errores (`mibarra.log`) y botón para reportar problemas.

## Instalación

**Lo más fácil:** descarga `mibarra-X.Y.Z-instalador.exe` desde https://github.com/Vecx06/mibarra/releases/latest y ábrelo.

**Con Python (esta carpeta):**
1. Instala **Python** desde python.org y **marca "Add Python to PATH"**.
2. Haz doble clic en **`instalar.bat`** y espera a que diga "Listo".

## Uso

- **Abrir:** desde el menú Inicio (si la instalaste) o con doble clic en **`iniciar.bat`** (con Python).
- **Cerrar:** clic derecho en un espacio vacío de la barra → **Cerrar mibarra**. La barra de Windows vuelve sola.
- **Si algo sale mal** y la barra de Windows quedó escondida: normalmente vuelve sola (el guardián). Si no, usa **Inicio › Restaurar barra de Windows** (instalada) o **`restaurar_barra.bat`** (con Python).

## Qué hace cada cosa

| Parte | Clic izquierdo | Clic derecho / otros |
|---|---|---|
| Cuadraditos (inicio) | Abre el menú Inicio | Menú rápido (apagar, ajustes…) |
| Ícono de app | Abre la app / la trae al frente / la minimiza | Nueva ventana, cerrar, fijar o quitar del dock |
| Música | ⏮ ⏯ ⏭ controlan lo que suena | |
| Clima | Abre el pronóstico | |
| CPU / RAM | Administrador de tareas | |
| 🔊 Volumen | Silenciar | Rueda del mouse: subir/bajar |
| ⌃ Bandeja | Muestra u oculta un rato la barra de Windows (wifi, íconos ocultos, notificaciones) | |
| Reloj | Calendario | |
| Franjita del extremo derecho | Mostrar escritorio | |
| Espacio vacío | | Ajustes, editar widgets, recargar, cerrar |

## Ajustes

Clic derecho en un espacio vacío de la barra → **Ajustes de mibarra…**. Todo se guarda solo.

Para usuarios avanzados, los mismos ajustes están en `config.json`:

| Opción | Qué hace | Valores |
|---|---|---|
| `posicion` | Dónde va la barra | `"abajo"` o `"arriba"` |
| `alineacion` | Forma de la barra | `"centro"` (justo del tamaño necesario) o `"completa"` |
| `alto` | Alto en píxeles | ej. `56` |
| `margen` | Separación con el borde | ej. `8` |
| `estilo` | Fondo | `"vidrio"` (borroso) o `"solido"` |
| `color_acento` | Color de los detalles | ej. `"#7aa2ff"`, `"#ff7aa2"` |
| `ocultar_barra_windows` | Esconder la barra de Windows | `true` / `false` |
| `reservar_espacio` | Que las ventanas maximizadas no queden debajo | `true` / `false` |
| `esconder_en_pantalla_completa` | Esconderse con juegos y videos | `true` / `false` |
| `apps_fijadas` | Tus apps fijas | lista de `{"nombre": ..., "ruta": ...}` |
| `widgets` | Qué widgets y en qué orden | `musica`, `clima`, `red`, `cpu`, `ram`, `disco`, `bateria`, `volumen`, `bandeja`, `enfoque`, `anio`, `reloj`, `comando`, `notas`, `conexiones`, `tema`, `capturas`, `bateria_anillo`, `cpu_anillo`, `moneda`, `almacenamiento` |
| `clima` | Ciudad del clima | `ciudad`, `latitud`, `longitud` |

Ojo: en JSON los textos van entre comillas dobles, `true`/`false` van en minúscula, y cada línea lleva coma menos la última de cada bloque.

## Cómo está hecho (para estudiar el código)

| Archivo | Qué contiene |
|---|---|
| `main.py` | El punto de partida: crea la app, el guardián y `--restaurar` |
| `version.py`, `rutas.py`, `registro.py` | Versión, dónde se guardan los archivos y registro de errores |
| `actualizaciones.py`, `bienvenida.py`, `logo.py` | Aviso de versiones nuevas, bienvenida y logo |
| `config.py` | Lee y guarda `config.json` |
| `estilo.py` | Colores, letras y estilos de menús |
| `dock.py` | La barra: inicio, íconos de apps, ubicación en pantalla, menús, modo edición |
| `ajustes.py` | La ventana de Ajustes estilo Apple (interruptores, galería, buscador) |
| `widgets.py` | Cada widget (reloj, CPU, RAM, red, batería, clima, música, volumen) |
| `mas_widgets.py` | Los widgets de la 1.2 (comando, notas, conexiones, tema, capturas, anillos, moneda, almacenamiento) |
| `sistema_windows.py` | Todo lo que habla con Windows con `ctypes`: ventanas abiertas, esconder la barra, reservar espacio, efecto vidrio, teclas |

Lo recomendable es leerlos en ese orden.

## Limitaciones conocidas

- Funciona solo en el **monitor principal**.
- Los íconos de la bandeja (wifi, Discord, Steam…) no se muestran en mibarra; usa el botón **⌃** para ver la de Windows un rato.
- Las apps de la Microsoft Store (Calculadora, Fotos…) aparecen con un ícono de letra.
- El nombre de la canción necesita el paquete opcional `winrt` (lo instala `instalar.bat`). Sin él, los botones de música igual funcionan.
- Si algo falla, el detalle queda en `error.log`, en esta misma carpeta.

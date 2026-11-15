# mibarra 1.1

## Novedades de la 1.1
- **Ajustes propios estilo Apple**: clic derecho en un espacio vacío de la barra → *Ajustes de mibarra…*. Ya no se abre el Bloc de notas.
- **Galería de widgets** con buscador: agrega, quita y ordena widgets con un clic.
- **Modo edición**: mientras los Ajustes están abiertos, cada widget de la barra muestra un círculo rojo **−** para quitarlo.
- **Los cambios se aplican al tiro**, sin reiniciar.
- **Widgets nuevos**: Disco, Progreso del año y Enfoque (temporizador de 25 min para estudiar).
- **Arreglado**: la barra ahora sí se esconde con videos de YouTube (u otros) en pantalla completa.
- Clima: busca tu ciudad por nombre, sin escribir latitud ni longitud.

Una barra para Windows 10 y 11 que reemplaza a la barra de tareas: tus apps, las ventanas abiertas y widgets en vivo, todo en una sola barra.

## Instalación (una sola vez)

1. Instala **Python** desde python.org. Al instalarlo, **marca la casilla "Add Python to PATH"**.
2. Descomprime esta carpeta donde quieras, por ejemplo en `Documentos\mibarra`.
3. Haz doble clic en **`instalar.bat`** y espera a que diga "Listo".

## Uso

- **Abrir:** doble clic en **`iniciar.bat`**.
- **Cerrar:** clic derecho en un espacio vacío de la barra → **Cerrar mibarra**. La barra de Windows vuelve sola.
- **Si algo sale mal** y la barra de Windows quedó escondida: doble clic en **`restaurar_barra.bat`**.

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
| `alto` | Alto en píxeles | ej. `56` |
| `margen` | Separación con el borde | ej. `8` |
| `estilo` | Fondo | `"vidrio"` (borroso) o `"solido"` |
| `color_acento` | Color de los detalles | ej. `"#7aa2ff"`, `"#ff7aa2"` |
| `ocultar_barra_windows` | Esconder la barra de Windows | `true` / `false` |
| `reservar_espacio` | Que las ventanas maximizadas no queden debajo | `true` / `false` |
| `esconder_en_pantalla_completa` | Esconderse con juegos y videos | `true` / `false` |
| `apps_fijadas` | Tus apps fijas | lista de `{"nombre": ..., "ruta": ...}` |
| `widgets` | Qué widgets y en qué orden | `musica`, `clima`, `red`, `cpu`, `ram`, `disco`, `bateria`, `volumen`, `bandeja`, `enfoque`, `anio`, `reloj` |
| `clima` | Ciudad del clima | `ciudad`, `latitud`, `longitud` |

Ojo: en JSON los textos van entre comillas dobles, `true`/`false` van en minúscula, y cada línea lleva coma menos la última de cada bloque.

## Cómo está hecho (para estudiar el código)

| Archivo | Qué contiene |
|---|---|
| `main.py` | El punto de partida: crea la app, carga los ajustes y abre la barra |
| `config.py` | Lee y guarda `config.json` |
| `estilo.py` | Colores, letras y estilos de menús |
| `dock.py` | La barra: inicio, íconos de apps, ubicación en pantalla, menús, modo edición |
| `ajustes.py` | La ventana de Ajustes estilo Apple (interruptores, galería, buscador) |
| `widgets.py` | Cada widget (reloj, CPU, RAM, red, batería, clima, música, volumen) |
| `sistema_windows.py` | Todo lo que habla con Windows con `ctypes`: ventanas abiertas, esconder la barra, reservar espacio, efecto vidrio, teclas |

Lo recomendable es leerlos en ese orden.

## Limitaciones conocidas

- Funciona solo en el **monitor principal**.
- Los íconos de la bandeja (wifi, Discord, Steam…) no se muestran en mibarra; usa el botón **⌃** para ver la de Windows un rato.
- Las apps de la Microsoft Store (Calculadora, Fotos…) aparecen con un ícono de letra.
- El nombre de la canción necesita el paquete opcional `winrt` (lo instala `instalar.bat`). Sin él, los botones de música igual funcionan.
- Si algo falla, el detalle queda en `error.log`, en esta misma carpeta.

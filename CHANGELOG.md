# Historial de cambios

Todas las versiones de mibarra. El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y los números siguen [versionado semántico](https://semver.org/lang/es/).

## [2.1.1] — 2026-11-19

### Arreglado
- **El widget de Claude ya no se queda en "Abre Claude Code para renovar la sesión".** La sesión de
  Claude Code dura unas 8 horas y solo Claude Code la renueva. Ahora, cuando vence, mibarra le pide a
  Claude Code (sin abrir ninguna ventana) que la renueve solo, con una pregunta mínima al modelo más
  barato. Como máximo una vez cada 20 minutos.
- Si aun así no se puede, el widget dice **"Sesión vencida · clic para renovar"**: un clic abre Claude Code
  y la barra vuelve a mirar sola a los pocos segundos.
- **Las apps de la Microsoft Store fijadas en la barra (como la app de Claude) vuelven a abrir después de
  actualizarse.** Esas apps cambian de carpeta en cada versión; ahora se abren por su identificador fijo.

## [2.1.0] — 2026-11-18

### Agregado
- **Widgets de inteligencia artificial:**
  - **Límites de Claude:** cuánto llevas de tu sesión de 5 horas y de la semana, y cuándo se renueva cada una
    (usa la sesión de Claude Code de tu PC).
  - **Tokens de Claude Code:** los tokens que llevas hoy, leídos de los registros de Claude Code en tu PC.
  - **Límites de Codex (ChatGPT):** tu sesión de 5 horas y la semana, leídos de los registros de Codex.
  - **Aviso** cuando pasas el 90% de tu sesión de 5 horas (se puede desactivar).
- **Buscador rápido** estilo Spotlight con **Alt + Espacio**: programas del menú Inicio, carpetas, ajustes de
  Windows, cuentas (Enter copia el resultado) y páginas web. Aprende qué abres más.
- **Atajos de teclado** que funcionan en cualquier parte: abrir el buscador y mostrar/ocultar la barra
  (**Ctrl + Alt + B**). Se pueden cambiar en Ajustes › Comportamiento.
- **Ocultar automáticamente:** la barra se esconde y aparece al llevar el mouse al borde.
- El **botón de inicio** puede abrir el buscador de mibarra en vez del menú de Windows.
- **Gestos en los íconos de apps:** clic con la rueda abre otra ventana; girar la rueda pasa de una ventana a otra.
- **Enfoque:** elige 15, 25, 45, 60 o 90 minutos (clic derecho) y te avisa al terminar.

## [2.0.0] — 2026-11-18

### Agregado
- **Instalador para Windows** (`mibarra-2.0.0-instalador.exe`): no necesita Python ni permisos de administrador.
  Crea accesos en el menú Inicio, puede abrir mibarra al iniciar Windows y trae desinstalador.
- **Versión portátil** (`.zip`) que se usa sin instalar.
- **Guardián:** si mibarra se cierra mal (se cuelga, la cierran desde el Administrador de tareas),
  la barra de Windows vuelve sola a como estaba.
- **Pantalla de bienvenida** la primera vez: tema, forma y color.
- **Aviso de versiones nuevas** (se puede desactivar en Ajustes › Acerca de).
- **Respaldar, importar y restablecer** los ajustes.
- **Registro de errores** (`mibarra.log`) y botón para reportar problemas en GitHub.
- Logo e ícono propios.
- Pruebas automáticas que corren en un Windows real en cada cambio.

### Cambiado
- Si usas el instalador, tus ajustes y notas se guardan en `%APPDATA%\mibarra`.
  Si usas mibarra con Python, siguen en la misma carpeta del programa.
- Los widgets que no caben en la pantalla se esconden solos (el reloj siempre queda) y los Ajustes avisan cuáles.
- `config.json` se revisa al abrir: un valor mal escrito ya no rompe nada, y si el archivo entero está dañado
  se guarda una copia (`config.con-error.json`) y se usan los valores por defecto.
- Los ajustes se guardan de forma segura (si se corta la luz a mitad de guardar, el archivo no queda a medias).

## [1.3.0] — 2026-11-15
### Agregado
- Barra **centrada como en Windows 11**: mide justo lo que ocupa y se anima al crecer o achicarse.
- Opción **Ancho completo**.

## [1.2.0] — 2026-11-15
### Agregado
- Tema **claro**, **oscuro** o **automático** para la barra.
- Widgets: comando, notas, conexiones (Wi-Fi, Bluetooth, modo avión), claro/oscuro de Windows, capturas,
  anillos de batería y CPU, conversor de moneda y almacenamiento.
- Página **Moneda** en Ajustes.

## [1.1.0] — 2026-11-15
### Agregado
- Ventana de **Ajustes** estilo Apple con galería de widgets y buscador.
- **Modo edición:** círculos rojos para quitar widgets desde la barra.
- Widgets: enfoque (temporizador de estudio), disco y progreso del año.
### Arreglado
- La barra no se escondía con videos en pantalla completa si el navegador estaba maximizado.

## [1.0.0] — 2026-11-15
### Agregado
- Primera versión: botón de inicio, apps fijadas y abiertas, música, clima, red, CPU, RAM, batería,
  volumen, reloj con calendario, efecto vidrio, reserva de espacio y ocultar la barra de Windows.

[2.1.0]: https://github.com/Vecx06/mibarra/releases/tag/v2.1.0
[2.0.0]: https://github.com/Vecx06/mibarra/releases/tag/v2.0.0
[1.3.0]: https://github.com/Vecx06/mibarra/releases/tag/v1.3

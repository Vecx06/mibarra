@echo off
cd /d "%~dp0"
REM Usa esto si mibarra se cerro mal y la barra de Windows quedo escondida.
REM (Si mibarra sigue abierta pero trabada, cierrala primero desde el Administrador de tareas.)
python main.py --restaurar
pause

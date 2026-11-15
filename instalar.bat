@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==============================================
echo   Instalando lo necesario para mibarra...
echo ==============================================
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo ERROR: no se pudo instalar. Revisa que Python este instalado
  echo y que marcaste "Add Python to PATH" al instalarlo.
  pause
  exit /b 1
)
echo.
echo (Opcional) Soporte para la cancion que suena y para encender/apagar Wi-Fi y Bluetooth...
python -m pip install winrt-runtime winrt-Windows.Foundation winrt-Windows.Media.Control winrt-Windows.Devices.Radios
if errorlevel 1 echo   No se pudo instalar, pero no importa: los botones igual funcionan.
echo.
echo Listo. Ahora haz doble clic en iniciar.bat
pause

@echo off
REM Ir a la carpeta del proyecto
cd /d "C:\Users\lucas\Desktop\code\PROYECTOS\Valyro"

REM 1) Si existe un entorno virtual llamado 'venv', usarlo
if exist "venv\Scripts\python.exe" (
    echo Usando venv\Scripts\python.exe
    "venv\Scripts\python.exe" -m scripts.daily_scrape
    exit /b
)

REM 2) Si existe un entorno virtual llamado '.venv', usarlo
if exist ".venv\Scripts\python.exe" (
    echo Usando .venv\Scripts\python.exe
    ".venv\Scripts\python.exe" -m scripts.daily_scrape
    exit /b
)

REM 3) Si no hay venv, usar 'python' del sistema
echo No se ha encontrado venv, usando 'python' del sistema
python -m scripts.daily_scrape

exit

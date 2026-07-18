@echo off
title J.A.R.V.I.S. IDE - Backend Launcher
color 0A
cls

echo ============================================================
echo   J.A.R.V.I.S. IDE - Iniciando Backend FastAPI
echo ============================================================
echo.

:: Verificar Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python no encontrado. Instalalo desde https://python.org
    pause & exit /b 1
)

:: Activar entorno virtual si existe
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
    echo [OK] Entorno virtual activado
) else if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
    echo [OK] Entorno virtual activado
) else (
    echo [INFO] Sin entorno virtual, usando Python del sistema
)

:: Instalar dependencias
echo [*] Verificando dependencias del backend...
pip install fastapi "uvicorn[standard]" websockets pydantic openai anthropic requests --quiet
if %errorlevel% neq 0 (
    echo [ERROR] Fallo al instalar dependencias
    pause & exit /b 1
)
echo [OK] Dependencias OK

:: Verificar que main.py existe en la raiz
if not exist main.py (
    echo [ERROR] main.py no encontrado. Ejecuta este .bat desde la carpeta raiz del proyecto.
    pause & exit /b 1
)

echo.
echo [*] Iniciando FastAPI en http://localhost:8000
echo [*] El frontend se sirve en http://localhost:8000 (carpeta gui/)
echo [*] Presiona Ctrl+C para detener el servidor
echo.

start "" http://localhost:8000
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

pause

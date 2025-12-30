@echo off
REM Wrapper para iniciar backend con encoding UTF-8
REM Fix para emojis en logs que causan error 'gbk' codec

REM Configurar encoding UTF-8 para Python
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

REM Iniciar uvicorn con las variables correctas
cd /d "C:\Users\devteam\Proyectos\fuel-analytics-backend"
"C:\Users\devteam\Proyectos\fuel-analytics-backend\venv\Scripts\uvicorn.exe" main:app --host 0.0.0.0 --port 8000

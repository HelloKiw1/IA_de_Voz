@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Ambiente virtual nao encontrado.
  pause
  exit /b 1
)
echo Abra http://127.0.0.1:8766 no navegador.
echo Mantenha esta janela aberta durante o uso.
".venv\Scripts\python.exe" interface.py --port 8766 --open
pause

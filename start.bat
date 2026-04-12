@echo off
echo *** Awakening System / 觉醒系统 ***
cd /d "%~dp0"

python -c "import fastapi" 2>NUL || (
  echo Installing dependencies...
  pip install -r requirements.txt -q
)

python launcher.py
pause

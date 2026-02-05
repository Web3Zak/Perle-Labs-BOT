@echo off
echo === Activating virtual environment ===
call venv\Scripts\activate.bat

echo === Starting bot ===
python main.py

pause

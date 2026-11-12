@echo off
cd /d "C:\Users\USER\OneDrive\Desktop\monitoring ideation\safetynet"
"C:\Users\USER\OneDrive\Desktop\monitoring ideation\venv\Scripts\python.exe" manage.py check_inactivity >> check_log.txt 2>&1
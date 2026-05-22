@echo off
echo Starting Arabic LLM Backend on port 5000...
cd /d "%~dp0Backend"
call ..\venv\Scripts\activate
python -m uvicorn main:app --host 0.0.0.0 --port 5000 --reload

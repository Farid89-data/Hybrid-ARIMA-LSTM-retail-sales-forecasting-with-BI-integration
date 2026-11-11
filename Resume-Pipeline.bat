@echo off
cd /d "%~dp0"
start "Pipeline runner" cmd /k ".venv\Scripts\python.exe scripts\run_chunks.py"

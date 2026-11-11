@echo off
cd /d "%~dp0"
if not exist outputs\state mkdir outputs\state
echo pause> outputs\state\PAUSE
echo Pause requested. The runner finishes the current units and prints "Paused safely" in its window.

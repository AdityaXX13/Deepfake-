>>>>>>> cbf1f73 (Add Fly deployment configuration)
@echo off
title Deepfake Detection - Auto Startup

echo ==========================================
echo       DEEPFAKE DETECTION SYSTEM
echo ==========================================

set "ROOT=%~dp0"
set "FRONTEND=%ROOT%"

cd /d "%ROOT%"

echo.
echo [1/3] Starting FastAPI Backend...

start "Deepfake Backend" cmd /k "cd /d ""%ROOT%"" && python -m uvicorn backend.main:app --host 127.0.0.1 --port 8765"

timeout /t 4 /nobreak >nul

echo.
echo [2/3] Starting Frontend...

if not exist "%FRONTEND%package.json" (
    echo ERROR: package.json not found in project folder.
    echo Please check your frontend folder location.
    pause
    exit /b 1
)

start "Deepfake Frontend" cmd /k "cd /d ""%FRONTEND%"" && npm run dev"

timeout /t 5 /nobreak >nul

echo.
echo [3/3] Opening Website...

start "" http://localhost:5173

echo.
echo ==========================================
echo   DEEPFAKE WEBSITE STARTED!
echo ==========================================
echo Backend: http://127.0.0.1:8765
echo API Docs: http://127.0.0.1:8765/docs
echo Frontend: http://localhost:5173
echo.
echo Do not close the Backend and Frontend windows.
echo.

>>>>>>> cbf1f73 (Add Fly deployment configuration)

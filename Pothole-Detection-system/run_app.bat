@echo off
setlocal
cd /d "%~dp0"
if not exist ".env" copy ".env.example" ".env" >nul
if exist ".runtime\node-v26.13.1-win-x64\node.exe" set "PATH=%~dp0.runtime\node-v26.13.1-win-x64;%~dp0.runtime\node-v26.13.1-win-x64\node_modules\npm\bin;%PATH%"

if not exist ".venv\Scripts\python.exe" (
  echo Creating Python environment...
  py -m venv --without-pip .venv || goto :error
)
echo Installing backend requirements...
".venv\Scripts\python.exe" -m pip --version >nul 2>nul
if errorlevel 1 (
  py -m pip --python ".venv\Scripts\python.exe" install -r backend\requirements.txt || goto :error
) else (
  ".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt || goto :error
)

where node >nul 2>nul || (echo Node.js is required. Install Node.js 20+ and run this script again.& exit /b 1)
if not exist "frontend\node_modules" (
  echo Installing frontend dependencies...
  pushd frontend
  call npm install || (popd & goto :error)
  popd
)

echo Starting PotholeAI API at http://127.0.0.1:8000
start "PotholeAI Backend" /min "%~dp0.venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir "%~dp0backend" --host 127.0.0.1 --port 8000
echo Starting PotholeAI dashboard at http://localhost:5173
start "PotholeAI Frontend" /min cmd /c "cd /d ""%~dp0frontend"" && npm run dev -- --host 127.0.0.1"
echo Both services are starting. Close their terminal windows to stop them.
exit /b 0

:error
echo Startup failed. Review the error above.
exit /b 1

@echo off
echo 🚀 Setting up Research Paper Reference Agent - Full Stack...
echo.

echo 📋 This will set up both backend and frontend
echo.

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python is not installed or not in PATH
    echo    Please install Python 3.8+ first
    pause
    exit /b 1
)

REM Check if Node.js is available
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Node.js is not installed or not in PATH
    echo    Please install Node.js 18+ first
    pause
    exit /b 1
)

echo ✅ Python and Node.js detected
echo.

echo 🔧 Setting up backend...
echo Installing Python dependencies...
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo ❌ Failed to install Python dependencies
    pause
    exit /b 1
)

echo ✅ Backend dependencies installed
echo.

echo 🔧 Setting up frontend...
cd frontend

REM Check if node_modules exists
if not exist "node_modules" (
    echo Installing frontend dependencies...
    npm install
    
    if %errorlevel% neq 0 (
        echo ❌ Failed to install frontend dependencies
        pause
        exit /b 1
    )
) else (
    echo ✅ Frontend dependencies already installed
)

cd ..

echo.
echo 🎉 Setup complete! Starting servers...
echo.

echo 📡 Starting backend server on port 8000...
start "Backend Server" cmd /k "python run_server.py"

echo ⏳ Waiting for backend to start...
timeout /t 5 /nobreak >nul

echo 🌐 Starting frontend server on port 3000...
start "Frontend Server" cmd /k "cd frontend && npm run dev"

echo.
echo 🎉 Both servers are starting up!
echo.
echo 📱 Frontend: http://localhost:3000
echo 📡 Backend API: http://localhost:8000
echo 📚 API Docs: http://localhost:8000/docs
echo.
echo Press any key to close this window...
pause >nul

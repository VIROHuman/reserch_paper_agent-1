#!/bin/bash

echo "🚀 Setting up Research Paper Reference Agent - Full Stack..."
echo

echo "📋 This will set up both backend and frontend"
echo

# Check if Python is available
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "❌ Python is not installed or not in PATH"
    echo "   Please install Python 3.8+ first"
    exit 1
fi

# Check if Node.js is available
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed or not in PATH"
    echo "   Please install Node.js 18+ first"
    exit 1
fi

echo "✅ Python and Node.js detected"
echo

echo "🔧 Setting up backend..."
echo "Installing Python dependencies..."
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "❌ Failed to install Python dependencies"
    exit 1
fi

echo "✅ Backend dependencies installed"
echo

echo "🔧 Setting up frontend..."
cd frontend

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
    
    if [ $? -ne 0 ]; then
        echo "❌ Failed to install frontend dependencies"
        exit 1
    fi
else
    echo "✅ Frontend dependencies already installed"
fi

cd ..

echo
echo "🎉 Setup complete! Starting servers..."
echo

echo "📡 Starting backend server on port 8000..."
python run_server.py &
BACKEND_PID=$!

echo "⏳ Waiting for backend to start..."
sleep 5

echo "🌐 Starting frontend server on port 3000..."
cd frontend
npm run dev &
FRONTEND_PID=$!

cd ..

echo
echo "🎉 Both servers are starting up!"
echo
echo "📱 Frontend: http://localhost:3000"
echo "📡 Backend API: http://localhost:8000"
echo "📚 API Docs: http://localhost:8000/docs"
echo
echo "Press Ctrl+C to stop both servers"

# Function to cleanup on exit
cleanup() {
    echo
    echo "🛑 Stopping servers..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    echo "✅ Servers stopped"
    exit 0
}

# Trap Ctrl+C
trap cleanup INT

# Wait for user to stop
wait

#!/bin/bash

# Wordhord Launcher - Optimized for Thermal Management & Dual GPU
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "🚀 Starting Wordhord (Optimized for Dual-GPU)..."

# 1. Clean up stale processes
fuser -k 8001/tcp 5174/tcp 2>/dev/null
pkill -f "electron" 2>/dev/null

# 2. Start Backend
echo "🧠 Starting Backend..."
cd "$DIR/backend"

# Load Gemini API Key into environment
if [ -f "$DIR/../wordhord_api.txt" ]; then
    export GOOGLE_API_KEY=$(cat "$DIR/../wordhord_api.txt")
    echo "✅ Gemini API Key loaded into environment."
fi

# Note: Ollama/Local LLM references removed. System now uses Gemini 2.0 API.
if [ -f "$DIR/../panglossia/google-credentials.json" ]; then
    export GOOGLE_APPLICATION_CREDENTIALS="$DIR/../panglossia/google-credentials.json"
fi

./venv_latest/bin/python -B main.py > backend.log 2>&1 &
BACKEND_PID=$!

# 3. Start Frontend (Vite)
echo "🖥️ Starting Frontend Dev Server..."
cd "$DIR/frontend"
npm run dev > frontend.log 2>&1 &
FRONTEND_PID=$!

sleep 5

# 4. Launch Electron (Intel iGPU for UI)
echo "✨ Launching UI on Intel iGPU..."
# DRI_PRIME=0 forces the Intel Integrated GPU on Linux
# We use Intel for UI to leave NVIDIA free for heavy tasks if needed.
DRI_PRIME=0 npx electron . --no-sandbox > electron.log 2>&1 &
ELECTRON_PID=$!

echo "-----------------------------------"
echo "✅ Wordhord is running!"
echo "GPU Split: Intel (UI) | API (LLM)"
echo "-----------------------------------"

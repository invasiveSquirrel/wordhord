#!/bin/bash

# Wordhord Launcher - Optimized for Thermal Management & Dual GPU
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "🚀 Starting Wordhord (Optimized for Dual-GPU)..."

# 1. Clean up stale processes
fuser -k 8001/tcp 5174/tcp 2>/dev/null
pkill -f "wordhord.*electron" 2>/dev/null

# 2. Start Backend (NVIDIA for Ollama)
echo "🧠 Starting Backend (NVIDIA focus)..."
cd "$DIR/backend"
export OLLAMA_MODEL="gemma2:9b"
export OLLAMA_NUM_PARALLEL=1
# Force Ollama to use the NVIDIA card (usually default, but ensures visibility)
export CUDA_VISIBLE_DEVICES=0 

if [ -f "$DIR/../polyglossia/google-credentials.json" ]; then
    export GOOGLE_APPLICATION_CREDENTIALS="$DIR/../polyglossia/google-credentials.json"
fi

./venv/bin/python -B main.py > backend.log 2>&1 &
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
# We removed --disable-gpu to allow smooth animations on the Intel card
DRI_PRIME=0 npx electron . --no-sandbox > electron.log 2>&1 &
ELECTRON_PID=$!

echo "-----------------------------------"
echo "✅ Wordhord is running!"
echo "GPU Split: Intel (UI) | NVIDIA (LLM)"
echo "-----------------------------------"

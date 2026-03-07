# Wordhord ði

Wordhord is an AI-powered vocabulary training desktop application designed for language learners. It uses LLMs to generate contextual flashcards and provides instant audio feedback for pronunciation.

## Features
- **Smart Flashcards**: Context-rich cards with IPA, grammatical gender, and example sentences.
- **AI Generation**: Automatically generate related vocabulary based on your existing deck.
- **Native Audio**: Instant text-to-speech using Google Cloud TTS.
- **Pronunciation Comparison**: Record your voice and see your waveform side-by-side with a native speaker's.
- **Spaced Repetition**: Intelligent study plans based on your learning progress (SQLite-backed).

---

## 🚀 Setting Up Ollama (AI Engine)

Wordhord requires [Ollama](https://ollama.com/) to be running locally to generate cards and provide feedback.

1.  **Download**: Visit [ollama.com](https://ollama.com/download) and download the installer for your OS (Windows, macOS, or Linux).
2.  **Install**: Run the installer and ensure the Ollama icon appears in your system tray.
3.  **Pull the Model**: Open your terminal (PowerShell, Terminal.app, or Bash) and run:
    ```bash
    ollama run gemma2:9b
    ```
    *Note: The app is configured for `gemma2:9b` by default. You can use other models by setting the `OLLAMA_MODEL` environment variable.*
4.  **Keep it Running**: Ensure Ollama is running in the background while using Wordhord.

---

## 💻 Installation

### Prerequisites
- **Node.js** (v18 or higher)
- **Python** (v3.10 or higher)
- **FFmpeg**: Required for audio playback (`ffplay`).

### 1. Clone the repository
```bash
git clone https://github.com/invasiveSquirrel/wordhord.git
cd wordhord
```

### 2. OS-Specific Setup

#### **Windows**
1.  **Install FFmpeg**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) or via Chocolatey: `choco install ffmpeg`.
2.  **Backend**:
    ```powershell
    cd backend
    python -m venv venv
    .\venv\Scripts\activate
    pip install fastapi sqlalchemy uvicorn pydantic langchain-ollama google-cloud-texttospeech google-cloud-speech
    ```
3.  **Frontend**:
    ```powershell
    cd ..\frontend
    npm install
    ```

#### **macOS**
1.  **Install FFmpeg**: Use Homebrew: `brew install ffmpeg`.
2.  **Backend**:
    ```bash
    cd backend
    python3 -m venv venv
    source venv/bin/activate
    pip install fastapi sqlalchemy uvicorn pydantic langchain-ollama google-cloud-texttospeech google-cloud-speech
    ```
3.  **Frontend**:
    ```bash
    cd ../frontend
    npm install
    ```

#### **Linux (CachyOS/Arch/Ubuntu)**
1.  **Install FFmpeg**: `sudo pacman -S ffmpeg` or `sudo apt install ffmpeg`.
2.  **Setup**: Follow the macOS steps above or use the provided `./start.sh`.

---

## 🏃 Running the Application

### Windows (Manual)
You need two terminals open:
1.  **Terminal 1 (Backend)**:
    ```powershell
    cd backend
    .\venv\Scripts\activate
    python main.py
    ```
2.  **Terminal 2 (Frontend)**:
    ```powershell
    cd frontend
    npm run dev
    ```
3.  **Terminal 3 (Electron)**:
    ```powershell
    cd frontend
    npm run electron
    ```

### Linux / macOS / Git Bash
```bash
./start.sh
```

---

## 📖 How to Use Wordhord

1.  **Select a Language**: Click a language button at the top.
2.  **Study**: Flip cards, listen to native audio, and record your own voice to compare waveforms.
3.  **Build**: Click **"New Cards"** to have the AI expand your deck based on your learning history.

---

## Technical Details
- **Backend**: FastAPI with SQLAlchemy (SQLite).
- **Frontend**: React (TypeScript) + Vite.
- **Desktop**: Electron.
- **AI**: Local Ollama (gemma2:9b).

## License
MIT

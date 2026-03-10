# Wordhord ð

Wordhord is an AI-powered vocabulary training desktop application designed for language learners. It uses LLMs to generate contextual flashcards and provides instant audio feedback for pronunciation.

## Features
- **Smart Flashcards**: Context-rich cards with IPA, grammatical gender, and example sentences.
- **Dynamic Audio & Waveforms**: Slow down native audio (0.5x, 0.75x, 1.0x) with pitch-preserved playback. A moving progress bar tracks across the waveform as you listen.
- **Quick-Listen Icon**: Click the sound icon directly on the front of a card for instant audio feedback.
- **AI Generation**: Automatically generate related vocabulary based on your existing deck.
- **Native Audio**: Instant text-to-speech using Google Cloud TTS or local fallback.
- **Pronunciation Comparison**: Record your voice and see your waveform side-by-side with a native speaker's.
- **Improved Card Management**: Reliable Card Editor with real-time synchronization and language-aware state handling.
- **Spaced Repetition**: Intelligent study plans based on your learning progress (SQLite-backed).
- **IPA Support**: Click the speaker icon to hear phonetic pronunciations via espeak-ng with adjustable speeds.

---

## 🚀 Setting Up Ollama (AI Engine)

Wordhord requires [Ollama](https://ollama.com/) to be running locally to generate cards and provide feedback.

1.  **Download**: Visit [ollama.com](https://ollama.com/download) and download the installer for your OS (Windows, macOS, or Linux).
2.  **Install**: Run the installer and ensure the Ollama icon appears in your system tray.
3.  **Pull the Model**: Open your terminal and run:
    ```bash
    ollama run gemma2:9b
    ```
4.  **Keep it Running**: Ensure Ollama is running in the background while using Wordhord.

---

## 💻 Installation

### Prerequisites
- **Node.js** (v18 or higher)
- **Python** (v3.10 or higher)
- **FFmpeg**: Required for audio playback (`ffplay`).
- **espeak-ng**: Required for IPA speech.

### 1. Clone the repository
```bash
git clone https://github.com/invasiveSquirrel/wordhord.git
cd wordhord
```

### 2. OS-Specific Setup

#### **Windows**
1.  **Install FFmpeg & espeak-ng**.
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
1.  **Install FFmpeg & espeak-ng** (via Homebrew).
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
1.  **Install FFmpeg & espeak-ng**: `sudo pacman -S ffmpeg espeak-ng`.
2.  **Setup**: Follow the macOS steps above or use the provided `./start.sh`.

---

## 🏃 Running the Application

### Windows (Manual)
You need two terminals open:
1.  **Backend**: `python main.py` (in venv)
2.  **Frontend**: `npm run dev`
3.  **Electron**: `npm run electron`

### Linux / macOS / Git Bash
```bash
./start.sh
```

---

## 📖 How to Use Wordhord

1.  **Select a Language**: Click a language button at the top (e.g., Gàidhlig, Swedish).
2.  **Study**: Flip cards, listen to native audio, and record your own voice to compare waveforms.
3.  **Build**: Click **"New Cards"** to have the AI expand your deck based on your learning history.

---

## 🔄 Integration with Panglossia

Wordhord shares a database with **Panglossia**. Any vocabulary words you "learn" during a chat session in Panglossia will automatically appear in your Wordhord deck for spaced repetition study.

---

## 📦 Bulk Generation

If you want to quickly build a large initial vocabulary, you can use the `bulk_generate_cards.py` script.

1.  **Activate Backend venv**:
    ```bash
    cd backend
    source venv/bin/activate
    ```
2.  **Run the Script**:
    ```bash
    python bulk_generate_cards.py
    ```
    This will generate up to 3000 common words for each supported language (Dutch, Finnish, German, Portuguese, Spanish, Swedish) using your local Ollama instance. It includes a cooldown to prevent CPU/GPU overheating during long runs.

---

## Technical Details
- **Backend**: FastAPI with SQLAlchemy (SQLite).
- **Frontend**: React (TypeScript) + Vite.
- **Desktop**: Electron.
- **AI**: Local Ollama (gemma2:9b).

## License
MIT

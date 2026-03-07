# Wordhord ði

Wordhord is an AI-powered vocabulary training desktop application designed for language learners. It uses LLMs to generate contextual flashcards and provides instant audio feedback for pronunciation.

## Features
- **Smart Flashcards**: Context-rich cards with IPA, grammatical gender, and example sentences.
- **AI Generation**: Automatically generate related vocabulary based on your existing deck.
- **Native Audio**: Instant text-to-speech using Google Cloud TTS.
- **Pronunciation Comparison**: Record your voice and see your waveform side-by-side with a native speaker's.
- **Spaced Repetition**: Intelligent study plans based on your learning progress (SQLite-backed).

## Prerequisites
- **Node.js** (v18+)
- **Python** (3.11+)
- **Ollama** (Running locally with `gemma2:9b` or similar)
- **FFmpeg** (specifically `ffplay` for audio)
- **Google Cloud Credentials** (Optional, for high-quality TTS/STT)

---

## Installation

### 1. Clone the repository
```bash
git clone https://github.com/invasiveSquirrel/wordhord.git
cd wordhord
```

### 2. Backend Setup
Create a virtual environment and install dependencies:
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install fastapi sqlalchemy uvicorn pydantic langchain-ollama google-cloud-texttospeech google-cloud-speech
```

### 3. Frontend Setup
Install Node dependencies:
```bash
cd ../frontend
npm install
```

---

## Running the Application

### The Easy Way (Linux)
Run the provided start script from the root directory:
```bash
./start.sh
```
This script automatically starts the FastAPI backend, the Vite dev server, and the Electron window.

### Desktop Entry
On Linux, you can install a desktop entry to launch Wordhord from your application menu:
1. Copy `wordhord.desktop` to `~/.local/share/applications/`
2. Update the `Exec` and `Icon` paths in the file to match your installation directory.

---

## How to Use Wordhord

### 1. Select a Language
Click one of the language buttons at the top (e.g., Swedish, German, Finnish) to load your deck.

### 2. Study Cards
- **Front**: See the word or phrase.
- **Flip**: Click the card to see the translation, IPA, grammar details, and an example sentence.
- **Native Audio**: Click "Fetch & Play Native" to hear the native pronunciation.
- **Test Speech**: Click "Test Speech" and record yourself. You will see your waveform compared to the native one and receive feedback.
- **Evaluation**: Click "Got it" or "Again" to update the card's spaced repetition statistics.

### 3. Generate New Cards
Click the **"New Cards"** button. The AI will generate 5 new cards related to your current deck and save them directly to the SQLite database.

---

## Vocabulary Management

### Migration from Markdown
If you have vocabulary in Markdown files (format: `- **word** (translation)`), you can migrate them to the SQLite database:
```bash
source backend/venv/bin/activate
python migrate_to_sqlite.py
```
This script parses files like `swedish_vocab.md` and imports them into `wordhord.db`.

### Bulk Generation (The Builder)
To generate thousands of cards automatically:
1. Open a terminal.
2. Run:
```bash
source backend/venv/bin/activate
python backend/bulk_generate_cards.py
```
This will continuously generate batches of 10 cards per language until it reaches your target (default 3000), saving them directly to the database.

---

## Technical Details
- **Backend**: FastAPI with SQLAlchemy (SQLite).
- **Frontend**: React (TypeScript) + Vite.
- **Desktop**: Electron.
- **AI**: Local Ollama (gemma2:9b).

---

## Acknowledgments
- Uses [Ollama](https://ollama.ai/) for local AI inference.
- Powered by [FastAPI](https://fastapi.tiangolo.com/) and [React](https://reactjs.org/).

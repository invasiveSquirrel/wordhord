# Wordhord ði

Wordhord is an AI-powered vocabulary training desktop application designed for language learners. It uses LLMs to generate contextual flashcards and provides instant audio feedback for pronunciation.

## Features
- **Smart Flashcards**: Context-rich cards with IPA, grammatical gender, and example sentences.
- **AI Generation**: Automatically generate related vocabulary based on your existing deck.
- **Native Audio**: Instant text-to-speech using Google Cloud TTS.
- **Pronunciation Testing**: Record your voice and get AI feedback on your pronunciation.
- **Spaced Repetition**: Intelligent study plans based on your learning progress.

## Languages Supported
- Swedish (with Pitch Accent support)
- German (with Verb Prefix support)
- Finnish (with Morphological notes)
- Spanish
- Portuguese
- Dutch

## Prerequisites
- **Node.js** (v18+)
- **Python** (3.10+)
- **Ollama** (Running locally with `gemma2:9b` or similar)
- **Google Cloud Credentials** (Optional, for high-quality TTS/STT)
- **ffplay** (Part of FFmpeg, for audio playback)

## Installation

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/wordhord.git
cd wordhord
```

### 2. Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Frontend Setup
```bash
cd ../frontend
npm install
```

## Running the Application
Use the provided start script:
```bash
./start.sh
```

## Bulk Vocabulary Generation
To generate thousands of cards automatically:
```bash
source backend/venv/bin/activate
python backend/bulk_generate_cards.py
```

## Configuration
- Set `OLLAMA_MODEL` environment variable to choose your model (default: `gemma2:9b`).
- For Google Cloud TTS, set `GOOGLE_APPLICATION_CREDENTIALS` to your service account JSON file.

## Acknowledgments
- Uses [Ollama](https://ollama.ai/) for local AI inference.
- Powered by [FastAPI](https://fastapi.tiangolo.com/) and [React](https://reactjs.org/).

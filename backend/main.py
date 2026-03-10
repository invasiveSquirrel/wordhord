from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, UniqueConstraint, func
from sqlalchemy.orm import declarative_base, sessionmaker
import os
import subprocess
import json
import re
import threading
import tempfile
from datetime import datetime, timedelta
from langchain_ollama import OllamaLLM

# Database Setup
DB_PATH = "/home/chris/wordhord.db"
engine = create_engine(f"sqlite:///{DB_PATH}")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class CardModel(Base):
    __tablename__ = "cards"
    id = Column(Integer, primary_key=True, index=True)
    language = Column(String)
    term = Column(String)
    translation = Column(String)
    ipa = Column(String)
    gender = Column(String)
    plural = Column(String)
    part_of_speech = Column(String)
    tone = Column(String)
    prefix = Column(String)
    preposition = Column(String)
    case = Column(String)
    accusative = Column(String) # For German N-declension
    conjugations = Column(String)
    example = Column(String)
    example_translation = Column(String)
    level = Column(String)
    interval = Column(Integer, default=0)
    ease_factor = Column(Float, default=2.5)
    repetition_count = Column(Integer, default=0)
    next_review = Column(DateTime, default=datetime.utcnow)
    passed = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    __table_args__ = (UniqueConstraint('language', 'term', name='_language_term_uc'),)

Base.metadata.create_all(bind=engine)

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Configuration
MODEL_NAME = os.getenv("OLLAMA_MODEL", "gemma2:9b")
llm = OllamaLLM(model=MODEL_NAME, temperature=0.1)

# TTS Paths
POLYGLOSSIA_DIR = "/home/chris/panglossia"
PIPER_BIN = os.path.join(POLYGLOSSIA_DIR, "backend", "bin", "piper")
PIPER_LIB = os.path.join(POLYGLOSSIA_DIR, "backend", "bin")
VOICE_DIR = os.path.join(POLYGLOSSIA_DIR, "backend", "voices")

try:
    from google.cloud import texttospeech
    from google.cloud import speech
except ImportError:
    texttospeech = None
    speech = None

class ProgressRequest(BaseModel):
    card_id: int
    quality: int

class SpeakRequest(BaseModel):
    text: str
    language: str
    speed: float = 0.95

@app.get("/cards/{language}")
async def get_cards(language: str, db = Depends(get_db), levels: str = None):
    query = db.query(CardModel).filter(CardModel.language == language)
    if levels:
        level_list = levels.split(",")
        if "" in level_list:
            query = query.filter((CardModel.level.in_(level_list)) | (CardModel.level == None))
        else:
            query = query.filter(CardModel.level.in_(level_list))
    cards = query.all()
    return {"cards": [c.__dict__ for c in cards]}

@app.get("/levels/{language}")
async def get_levels(language: str, db = Depends(get_db)):
    levels = db.query(CardModel.level).filter(CardModel.language == language).distinct().all()
    return {"levels": [l[0] for l in levels if l[0]]}

@app.post("/cards/review")
async def review_card(request: ProgressRequest, db = Depends(get_db)):
    card = db.query(CardModel).filter(CardModel.id == request.card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    q = request.quality
    if q >= 3:
        card.passed += 1
        if card.repetition_count == 0: card.interval = 1
        elif card.repetition_count == 1: card.interval = 6
        else: card.interval = int(card.interval * card.ease_factor)
        card.repetition_count += 1
        card.ease_factor = max(1.3, card.ease_factor + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)))
    else:
        card.failed += 1
        card.repetition_count = 0
        card.interval = 1
    card.next_review = datetime.utcnow() + timedelta(days=card.interval)
    db.commit()
    return {"status": "ok"}

@app.post("/cards/next")
async def next_cards(request: dict, db = Depends(get_db)):
    language = request.get("language")
    levels = request.get("levels", [])
    now = datetime.utcnow()
    query = db.query(CardModel).filter(CardModel.language == language)
    if levels: 
        if "" in levels or "None" in levels:
            query = query.filter((CardModel.level.in_(levels)) | (CardModel.level == None))
        else:
            query = query.filter(CardModel.level.in_(levels))
    overdue = query.filter(CardModel.next_review <= now).order_by(CardModel.next_review).limit(10).all()
    if len(overdue) < 10:
        new_cards = query.filter(CardModel.repetition_count == 0).limit(10 - len(overdue)).all()
        overdue.extend(new_cards)
    return {"ids": [str(c.id) for c in overdue]}

@app.post("/native_audio")
async def get_native_audio(request: SpeakRequest):
    text = request.text.strip()
    if not text: raise HTTPException(status_code=400)
    try:
        if texttospeech and os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            client = texttospeech.TextToSpeechClient()
            synthesis_input = texttospeech.SynthesisInput(text=text)
            gtts_voice_map = {
                "swedish": ("sv-SE", "sv-SE-Chirp3-HD-Laomedeia"),
                "german": ("de-DE", "de-DE-Chirp3-HD-Leda"),
                "finnish": ("fi-FI", "fi-FI-Chirp3-HD-Despina"),
                "portuguese": ("pt-BR", "pt-BR-Chirp3-HD-Dione"),
                "spanish": ("es-US", "es-US-Chirp3-HD-Callirrhoe"),
                "dutch": ("nl-NL", "nl-NL-Chirp3-HD-Despina")
            }
            l_code, v_name = gtts_voice_map.get(request.language, ("en-US", "en-US-Journey-F"))
            voice = texttospeech.VoiceSelectionParams(language_code=l_code, name=v_name)
            audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16, speaking_rate=0.95)
            response = client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
            return Response(content=response.audio_content, media_type="audio/wav")
        # Local Fallback
        voice_map = {"swedish": "sv_female.onnx", "finnish": "fi_female.onnx", "spanish": "es_mx_ximena.onnx"}
        if request.language in voice_map:
            v_path = os.path.join(VOICE_DIR, voice_map[request.language])
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                temp_wav = tmp.name
            env = os.environ.copy()
            env["LD_LIBRARY_PATH"] = f"{PIPER_LIB}:{env.get('LD_LIBRARY_PATH', '')}"
            subprocess.run([PIPER_BIN, "--model", v_path, "--output_file", temp_wav], input=text, text=True, env=env, check=True)
            with open(temp_wav, "rb") as f: content = f.read()
            os.unlink(temp_wav)
            return Response(content=content, media_type="audio/wav")
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))
    raise HTTPException(status_code=501)

@app.post("/evaluate_pronunciation")
async def evaluate_pronunciation(audio: UploadFile = File(...), language: str = Form(...), expected_text: str = Form(...)):
    # Best Speech Eval: Levenshtein distance on phonemes or characters from STT
    transcript = "[Speech Recognition Failed]"
    feedback = "Ensure you emphasize the primary stress marks."
    if speech and os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        try:
            client = speech.SpeechClient()
            content = await audio.read()
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
                sample_rate_hertz=48000,
                language_code="sv-SE" if language == "swedish" else "de-DE" if language == "german" else "en-US",
            )
            response = client.recognize(config=config, audio=speech.RecognitionAudio(content=content))
            if response.results:
                transcript = response.results[0].alternatives[0].transcript
                # Use LLM for semantic & phonetic evaluation
                prompt = f"Expected: '{expected_text}'. User said: '{transcript}'. Language: {language}. Provide 1-sentence concise feedback."
                feedback = llm.invoke(prompt)
        except Exception as e: feedback = f"Error: {e}"
    return {"transcript": transcript, "feedback": feedback}

@app.post("/speak_ipa")
async def speak_ipa(request: SpeakRequest):
    def play_ipa():
        subprocess.run(["espeak-ng", "-v", "en-gb", "-s", "150", f"[[{request.text}]]"], check=False)
    threading.Thread(target=play_ipa, daemon=True).start()
    return {"status": "ok"}

@app.post("/progress/reset")
async def reset_progress(request: dict, db = Depends(get_db)):
    language = request.get("language")
    cards = db.query(CardModel).filter(CardModel.language == language).all()
    for card in cards:
        card.passed = card.failed = card.repetition_count = card.interval = 0
        card.ease_factor = 2.5
        card.next_review = datetime.utcnow()
    db.commit()
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

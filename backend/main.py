from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZIPMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Float, DateTime, UniqueConstraint, Index, func, select, update, delete
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.inspection import inspect
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import OllamaLLM
from rapidfuzz import fuzz
import os
import asyncio
import subprocess
import json
import re
import threading
import tempfile
import aiofiles
from datetime import datetime, timedelta

# Database Setup
DB_PATH = "/home/chris/wordhord/wordhord.db"
engine = create_async_engine(f"sqlite+aiosqlite:///{DB_PATH}")
AsyncSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()

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
    accusative = Column(String)
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
    __table_args__ = (
        UniqueConstraint('language', 'term', name='_language_term_uc'),
        Index('idx_language', 'language'),
        Index('idx_language_level', 'language', 'level'),
        Index('idx_next_review', 'next_review'),
        Index('idx_repetition_count', 'repetition_count'),
    )

app = FastAPI()
app.add_middleware(GZIPMiddleware, minimum_size=1000)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# Configuration
API_KEY_FILE = "/home/chris/wordhord/wordhord_api.txt"
with open(API_KEY_FILE, "r") as f:
    GOOGLE_API_KEY = f.read().strip()

# Gemini 2.5 Flash
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=GOOGLE_API_KEY, temperature=0.1)
# Local Fallback
ollama_llm = OllamaLLM(model=os.getenv("OLLAMA_MODEL", "gemma2:9b"), temperature=0.1)

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

class CardCreate(BaseModel):
    language: str
    term: str
    translation: str
    ipa: str = ""
    gender: str = ""
    plural: str = ""
    part_of_speech: str = ""
    tone: str = ""
    prefix: str = ""
    preposition: str = ""
    case: str = ""
    accusative: str = ""
    conjugations: str = ""
    example: str = ""
    example_translation: str = ""
    level: str = ""

@app.post("/cards")
async def create_card(card_data: CardCreate, db: AsyncSession = Depends(get_db)):
    new_card = CardModel(**card_data.dict())
    db.add(new_card)
    try:
        await db.commit()
        await db.refresh(new_card)
        return new_card
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Error creating card: {str(e)}")

@app.put("/cards/{card_id}")
async def update_card(card_id: int, card_data: CardCreate, db: AsyncSession = Depends(get_db)):
    stmt = select(CardModel).filter(CardModel.id == card_id)
    result = await db.execute(stmt)
    card = result.scalars().first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    for key, value in card_data.dict().items():
        setattr(card, key, value)
    await db.commit()
    return {"status": "ok"}

@app.delete("/cards/{card_id}")
async def delete_card(card_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(CardModel).filter(CardModel.id == card_id)
    result = await db.execute(stmt)
    card = result.scalars().first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    await db.delete(card)
    await db.commit()
    return {"status": "ok"}

@app.get("/cards/{language}")
async def get_cards(language: str, db: AsyncSession = Depends(get_db), levels: str = None, skip: int = 0, limit: int = 100):
    stmt = select(CardModel).filter(CardModel.language == language)
    if levels:
        level_list = levels.split(",")
        if "" in level_list:
            stmt = stmt.filter((CardModel.level.in_(level_list)) | (CardModel.level == None))
        else:
            stmt = stmt.filter(CardModel.level.in_(level_list))
    
    total_count = await db.execute(select(func.count(CardModel.id)).filter(CardModel.language == language))
    total = total_count.scalar()
    
    result = await db.execute(stmt.offset(skip).limit(limit))
    cards = result.scalars().all()
    
    mapper = {c.name: None for c in inspect(CardModel).columns}
    return {
        "cards": [
            {key: getattr(card, key) for key in mapper.keys()} 
            for card in cards
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }

@app.get("/levels/{language}")
async def get_levels(language: str, db: AsyncSession = Depends(get_db)):
    stmt = select(CardModel.level).filter(CardModel.language == language).distinct()
    result = await db.execute(stmt)
    levels = result.scalars().all()
    return {"levels": [l for l in levels if l]}

@app.post("/cards/review")
async def review_card(request: ProgressRequest, db: AsyncSession = Depends(get_db)):
    stmt = select(CardModel).filter(CardModel.id == request.card_id)
    result = await db.execute(stmt)
    card = result.scalars().first()
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
    await db.commit()
    return {"status": "ok"}

@app.post("/cards/next")
async def next_cards(request: dict, db: AsyncSession = Depends(get_db)):
    language = request.get("language")
    levels = request.get("levels", [])
    now = datetime.utcnow()
    stmt = select(CardModel).filter(CardModel.language == language)
    if levels: 
        if "" in levels or "None" in levels:
            stmt = stmt.filter((CardModel.level.in_(levels)) | (CardModel.level == None))
        else:
            stmt = stmt.filter(CardModel.level.in_(levels))
    overdue_stmt = stmt.filter(CardModel.next_review <= now).order_by(CardModel.next_review).limit(10)
    result = await db.execute(overdue_stmt)
    overdue = list(result.scalars().all())
    if len(overdue) < 10:
        new_stmt = stmt.filter(CardModel.repetition_count == 0).limit(10 - len(overdue))
        result = await db.execute(new_stmt)
        new_cards = result.scalars().all()
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
        voice_map = {"swedish": "sv_female.onnx", "finnish": "fi_female.onnx", "spanish": "es_mx_ximena.onnx"}
        if request.language in voice_map:
            v_path = os.path.join(VOICE_DIR, voice_map[request.language])
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                temp_wav = tmp.name
            try:
                env = os.environ.copy()
                env["LD_LIBRARY_PATH"] = f"{PIPER_LIB}:{env.get('LD_LIBRARY_PATH', '')}"
                proc = await asyncio.create_subprocess_exec(
                    PIPER_BIN, "--model", v_path, "--output_file", temp_wav,
                    stdin=asyncio.subprocess.PIPE, env=env
                )
                await proc.communicate(input=text.encode())
                async with aiofiles.open(temp_wav, "rb") as f: content = await f.read()
                return Response(content=content, media_type="audio/wav")
            finally:
                if os.path.exists(temp_wav):
                    os.unlink(temp_wav)
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))
    raise HTTPException(status_code=501)

@app.post("/evaluate_pronunciation")
async def evaluate_pronunciation(audio: UploadFile = File(...), language: str = Form(...), expected_text: str = Form(...)):
    transcript = "[Speech Recognition Failed]"
    feedback = "Ensure you emphasize the primary stress marks."
    similarity_score = 0
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
                similarity_score = fuzz.ratio(expected_text.lower().strip(), transcript.lower().strip())
                prompt = (
                    f"Language: {language}. Target text: '{expected_text}'. "
                    f"User said: '{transcript}'. Similarity: {similarity_score}/100. "
                    f"Provide one sentence of helpful, encouraging feedback."
                )
                try:
                    response_msg = await llm.ainvoke(prompt)
                    feedback = response_msg.content
                except (Exception,) as llm_error:
                    try:
                        feedback = await ollama_llm.ainvoke(prompt)
                    except (Exception,):
                        feedback = "Unable to generate feedback. Please try again."
                feedback = f"[{similarity_score:.0f}% Match] {feedback}"
        except Exception as e: feedback = f"Error: {e}"
    return {"transcript": transcript, "feedback": feedback, "score": similarity_score}

@app.post("/speak_ipa")
async def speak_ipa(request: SpeakRequest):
    def play_ipa():
        subprocess.run(["espeak-ng", "-v", "en-gb", "-s", "150", f"[[{request.text}]]"], check=False)
    threading.Thread(target=play_ipa, daemon=True).start()
    return {"status": "ok"}

@app.post("/migrate")
async def trigger_migrate():
    script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrate_to_sqlite.py")
    venv_python = os.path.join(os.path.dirname(__file__), "venv", "bin", "python3")
    try:
        proc = await asyncio.create_subprocess_exec(
            venv_python, script_path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0: return {"status": "ok", "output": stdout.decode()}
        else: return {"status": "error", "message": stderr.decode()}
    except Exception as e: return {"status": "error", "message": str(e)}

@app.post("/progress/reset")
async def reset_progress(request: dict, db: AsyncSession = Depends(get_db)):
    language = request.get("language")
    stmt = update(CardModel).filter(CardModel.language == language).values(
        passed=0, failed=0, repetition_count=0, interval=0, 
        ease_factor=2.5, next_review=datetime.utcnow()
    )
    await db.execute(stmt)
    await db.commit()
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

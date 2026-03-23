from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, model_validator
from langdetect import detect, LangDetectException
from sqlalchemy import Column, Integer, String, Float, DateTime, UniqueConstraint, Index, func, select, update, delete, cast
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
import hashlib
from datetime import datetime, timedelta
from synonyms import get_synonyms

# Database Setup
DB_PATH = "/home/chris/wordhord/wordhord.db"
engine = create_async_engine(
    f"sqlite+aiosqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False}
)

from sqlalchemy import event
from sqlalchemy.engine import Engine

@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

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
app.add_middleware(GZipMiddleware, minimum_size=1000)

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8000",
    "http://localhost:8001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8001",
]

if os.getenv("ENVIRONMENT") == "production":
    allowed = os.getenv("CORS_ORIGINS", "").split(",")
    ALLOWED_ORIGINS = [origin.strip() for origin in allowed if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# Configuration
def load_google_api_key() -> str:
    # Ensure Google Cloud Credentials are set for TTS
    creds_path = "/home/chris/panglossia/google-credentials.json"
    if os.path.exists(creds_path):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path
    
    key = os.getenv("GOOGLE_API_KEY")
    if key:
        return key
    try:
        api_key_file = os.getenv("API_KEY_FILE", "/home/chris/wordhord/wordhord_api.txt")
        with open(api_key_file, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        raise RuntimeError(
            "GOOGLE_API_KEY environment variable not set and API key file not found. "
            "Set GOOGLE_API_KEY environment variable or create the API key file."
        )

GOOGLE_API_KEY = load_google_api_key()

# Gemini 2.5 Flash
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=GOOGLE_API_KEY, temperature=0.1)
# Local Fallback
ollama_llm = OllamaLLM(model=os.getenv("OLLAMA_MODEL", "gemma2:9b"), temperature=0.1)

# TTS Paths
POLYGLOSSIA_DIR = "/home/chris/panglossia"
PIPER_BIN = os.path.join(POLYGLOSSIA_DIR, "backend", "bin", "piper")
PIPER_LIB = os.path.join(POLYGLOSSIA_DIR, "backend", "bin")
VOICE_DIR = os.path.join(POLYGLOSSIA_DIR, "backend", "voices")
CACHE_DIR = "/tmp/wordhord_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

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

    @model_validator(mode='after')
    def validate_card(self):
        target_lang = self.language.lower().strip() if self.language else ""
        term = self.term.strip() if self.term else ""
        translation = self.translation.strip() if self.translation else ""
        example = self.example.strip() if self.example else ""
        
        # 1. Reverse inverted entries (English word with foreign language definition)
        # We assume an entry is inverted if the target_lang is NOT English, but the term is detected as English
        # AND the translation contains foreign characters or doesn't look like English.
        # A simpler check based on user request: if they provide an English word in 'term' and definition in 'translation'
        if target_lang and target_lang != "english":
            try:
                if term:
                    # Very basic check: If the term is completely English and translation is not
                    term_lang = detect(term)
                    trans_lang = detect(translation) if translation else ""
                    if term_lang == 'en' and trans_lang != 'en' and trans_lang != '':
                        # Swap them
                        self.term, self.translation = self.translation, self.term
                        term = self.term.strip()
                        translation = self.translation.strip()
            except LangDetectException:
                pass
                
        # 2. Swedish validation
        if target_lang == "swedish":
            # Remove english words from the name of foreign words (term)
            # This is tricky without a dictionary, but we can remove text in brackets e.g. "word (english)"
            self.term = re.sub(r'\s*\([a-zA-Z\s]+\)', '', self.term).strip()
            term = self.term
            
            # Ensure verbs start with "att "
            pos = self.part_of_speech.lower().strip() if self.part_of_speech else ""
            if "verb" in pos and not term.startswith("att "):
                self.term = "att " + term
                term = self.term
                
            # Filter German origin words
            # (In a real app, this would use a lexicon, but here we can check for common German patterns or use a hardcoded list if provided)
            # For now, we will add a simple placeholder check. A real filter requires a DB or API.
            # Example: words ending in -ung, -heit, -keit are often German, but let's just do a basic check
            german_suffixes = ("ung", "heit", "keit", "schaft", "tion")
            if any(term.endswith(suf) for suf in german_suffixes):
                 raise ValueError(f"Term '{term}' appears to be of German origin and is excluded from Swedish.")

            # Validation for mandatory fields
            missing_fields = []
            if not self.ipa: missing_fields.append("ipa")
            if not self.tone or self.tone not in ["1", "2"]: missing_fields.append("tone (must be '1' or '2')")
            if not self.part_of_speech: missing_fields.append("part_of_speech")
            if not self.example: missing_fields.append("example (sample sentence)")
            if not self.example_translation: missing_fields.append("example_translation")
            
            if "noun" in pos and not self.gender: missing_fields.append("gender")
            if "verb" in pos and not self.conjugations: missing_fields.append("conjugations (verb_parts)")
            
            if missing_fields:
                raise ValueError(f"Swedish words require the following fields: {', '.join(missing_fields)}")

        # 3. Portuguese case normalization
        if target_lang == "portuguese":
            # Make lowercase unless proper noun. Proper nouns usually start with uppercase and aren't at the beginning of a sentence.
            # A simple heuristic: if it's strictly alphabetical and not identified as a proper noun in POS, lower it.
            pos = self.part_of_speech.lower().strip() if self.part_of_speech else ""
            if "proper" not in pos and "proper noun" not in pos:
                self.term = self.term.lower()

        if target_lang and target_lang != "english" and term:
            try:
                detected_lang = detect(term)
                suspicious_langs = ["en"] if target_lang == "german" else ["en", "de"]
                if detected_lang in suspicious_langs and not example:
                    raise ValueError(f"Suspected incorrect language insertion: Term '{term}' detected as '{detected_lang}', but missing sample sentence for target language '{target_lang}'.")
            except LangDetectException:
                pass
        return self

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
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        if "UNIQUE constraint failed" in str(e):
             raise HTTPException(status_code=400, detail="This term already exists for this language.")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
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

def expand_abbreviations(text: str, language: str) -> str:
    if not text: return ""
    
    # Common English expansions for translations
    eng_expansions = {
        r'\bsth\.?\b': 'something',
        r'\bsb\.?\b': 'someone',
        r'\bsomeb\.?\b': 'somebody',
        r'\bsomew\.?\b': 'somewhere',
    }
    
    # Language specific expansions for terms
    lang_expansions = {
        'german': {
            r'\betw\.?\b': 'etwas',
            r'\bjmd\.?\b': 'jemand',
            r'\bjmdn\.?\b': 'jemanden',
            r'\bjmdm\.?\b': 'jemandem',
            r'\bjmds\.?\b': 'jemandes',
        },
        'swedish': {
            r'\bngt\.?\b': 'något',
            r'\bngn\.?\b': 'någon',
        },
        'dutch': {
            r'\biem\.?\b': 'iemand',
        },
        'spanish': {
            r'\balg\.?\b': 'algo',
            r'\balgn\.?\b': 'alguien',
        }
    }

    # Expand English definitions
    for pattern, expansion in eng_expansions.items():
        text = re.sub(pattern, expansion, text, flags=re.IGNORECASE)
        
    # Expand native language terms
    if language in lang_expansions:
        for pattern, expansion in lang_expansions[language].items():
            text = re.sub(pattern, expansion, text, flags=re.IGNORECASE)
            
    return text

@app.get("/cards/{language}")
async def get_cards(language: str, db: AsyncSession = Depends(get_db), levels: str = None, skip: int = 0, limit: int = 100000):
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
    
    formatted_cards = []
    for card in cards:
        term = card.term.strip()
        translation = expand_abbreviations(card.translation or "", language)
        gender = (card.gender or "").lower()
        
        # Apply language-specific formatting
        if language == 'german':
            is_noun = (card.part_of_speech and 'noun' in card.part_of_speech.lower()) or \
                      (gender in ['masculine', 'feminine', 'neuter', 'der', 'die', 'das', 'm', 'f', 'n'])
            
            # Handle parentheses and articles
            if is_noun:
                # Handle 'der/die ' prefix specifically
                if term.lower().startswith('der/die '):
                    # Capitalize the word following der/die
                    term = re.sub(r'^(der/die\s+)(\(?\w)', lambda m: m.group(1) + m.group(2).upper(), term, flags=re.IGNORECASE)
                else:
                    # Remove any existing single article to re-add it consistently
                    term = re.sub(r'^(der|die|das)\s+', '', term, flags=re.IGNORECASE).strip()
                    
                    g_map = {'masculine': 'der', 'feminine': 'die', 'neuter': 'das', 'der': 'der', 'die': 'die', 'das': 'das', 'm': 'der', 'f': 'die', 'n': 'das'}
                    art = g_map.get(gender, "")
                    
                    # Expand abbreviations in the term itself
                    term = expand_abbreviations(term, language)
                    
                    # Capitalize first word char (handles (prefix)Noun -> (Prefix)noun)
                    term = re.sub(r'(\w+)', lambda m: m.group(1).capitalize(), term, count=1)
                    
                    if art:
                        term = f"{art} {term}"
            else:
                # For non-nouns, lowercase unless it's a proper noun
                term = expand_abbreviations(term.lower(), language)

        elif language == 'dutch':
            term = expand_abbreviations(term.lower(), language)
            if 'de' in gender or 'maskulin' in gender or 'feminin' in gender:
                if not term.startswith('de '):
                    term = f"de {term}"
            elif 'het' in gender or 'neuter' in gender or 'onzijdig' in gender:
                if not term.startswith('het '):
                    term = f"het {term}"
                
        elif language == 'spanish':
            # Preserve database capitalization as requested (don't force .lower())
            term = expand_abbreviations(term, language)
            if 'maskulin' in gender or 'masculine' in gender or 'el' in gender:
                if not term.lower().startswith('el '):
                    term = f"el {term}"
            elif 'feminin' in gender or 'feminine' in gender or 'la' in gender:
                if not term.lower().startswith('la '):
                    term = f"la {term}"
                
        elif language == 'portuguese':
            # Preserve database capitalization as requested
            term = expand_abbreviations(term, language)
            if 'maskulin' in gender or 'masculine' in gender or ' o ' in f" {gender} " or gender == 'o':
                if not term.lower().startswith('o '):
                    term = f"o {term}"
            elif 'feminin' in gender or 'feminine' in gender or ' a ' in f" {gender} " or gender == 'a':
                if not term.lower().startswith('a '):
                    term = f"a {term}"
        
        elif language == 'swedish':
            term = expand_abbreviations(term.lower(), language)
            
        elif language == 'finnish':
            term = expand_abbreviations(term.lower(), language)

        # Global Rule: Ensure balanced parentheses
        def balance_parens(text: str) -> str:
            if not text: return ""
            open_count = text.count('(')
            close_count = text.count(')')
            if open_count > close_count:
                text += ')' * (open_count - close_count)
            return text

        term = balance_parens(term)
        translation = balance_parens(translation)
            
        card_dict = {c.name: getattr(card, c.name) for c in inspect(CardModel).columns}
        card_dict['term'] = term
        card_dict['translation'] = translation
        formatted_cards.append(card_dict)

    return {
        "cards": formatted_cards,
        "total": total,
        "skip": skip,
        "limit": limit
    }

@app.get("/count/{language}")
async def get_count(language: str, db: AsyncSession = Depends(get_db)):
    stmt = select(func.count(CardModel.id)).filter(CardModel.language == language)
    result = await db.execute(stmt)
    total = result.scalar()
    return {"total": total}

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
            
    # Weighted Learning Algorithm: Prioritize cards that have a high failure rate.
    # Weight = failed / (passed + 1) -> highest ratio goes first.
    weight_expression = cast(CardModel.failed, Float) / (cast(CardModel.passed, Float) + 1.0)
    
    overdue_stmt = stmt.filter(CardModel.next_review <= now).order_by(
        weight_expression.desc(),
        CardModel.next_review
    ).limit(10)
    
    result = await db.execute(overdue_stmt)
    overdue = list(result.scalars().all())
    
    if len(overdue) < 10:
        # Also randomize new vocabulary acquisition for better learning variance
        import random
        count_stmt = select(func.count(CardModel.id)).filter(CardModel.language == language, CardModel.repetition_count == 0)
        if levels:
            if "" in levels or "None" in levels:
                count_stmt = count_stmt.filter((CardModel.level.in_(levels)) | (CardModel.level == None))
            else:
                count_stmt = count_stmt.filter(CardModel.level.in_(levels))
        count_result = await db.execute(count_stmt)
        num_new = count_result.scalar()
        
        if num_new > 0:
            needed = 10 - len(overdue)
            offset = random.randint(0, max(0, num_new - needed))
            new_stmt = stmt.filter(CardModel.repetition_count == 0).offset(offset).limit(needed)
            result = await db.execute(new_stmt)
            new_cards = result.scalars().all()
            overdue.extend(new_cards)
        
    return {"ids": [str(c.id) for c in overdue]}

@app.post("/native_audio")
async def get_native_audio(request: SpeakRequest):
    text = request.text.strip()
    if not text: raise HTTPException(status_code=400)
    
    # Include speed in hash to cache different speeds
    text_hash = hashlib.md5(f"{text}_{request.language}_{request.speed}".encode()).hexdigest()
    cache_path = os.path.join(CACHE_DIR, f"{text_hash}.mp3")

    if os.path.exists(cache_path):
        async with aiofiles.open(cache_path, "rb") as f:
            content = await f.read()
            return Response(content=content, media_type="audio/mpeg")

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
                "dutch": ("nl-NL", "nl-NL-Chirp3-HD-Despina"),
                "scottish gaelic": ("en-GB", "en-GB-Standard-A")
            }
            l_code, v_name = gtts_voice_map.get(request.language, ("en-US", "en-US-Journey-F"))
            print(f"DEBUG: Using voice {v_name} for {request.language}", flush=True)
            voice = texttospeech.VoiceSelectionParams(language_code=l_code, name=v_name)
            
            # Use SSML for Gaelic or if IPA characters detected
            is_ipa = bool(re.search(r'[ɑʋɛɪɔʊæøœʉɟʝɲŋʃʒθðɬɮɹɻɥɰʁˈˌ]', text))
            if request.language == "scottish gaelic" or is_ipa:
                clean_ipa = text.strip('[]').replace('"', '&quot;')
                synthesis_input = texttospeech.SynthesisInput(
                    ssml=f'<speak><phoneme alphabet="ipa" ph="{clean_ipa}">{clean_ipa}</phoneme></speak>'
                )
            else:
                synthesis_input = texttospeech.SynthesisInput(text=text)

            # Fix: Use MP3 encoding to avoid noise issues common with LINEAR16 if headers are mismatched
            # Support variable speaking_rate
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3, 
                speaking_rate=request.speed
            )
            
            response = await asyncio.to_thread(client.synthesize_speech, input=synthesis_input, voice=voice, audio_config=audio_config)
            
            # Save to cache
            async with aiofiles.open(cache_path, "wb") as f:
                await f.write(response.audio_content)
                
            return Response(content=response.audio_content, media_type="audio/mpeg")
        
        # Local fallback using Piper
        voice_map = {"swedish": "sv_female.onnx", "finnish": "fi_female.onnx", "spanish": "es_mx_ximena.onnx"}
        if request.language in voice_map:
            v_path = os.path.join(VOICE_DIR, voice_map[request.language])
            try:
                # Piper generates WAV, we might need to convert or just serve as WAV
                local_cache_path = os.path.join(CACHE_DIR, f"{text_hash}.wav")
                env = os.environ.copy()
                env["LD_LIBRARY_PATH"] = f"{PIPER_LIB}:{env.get('LD_LIBRARY_PATH', '')}"
                # Piper doesn't directly support speed, we'd need ffmpeg or similar if really needed
                proc = await asyncio.create_subprocess_exec(
                    PIPER_BIN, "--model", v_path, "--output_file", local_cache_path,
                    stdin=asyncio.subprocess.PIPE, env=env
                )
                await proc.communicate(input=text.encode())
                
                if os.path.exists(local_cache_path):
                    async with aiofiles.open(local_cache_path, "rb") as f: 
                        content = await f.read()
                        return Response(content=content, media_type="audio/wav")
            except Exception as e:
                print(f"Local TTS error: {e}")
    except Exception as e:
        print(f"DEBUG: get_native_audio error: {e}", flush=True)
        raise HTTPException(status_code=500, detail=str(e))
    
    print(f"DEBUG: No audio available for {request.language}", flush=True)
    raise HTTPException(status_code=404, detail="No voice available for this language")

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
            # Run the synchronous Google Cloud SDK call in a separate thread
            response = await asyncio.to_thread(client.recognize, config=config, audio=speech.RecognitionAudio(content=content))
            if response.results:
                transcript = response.results[0].alternatives[0].transcript
                similarity_score = fuzz.ratio(expected_text.lower().strip(), transcript.lower().strip())
                prompt = (
                    f"Language: {language}. Target text: '{expected_text}'. "
                    f"User said: '{transcript}'. Similarity: {similarity_score}/100. "
                    f"Provide one sentence of helpful, encouraging feedback."
                )
                try:
                    for attempt in range(5):
                        try:
                            response_msg = await llm.ainvoke(prompt)
                            feedback = response_msg.content
                            break
                        except Exception as e:
                            if attempt < 4:
                                import random
                                await asyncio.sleep(2 * (2 ** attempt) + random.uniform(0, 1))
                            else:
                                raise e
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
    if not isinstance(request.text, str) or not request.text.strip():
        raise HTTPException(status_code=400, detail="Invalid IPA text")
    
    clean_ipa = request.text.strip().strip('[]').replace('"', '&quot;')
    
    # Try Google TTS SSML first to match standard playback voices
    try:
        if texttospeech and os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            client = texttospeech.TextToSpeechClient()
            gtts_voice_map = {
                "swedish": ("sv-SE", "sv-SE-Chirp3-HD-Laomedeia"),
                "german": ("de-DE", "de-DE-Chirp3-HD-Leda"),
                "finnish": ("fi-FI", "fi-FI-Chirp3-HD-Despina"),
                "portuguese": ("pt-BR", "pt-BR-Chirp3-HD-Dione"),
                "spanish": ("es-US", "es-US-Chirp3-HD-Callirrhoe"),
                "dutch": ("nl-NL", "nl-NL-Chirp3-HD-Despina"),
                "scottish gaelic": ("en-GB", "en-GB-Standard-A")
            }
            l_code, v_name = gtts_voice_map.get(request.language.lower(), ("en-US", "en-US-Journey-F"))
            voice = texttospeech.VoiceSelectionParams(language_code=l_code, name=v_name)
            
            synthesis_input = texttospeech.SynthesisInput(
                ssml=f'<speak><phoneme alphabet="ipa" ph="{clean_ipa}">{clean_ipa}</phoneme></speak>'
            )
            
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3, 
                speaking_rate=request.speed
            )
            
            response = await asyncio.to_thread(client.synthesize_speech, input=synthesis_input, voice=voice, audio_config=audio_config)
            return Response(content=response.audio_content, media_type="audio/mpeg")
    except Exception as e:
        print(f"DEBUG: Google TTS failed for IPA, falling back to espeak-ng: {e}", flush=True)

    # Fallback to espeak-ng
    sanitized = re.sub(r'[^\w\s\.\,ˈˌːˑ˘\.◌\u0250-\u02AF\u1D00-\u1D7F\u1D80-\u1DBF]', '', clean_ipa)
    ipa_input = f"[[{sanitized}]]"
    
    # Map app language to espeak-ng voice codes
    voice_map = {
        "english": "en-gb",
        "german": "de",
        "dutch": "nl",
        "spanish": "es",
        "portuguese": "pt",
        "finnish": "fi",
        "swedish": "sv",
        "scottish gaelic": "gd"
    }
    voice = voice_map.get(request.language.lower(), "en-gb")
    
    # Scale base speed (150) by request.speed
    espeak_speed = str(int(150 * request.speed))
    
    try:
        # Generate audio using espeak-ng and capture stdout
        result = subprocess.run(
            ["espeak-ng", "-v", voice, "-s", espeak_speed, "--stdout", ipa_input],
            capture_output=True,
            check=True,
            timeout=5
        )
        return Response(content=result.stdout, media_type="audio/wav")
    except Exception as e:
        print(f"Speak IPA error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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

@app.get("/synonyms/{word}")
async def fetch_synonyms(word: str, lang: str = "en", source: str = "dm"):
    try:
        syns = get_synonyms(word, lang, source)
        return {"synonyms": syns}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

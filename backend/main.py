from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import declarative_base, sessionmaker
import os
import subprocess
import json
import re
import threading
import tempfile
from langchain_ollama import OllamaLLM

# Database Setup
DB_PATH = "/home/chris/wordhord.db"
engine = create_engine(f"sqlite:///{DB_PATH}")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class CardModel(Base):
    __tablename__ = "cards"
    id = Column(Integer, primary_key=True, index=True)
    language = Column(String)
    term = Column(String)
    translation = Column(String)
    ipa = Column(String)
    gender = Column(String)
    part_of_speech = Column(String)
    tone = Column(String)
    prefix = Column(String)
    preposition = Column(String)
    case = Column(String)
    conjugations = Column(String)
    example = Column(String)
    example_translation = Column(String)
    passed = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    __table_args__ = (UniqueConstraint('language', 'term', name='_language_term_uc'),)

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
MODEL_NAME = os.getenv("OLLAMA_MODEL", "gemma2:9b")
llm = OllamaLLM(model=MODEL_NAME, temperature=0.1)

POLYGLOSSIA_DIR = "/home/chris/polyglossia"
PIPER_BIN = os.path.join(POLYGLOSSIA_DIR, "backend", "bin", "piper")
PIPER_LIB = os.path.join(POLYGLOSSIA_DIR, "backend", "bin")
VOICE_DIR = os.path.join(POLYGLOSSIA_DIR, "backend", "voices")

try:
    from google.cloud import texttospeech
    from google.cloud import speech
except ImportError:
    texttospeech = None
    speech = None

class GenerateRequest(BaseModel):
    language: str
    existing_terms: list[str]

class SpeakRequest(BaseModel):
    text: str
    language: str

class NextCardsRequest(BaseModel):
    language: str
    cards: list[dict]

class CardCreateRequest(BaseModel):
    language: str
    term: str
    translation: str
    ipa: str = ""
    gender: str = ""
    part_of_speech: str = ""
    tone: str = ""
    prefix: str = ""
    preposition: str = ""
    case: str = ""
    conjugations: str = ""
    example: str = ""
    example_translation: str = ""

@app.get("/cards/{language}")
async def get_cards(language: str):
    db = SessionLocal()
    cards = db.query(CardModel).filter(CardModel.language == language).all()
    db.close()
    return {"cards": [c.__dict__ for c in cards]}

def enrich_cards_background(language, cards_data):
    db = SessionLocal()
    for card_data in cards_data:
        term = card_data.get('term')
        # Check if we already have it with full data
        existing = db.query(CardModel).filter_by(language=language, term=term).first()
        if existing and existing.ipa:
            continue
            
        prompt = f"""
Provide linguistic details for the {language} word: "{term}".
Fill in missing info if not provided:
- translation: {card_data.get('translation', '')}
- ipa: (MANDATORY: with primary stress 'ˈ')
- part_of_speech:
- gender:
- tone: (Swedish only)
- prefix: (German/Swedish verbs)
- preposition:
- case:
- conjugations:
- example:
- example_translation:

Output ONLY JSON.
"""
        try:
            resp = llm.invoke(prompt)
            match = re.search(r'\{.*\}', resp, re.DOTALL)
            if match:
                details = json.loads(match.group(0))
                if existing:
                    for key, val in details.items():
                        if hasattr(existing, key) and val:
                            setattr(existing, key, val)
                else:
                    new_card = CardModel(language=language, **details)
                    db.add(new_card)
                db.commit()
        except Exception as e:
            print(f"Background enrichment error for {term}: {e}")
            db.rollback()
    db.close()

@app.post("/cards/generate")
async def generate_related(request: GenerateRequest):
    prompt = f"""
Generate 5 unique and common {request.language} vocabulary words or expressions at A1-B2 level.
Exclude these: {', '.join(request.existing_terms[-20:])}.

REQUIREMENTS for each entry:
- term: the word/phrase.
- translation: English translation.
- ipa: IPA pronunciation. MANDATORY: Include the 'ˈ' mark for primary stress.
- part_of_speech: Noun, Verb, Adjective, etc.
- gender: if applicable.
- tone: For Swedish ONLY, include Accent 1 or Accent 2.
- prefix: For German/Swedish verbs, explicitly state if a prefix is 'Separable' or 'Inseparable'.
- preposition: For verbs, common associated preposition.
- case: The grammatical case governed by the verb/preposition.
- conjugations: Main forms. 
- example: A simple example sentence. 
- example_translation: English translation.

Output ONLY a JSON array of objects. No other text.
"""
    try:
        response = llm.invoke(prompt)
        json_match = re.search(r'\[.*\]', response, re.DOTALL)
        if json_match:
            cards = json.loads(json_match.group(0))
            # Save to DB
            db = SessionLocal()
            for c in cards:
                db_card = CardModel(language=request.language, **c)
                db.merge(db_card)
            db.commit()
            db.close()
            return {"cards": cards}
        return {"cards": []}
    except Exception as e:
        return {"cards": []}

@app.post("/cards/create")
async def create_card(request: CardCreateRequest):
    db = SessionLocal()
    db_card = CardModel(**request.dict())
    try:
        db.add(db_card)
        db.commit()
        return {"status": "created"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()

@app.post("/cards/update")
async def update_card(request: CardCreateRequest):
    db = SessionLocal()
    card = db.query(CardModel).filter_by(language=request.language, term=request.term).first()
    if not card:
        db.close()
        raise HTTPException(status_code=404, detail="Card not found")
    
    for key, value in request.dict().items():
        setattr(card, key, value)
    
    try:
        db.commit()
        return {"status": "updated"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()

@app.delete("/cards/{language}/{term}")
async def delete_card(language: str, term: str):
    db = SessionLocal()
    card = db.query(CardModel).filter(CardModel.language == language, CardModel.term == term).first()
    if card:
        db.delete(card)
        db.commit()
        db.close()
        return {"status": "deleted"}
    db.close()
    raise HTTPException(status_code=404, detail="Card not found")

@app.post("/cards/next")
async def next_cards(request: NextCardsRequest):
    # Basic spaced repetition: 
    # Prioritize cards with more fails or fewer passes
    db = SessionLocal()
    # Update stats first
    for c in request.cards:
        db_card = db.query(CardModel).filter_by(id=c.get('id')).first()
        if db_card:
            db_card.passed = c.get('passed', db_card.passed)
            db_card.failed = c.get('failed', db_card.failed)
    db.commit()
    
    # Select next batch (e.g., 10 cards)
    # Strategy: 5 failed/new, 5 regular
    all_cards = db.query(CardModel).filter(CardModel.language == request.language).all()
    db.close()
    
    # Sort by "need to study": failed / (passed + 1)
    sorted_cards = sorted(all_cards, key=lambda x: x.failed / (x.passed + 1), reverse=True)
    next_ids = [str(c.id) for c in sorted_cards[:10]]
    
    return {"ids": next_ids}

@app.post("/evaluate_pronunciation")
async def evaluate_pronunciation(audio: UploadFile = File(...), language: str = Form(...), expected_text: str = Form(...)):
    # Local fallback for STT evaluation
    # Since we don't have a reliable local STT right now, we use a mock/LLM based feedback
    # if speech is available, we could use Google Cloud Speech
    
    transcript = "[Speech Recognition Mocked]"
    feedback = "Keep practicing! Ensure you emphasize the stressed syllables."
    
    if speech and os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        try:
            client = speech.SpeechClient()
            content = await audio.read()
            audio_obj = speech.RecognitionAudio(content=content)
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
                sample_rate_hertz=48000,
                language_code="sv-SE" if language == "swedish" else "en-US", # simplistic map
            )
            response = client.recognize(config=config, audio=audio_obj)
            if response.results:
                transcript = response.results[0].alternatives[0].transcript
                # Use LLM to compare transcript with expected_text
                prompt = f"""
Compare the speaker's transcript: "{transcript}"
With the expected text: "{expected_text}"
In {language}.
Provide brief feedback on pronunciation and accuracy.
"""
                feedback = llm.invoke(prompt)
        except Exception as e:
            feedback = f"Evaluation error: {e}"

    return {"transcript": transcript, "feedback": feedback}

@app.post("/speak")
async def speak(request: SpeakRequest):
    text_to_speak = request.text.strip()
    if not text_to_speak: return {"status": "ok"}

    def play_audio():
        try:
            if texttospeech and os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
                client = texttospeech.TextToSpeechClient()
                synthesis_input = texttospeech.SynthesisInput(text=text_to_speak)
                gtts_voice_map = {
                    "swedish": ("sv-SE", "sv-SE-Chirp3-HD-Laomedeia"),
                    "german": ("de-DE", "de-DE-Chirp3-HD-Leda"),
                    "finnish": ("fi-FI", "fi-FI-Chirp3-HD-Despina"),
                    "portuguese": ("pt-BR", "pt-BR-Chirp3-HD-Dione"),
                    "spanish": ("es-US", "es-US-Chirp3-HD-Callirrhoe"),
                    "dutch": ("nl-NL", "nl-NL-Chirp3-HD-Despina"),
                    "scottish_gaelic": ("en-GB", "en-GB-Wavenet-B")
                }
                l_code, v_name = gtts_voice_map.get(request.language, ("en-US", "en-US-Journey-F"))
                voice = texttospeech.VoiceSelectionParams(language_code=l_code, name=v_name)
                audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16, speaking_rate=0.95)
                response = client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
                
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp.write(response.audio_content)
                    temp_wav = tmp.name
                
                subprocess.run(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", temp_wav], check=False)
                os.unlink(temp_wav)
                return

            # Fallback to local Piper
            voice_map = {"swedish": "sv_female.onnx", "finnish": "fi_female.onnx", "spanish": "es_mx_ximena.onnx"}
            if request.language in voice_map:
                v_path = os.path.join(VOICE_DIR, voice_map[request.language])
                if os.path.exists(v_path):
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                        temp_wav = tmp.name
                    env = os.environ.copy()
                    env["LD_LIBRARY_PATH"] = f"{PIPER_LIB}:{env.get('LD_LIBRARY_PATH', '')}"
                    cmd = [PIPER_BIN, "--model", v_path, "--output_file", temp_wav]
                    subprocess.run(cmd, input=text_to_speak, text=True, env=env, check=False)
                    subprocess.run(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", temp_wav], check=False)
                    os.unlink(temp_wav)
        except Exception as e:
            print(f"DEBUG Error: {e}")

    threading.Thread(target=play_audio, daemon=True).start()
    return {"status": "ok"}

@app.post("/native_audio")
async def get_native_audio(request: SpeakRequest):
    text_to_speak = request.text.strip()
    if not text_to_speak:
        raise HTTPException(status_code=400, detail="Text is empty")

    try:
        if texttospeech and os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            client = texttospeech.TextToSpeechClient()
            synthesis_input = texttospeech.SynthesisInput(text=text_to_speak)
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
            
            from fastapi.responses import Response
            return Response(content=response.audio_content, media_type="audio/wav")

        # Fallback to local Piper
        voice_map = {"swedish": "sv_female.onnx", "finnish": "fi_female.onnx", "spanish": "es_mx_ximena.onnx"}
        if request.language in voice_map:
            v_path = os.path.join(VOICE_DIR, voice_map[request.language])
            if os.path.exists(v_path):
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    temp_wav = tmp.name
                env = os.environ.copy()
                env["LD_LIBRARY_PATH"] = f"{PIPER_LIB}:{env.get('LD_LIBRARY_PATH', '')}"
                cmd = [PIPER_BIN, "--model", v_path, "--output_file", temp_wav]
                subprocess.run(cmd, input=text_to_speak, text=True, env=env, check=False)
                
                with open(temp_wav, "rb") as f:
                    content = f.read()
                os.unlink(temp_wav)
                from fastapi.responses import Response
                return Response(content=content, media_type="audio/wav")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    raise HTTPException(status_code=501, detail="TTS not configured")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

import sqlite3
import os
import re
import json
import time
from sqlalchemy import create_engine, Column, Integer, String, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker
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

# Configuration
MODEL_NAME = os.getenv("OLLAMA_MODEL", "gemma2:9b")
llm = OllamaLLM(model=MODEL_NAME, temperature=0.2)
LANGUAGES = ['dutch', 'finnish', 'german', 'portuguese', 'spanish', 'swedish', 'scottish_gaelic']
BATCH_SIZE = 10 
TOTAL_TARGET = 3000
THERMAL_DELAY = 15 

def get_existing_count(db, language):
    return db.query(CardModel).filter(CardModel.language == language).count()

def get_recent_terms(db, language):
    # Get 100 recent terms to avoid repeats in generation
    cards = db.query(CardModel).filter(CardModel.language == language).order_by(CardModel.id.desc()).limit(100).all()
    return [c.term for c in cards]

def generate_batch(language, recent_terms, level="A1-B2"):
    prompt = f"""
Generate {BATCH_SIZE} unique and common {language} vocabulary words or expressions at {level} level.
Exclude these: {', '.join(recent_terms)}.

REQUIREMENTS for each entry:
- term: the {language} word.
- translation: English translation.
- ipa: IPA pronunciation. MANDATORY: Include the 'ˈ' mark for primary stress.
- part_of_speech: Noun, Verb, Adjective, etc.
- gender: if applicable.
- tone: For Swedish ONLY, include Accent 1 or Accent 2.
- prefix: For German/Swedish verbs, explicitly state if a prefix is 'Separable' or 'Inseparable'.
- preposition: For verbs, common associated preposition.
- case: The grammatical case governed by the verb or preposition.
- conjugations: Main forms. 
- example: A simple example sentence. 
- example_translation: English translation.

Output ONLY a JSON array of objects. No other text.
"""
    try:
        response = llm.invoke(prompt)
        json_match = re.search(r'\[.*\]', response, re.DOTALL)
        if json_match: return json.loads(json_match.group(0))
    except Exception as e:
        print(f"Error: {e}")
    return []

def clean_value(val):
    if isinstance(val, list):
        return ", ".join(map(str, val))
    if val is None:
        return ""
    return str(val)

def save_to_db(db, language, cards):
    for entry in cards:
        term = clean_value(entry.get('term'))
        if not term: continue
        
        # Check if exists to avoid unique constraint failure
        existing_card = db.query(CardModel).filter_by(language=language, term=term).first()
        
        if existing_card:
            # Update existing with new AI data
            existing_card.translation = clean_value(entry.get('translation', existing_card.translation))
            existing_card.ipa = clean_value(entry.get('ipa', existing_card.ipa))
            existing_card.gender = clean_value(entry.get('gender', existing_card.gender))
            existing_card.part_of_speech = clean_value(entry.get('part_of_speech', existing_card.part_of_speech))
            existing_card.tone = clean_value(entry.get('tone', existing_card.tone))
            existing_card.prefix = clean_value(entry.get('prefix', existing_card.prefix))
            existing_card.preposition = clean_value(entry.get('preposition', existing_card.preposition))
            existing_card.case = clean_value(entry.get('case', existing_card.case))
            existing_card.conjugations = clean_value(entry.get('conjugations', existing_card.conjugations))
            existing_card.example = clean_value(entry.get('example', existing_card.example))
            existing_card.example_translation = clean_value(entry.get('example_translation', existing_card.example_translation))
        else:
            # Create new
            new_card = CardModel(
                language=language,
                term=term,
                translation=clean_value(entry.get('translation')),
                ipa=clean_value(entry.get('ipa', '')),
                gender=clean_value(entry.get('gender', '')),
                part_of_speech=clean_value(entry.get('part_of_speech', '')),
                tone=clean_value(entry.get('tone', '')),
                prefix=clean_value(entry.get('prefix', '')),
                preposition=clean_value(entry.get('preposition', '')),
                case=clean_value(entry.get('case', '')),
                conjugations=clean_value(entry.get('conjugations', '')),
                example=clean_value(entry.get('example', '')),
                example_translation=clean_value(entry.get('example_translation', ''))
            )
            db.add(new_card)
        
        try:
            db.commit()
        except Exception as e:
            print(f"Error saving {term}: {e}")
            db.rollback()

def main():
    db = SessionLocal()
    for lang in LANGUAGES:
        print(f"--- {lang.upper()} ---")
        count = get_existing_count(db, lang)
        while count < TOTAL_TARGET:
            recent = get_recent_terms(db, lang)
            print(f"Batch ({count}/{TOTAL_TARGET})...")
            cards = generate_batch(lang, recent)
            if not cards:
                time.sleep(5); continue
            save_to_db(db, lang, cards)
            count = get_existing_count(db, lang)
            print(f"Cooling down for {THERMAL_DELAY}s...")
            time.sleep(THERMAL_DELAY)
    db.close()

if __name__ == "__main__":
    main()

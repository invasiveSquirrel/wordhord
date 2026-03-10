import sqlite3
import os
import re
import json
import time
import random
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
    plural = Column(String)
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
llm = OllamaLLM(model=MODEL_NAME, temperature=0.7)
LANGUAGES = ['dutch', 'finnish', 'german', 'portuguese', 'spanish', 'swedish']
BATCH_SIZE = 10 
TOTAL_TARGET = 3000
THERMAL_DELAY = 15 
LEVELS = ["A1", "A2", "B1", "B2"]

def get_existing_count(db, language):
    return db.query(CardModel).filter(CardModel.language == language).count()
def get_all_terms(db, language):
    # Get all terms to avoid any repeats in generation
    cards = db.query(CardModel).filter(CardModel.language == language).all()
    return [c.term for c in cards]

def generate_batch(language, existing_terms, level="A1-B2"):
    # Limit to 100 random existing terms to avoid prompt bloat while maintaining variety
    random_samples = random.sample(existing_terms, min(len(existing_terms), 100))
    prompt = f"""
Generate {BATCH_SIZE} unique and common {language} vocabulary words or expressions at {level} level.
CRITICAL: Do NOT generate any of these terms: {', '.join(random_samples)}.
Choose new, interesting words that aren't in that list.

REQUIREMENTS for each entry:
- term: the {language} word.
- translation: English translation.
- ipa: IPA pronunciation. MANDATORY: Include the 'ˈ' mark for primary stress.
- part_of_speech: Noun, Verb, Adjective, etc.
- gender: (Only for nouns)
- plural: (For nouns)
- tone: For Swedish ONLY, include Accent 1 or Accent 2.
- prefix: For German/Dutch/Swedish verbs, explicitly state if a prefix is 'Separable' or 'Inseparable'.
- preposition: (If the verb is commonly used with one)
- case: (The grammatical case governed by the verb/preposition)
- conjugations: Main forms. 
- example: A simple example sentence. 
- example_translation: English translation.

Output ONLY a JSON array of objects. No other text.
"""
    try:
        response = llm.invoke(prompt)
        print(f"DEBUG: LLM Response (first 100 chars): {response[:100]}...")
        json_match = re.search(r'\[.*\]', response, re.DOTALL)
        if json_match: return json.loads(json_match.group(0))
        else:
            print("DEBUG: No JSON array found in LLM response.")
    except Exception as e:
        print(f"Error: {e}")
    return []

def clean_value(val):
    if isinstance(val, list):
        return ", ".join(map(str, val))
    if val is None:
        return ""
    s = str(val).strip()
    if s.lower() in ["none", "null", "undefined", "n/a"]:
        return ""
    return s

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
            existing_card.plural = clean_value(entry.get('plural', existing_card.plural))
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
                plural=clean_value(entry.get('plural', '')),
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
            all_existing = get_all_terms(db, lang)
            level = random.choice(LEVELS)
            print(f"Batch ({count}/{TOTAL_TARGET}) - Level {level}...")
            cards = generate_batch(lang, all_existing, level=level)
            print(f"DEBUG: LLM returned {len(cards)} cards")
            if not cards:
                time.sleep(5); continue
            save_to_db(db, lang, cards)
            new_count = get_existing_count(db, lang)
            if new_count == count:
                print(f"DEBUG: No new cards added (maybe duplicates).")
                # Wait longer if we are hitting repeats to let LLM "think" differently
                time.sleep(10)
            count = new_count
            print(f"Cooling down for {THERMAL_DELAY}s...")
            time.sleep(THERMAL_DELAY)
    db.close()

if __name__ == "__main__":
    main()

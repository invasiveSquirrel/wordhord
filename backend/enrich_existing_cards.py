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

# Configuration
MODEL_NAME = os.getenv("OLLAMA_MODEL", "gemma2:9b")
llm = OllamaLLM(model=MODEL_NAME, temperature=0.1)

def clean_value(val):
    if isinstance(val, list):
        return ", ".join(map(str, val))
    if val is None:
        return ""
    s = str(val).strip()
    if s.lower() in ["none", "null", "undefined", "n/a"]:
        return ""
    return s

import subprocess

def get_cpu_temp():
    try:
        # Use sensors to get Package id 0 temperature
        output = subprocess.check_output(["sensors"], text=True)
        for line in output.split("\n"):
            if "Package id 0" in line:
                temp_str = line.split("+")[1].split("°C")[0]
                return float(temp_str)
    except:
        return 50.0 # Fallback
    return 50.0

def thermal_throttle():
    temp = get_cpu_temp()
    if temp > 85.0:
        print(f"🔥 CPU Overheat ({temp}°C)! Cooling down for 60s...")
        time.sleep(60)
    elif temp > 75.0:
        print(f"🌡️ CPU High ({temp}°C). Throttling for 15s...")
        time.sleep(15)
    elif temp > 65.0:
        time.sleep(5)
    else:
        time.sleep(1)

def enrich_existing():
    db = SessionLocal()
    # Enrich ALL cards to ensure 27b-level quality on IPA stress and plurals
    cards = db.query(CardModel).all()
    
    print(f"Found {len(cards)} cards to verify and enrich with gemma2:27b.")
    
    for i, card in enumerate(cards):
        thermal_throttle()
        print(f"[{i+1}/{len(cards)}] Verifying {card.language}: {card.term}...")
        
        prompt = f"""
Provide precise linguistic details for the {card.language} word: "{card.term}".
CRITICAL: Ensure the IPA pronunciation includes the primary stress mark 'ˈ' before the stressed syllable.

Fill in the following fields:
- translation: {card.translation}
- ipa: (MANDATORY: Use standard IPA. Include primary stress 'ˈ')
- part_of_speech: {card.part_of_speech}
- gender: (Nouns only: Masculine, Feminine, Neuter, or Common)
- plural: (Nouns only: Provide the full plural form)
- tone: (Swedish ONLY: Accent 1 or Accent 2)
- prefix: (German/Dutch/Swedish verbs ONLY: 'Separable' or 'Inseparable')
- preposition: (If the verb is commonly used with one)
- case: (The grammatical case governed by the preposition or verb)
- conjugations: (Main verb forms)
- example: {card.example}
- example_translation: {card.example_translation}

Output ONLY a JSON object.
"""
        try:
            resp = llm.invoke(prompt)
            match = re.search(r'\{.*\}', resp, re.DOTALL)
            if match:
                details = json.loads(match.group(0))
                card.ipa = clean_value(details.get('ipa', card.ipa))
                card.gender = clean_value(details.get('gender', card.gender))
                card.plural = clean_value(details.get('plural', card.plural))
                card.tone = clean_value(details.get('tone', card.tone))
                card.prefix = clean_value(details.get('prefix', card.prefix))
                card.preposition = clean_value(details.get('preposition', card.preposition))
                card.case = clean_value(details.get('case', card.case))
                card.conjugations = clean_value(details.get('conjugations', card.conjugations))
                
                # If gender was provided but it's not a noun, clear it (as per user request)
                if card.part_of_speech and 'noun' not in card.part_of_speech.lower():
                    card.gender = ""

                db.commit()
                print(f"  ✓ Updated.")
            else:
                print(f"  ⚠ No JSON found.")
        except Exception as e:
            print(f"  ❌ Error: {e}")
            db.rollback()
        
        # Small sleep to be nice to the LLM/System
        time.sleep(1)

    db.close()

if __name__ == "__main__":
    print("ENRICHMENT SCRIPT STARTING...")
    enrich_existing()

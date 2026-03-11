import sqlite3
import os
import re
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

DB_PATH = "/home/chris/wordhord/wordhord.db"
POLYGLOSSIA_DIR = "/home/chris/polyglossia"
LANGUAGES = ['dutch', 'finnish', 'german', 'portuguese', 'spanish', 'swedish']

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
    accusative = Column(String) # For German N-declension
    conjugations = Column(String)
    example = Column(String)
    example_translation = Column(String)
    level = Column(String)
    interval = Column(Integer, default=0)
    ease_factor = Column(Float, default=2.5)
    repetition_count = Column(Integer, default=0)
    next_review = Column(DateTime)
    passed = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    __table_args__ = (UniqueConstraint('language', 'term', name='_language_term_uc'),)

def extract_field(section, field_name):
    # Support both "Field: value" and "- Field: value"
    pattern = fr'(?:- )?{field_name}:\s*(.*?)(?:\n\s*-|\n\s*Example:|\n\s*##|$)'
    match = re.search(pattern, section, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""

def migrate():
    engine = create_engine(f"sqlite:///{DB_PATH}")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    for lang in LANGUAGES:
        filepath = os.path.join(POLYGLOSSIA_DIR, f"{lang}_vocab.md")
        if not os.path.exists(filepath):
            print(f"File not found: {filepath}")
            continue
            
        print(f"Migrating {lang}...")
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Updated pattern to catch [A1], A1, or Level 1
        pattern = r'- \*\*(?:\[?([A-C][12])\]?|Level\s+(\d))\s*([^*]+)\*\*\s*\(([^)]+)\)'
        matches = list(re.finditer(pattern, content))
        
        for i, match in enumerate(matches):
            level_code = match.group(1)
            level_num = match.group(2)
            raw_term = match.group(3).strip()
            translation = match.group(4).strip()
            
            # Map Level 1 -> A1, Level 2 -> A2 etc.
            if level_num:
                level_map = {'1': 'A1', '2': 'A2', '3': 'B1', '4': 'B2', '5': 'C1', '6': 'C2'}
                level_from_header = level_map.get(level_num, 'A1')
            else:
                level_from_header = level_code
            
            # Aggressive multi-pass cleaning
            term = raw_term.strip()
            while True:
                old_val = term
                term = re.sub(r'^[^\w\s\(]+', '', term).strip()
                term = re.sub(r'^(Level\s*\w\d?|\[?[A-C][12]\]?)\s*', '', term, flags=re.IGNORECASE).strip()
                term = re.sub(r'^(Verb|Adjektiv|Adverb|Nomen|Substantiv|Noun|Adj|Adv)\s+', '', term, flags=re.IGNORECASE).strip()
                if lang == 'german':
                    term = re.sub(r'^(Der|Die|Das)\s+', '', term, flags=re.IGNORECASE).strip()
                term = re.sub(r'^\d+[\.\s]*', '', term).strip()
                if term == old_val:
                    break

            if not term:
                continue
            
            start_pos = match.end()
            if i + 1 < len(matches):
                end_pos = matches[i+1].start()
            else:
                end_pos = len(content)
                
            section = content[start_pos:end_pos]
            
            ipa = extract_field(section, 'IPA')
            gender = extract_field(section, 'Gender')
            plural = extract_field(section, 'Plural')
            pos = extract_field(section, 'Part of Speech')
            
            # Special logic for German: Capitalize nouns and prepend articles
            if lang == 'german':
                is_noun = (pos and 'noun' in pos.lower()) or (gender and gender.lower() in ['masculine', 'feminine', 'neuter', 'der', 'die', 'das', 'm', 'f', 'n'])
                
                if is_noun:
                    g_map = {'masculine': 'der', 'feminine': 'die', 'neuter': 'das', 'der': 'der', 'die': 'die', 'das': 'das', 'm': 'der', 'f': 'die', 'n': 'das'}
                    art = g_map.get(gender.lower() if gender else "", "")
                    if art:
                        term = f"{art} {term.capitalize()}"
                    else:
                        term = term.capitalize()
                else:
                    term = term.lower()
            
            tone = extract_field(section, 'Tone')
            if tone:
                tone = tone.replace("'", "").replace('"', "").strip()
                tone = re.sub(r'^(Accent|Tone)\s*', '', tone, flags=re.IGNORECASE).strip()
            
            prefix = extract_field(section, 'Prefix')
            prep = extract_field(section, 'Preposition')
            case = extract_field(section, 'Case')
            accusative = extract_field(section, 'N-Declension')
            conj = extract_field(section, 'Conjugations')
            level = extract_field(section, 'Level') or level_from_header
            
            ex_match = re.search(r'Example:\s*"([^"]+)"\s*\(([^)]+)\)', section)
            example = ex_match.group(1) if ex_match else ""
            ex_trans = ex_match.group(2) if ex_match else ""
            
            # Check if exists
            existing_card = session.query(CardModel).filter_by(language=lang, term=term).first()
            
            if existing_card:
                existing_card.translation = translation
                existing_card.ipa = ipa
                existing_card.gender = gender
                existing_card.plural = plural
                existing_card.part_of_speech = pos
                existing_card.tone = tone
                existing_card.prefix = prefix
                existing_card.preposition = prep
                existing_card.case = case
                existing_card.accusative = accusative
                existing_card.conjugations = conj
                existing_card.example = example
                existing_card.example_translation = ex_trans
                if level: existing_card.level = level
            else:
                new_card = CardModel(
                    language=lang,
                    term=term,
                    translation=translation,
                    ipa=ipa,
                    gender=gender,
                    plural=plural,
                    part_of_speech=pos,
                    tone=tone,
                    prefix=prefix,
                    preposition=prep,
                    case=case,
                    accusative=accusative,
                    conjugations=conj,
                    example=example,
                    example_translation=ex_trans,
                    level=level,
                    next_review=datetime.utcnow()
                )
                session.add(new_card)
                
        session.commit()
    session.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()

import sqlite3
import os
import re
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

DB_PATH = "/home/chris/wordhord/wordhord.db"
VOCABULARY_DIR = "/home/chris/wordhord/vocabulary"
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
        filepath = os.path.join(VOCABULARY_DIR, f"{lang}_vocab.md")
        if not os.path.exists(filepath):
            print(f"File not found: {filepath}")
            continue
            
        print(f"Migrating {lang}...")
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Optimization: Fetch all existing terms for this language once to avoid N+1 queries
        existing_cards = {c.term: c for c in session.query(CardModel).filter_by(language=lang).all()}
            
        # Capture Level/Level num, then skip any bracketed tags or leading non-word chars like stress marks 'ˈ'
        # The translation part now captures everything until the LAST closing parenthesis on the line
        pattern = r'- \*\*(?:\[?([A-C][12])\]?|Level\s+(\d))\s*(?:\[[^\]]+\]\s*)?[^a-zA-Z0-9\[(]*([^*]+)\*\*\s*\((.*)\)'
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
                # Remove common prefixes and junk
                term = re.sub(r'^[^\w\s"\'ˈ]+', '', term).strip() # Remove leading punctuation/brackets but keep stress mark
                term = re.sub(r'^(Level\s*\w\d?|\[?[A-C][12]\]?)\s*', '', term, flags=re.IGNORECASE).strip()
                term = re.sub(r'^\[[^\]]+\]\s*', '', term).strip()
                term = re.sub(r'^(Verb|Adjektiv|Adverb|Nomen|Substantiv|Noun|Adj|Adv)\s+', '', term, flags=re.IGNORECASE).strip()
                if lang == 'german':
                    term = re.sub(r'^(Der|Die|Das)\s+', '', term, flags=re.IGNORECASE).strip()
                if lang in ['portuguese', 'spanish']:
                    term = re.sub(r'^(o|a|el|la)\s+', '', term, flags=re.IGNORECASE).strip()
                term = re.sub(r'^\d+[\.\s]*', '', term).strip()
                if term == old_val:
                    break

            if not term or len(term) < 1:
                continue
            
            # Final check: if term starts with junk again after cleaning
            term = re.sub(r'^[\s\]\-\*]+', '', term).strip()
            
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
            
            # Check if exists in our local cache or if we already added it in this run
            if term in existing_cards:
                existing_card = existing_cards[term]
                # Merge translation if new
                if translation and translation.lower() not in (existing_card.translation or "").lower():
                    existing_card.translation = f"{existing_card.translation}, {translation}"
                
                # Merge example if new
                if example and example.lower() not in (existing_card.example or "").lower():
                    if existing_card.example:
                        existing_card.example = f"{existing_card.example}\n{example}"
                        existing_card.example_translation = f"{existing_card.example_translation}\n{ex_trans}"
                    else:
                        existing_card.example = example
                        existing_card.example_translation = ex_trans

                # Fill in missing fields
                if not existing_card.ipa: existing_card.ipa = ipa
                if not existing_card.gender: existing_card.gender = gender
                if not existing_card.plural: existing_card.plural = plural
                if not existing_card.part_of_speech: existing_card.part_of_speech = pos
                if not existing_card.tone: existing_card.tone = tone
                if not existing_card.prefix: existing_card.prefix = prefix
                if not existing_card.preposition: existing_card.preposition = prep
                if not existing_card.case: existing_card.case = case
                if not existing_card.accusative: existing_card.accusative = accusative
                if not existing_card.conjugations: existing_card.conjugations = conj
                if not existing_card.level: existing_card.level = level
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
                existing_cards[term] = new_card # Add to cache for this run
                
        try:
            session.commit()
        except Exception as e:
            print(f"  ⚠ Error committing {lang}: {e}")
            session.rollback()
    session.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()

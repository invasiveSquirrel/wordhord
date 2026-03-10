import sqlite3
import os
import re
from sqlalchemy import create_engine, Column, Integer, String, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker

DB_PATH = "/home/chris/wordhord.db"
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
    conjugations = Column(String)
    example = Column(String)
    example_translation = Column(String)
    level = Column(String)
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
            
        pattern = r'- \*\*([^*]+)\*\*\s*\(([^)]+)\)'
        matches = list(re.finditer(pattern, content))
        
        for i, match in enumerate(matches):
            term = match.group(1).strip()
            translation = match.group(2).strip()
            
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
            tone = extract_field(section, 'Tone')
            prefix = extract_field(section, 'Prefix')
            prep = extract_field(section, 'Preposition')
            case = extract_field(section, 'Case')
            conj = extract_field(section, 'Conjugations')
            level = extract_field(section, 'Level')
            
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
                existing_card.conjugations = conj
                existing_card.example = example
                existing_card.example_translation = ex_trans
                existing_card.level = level if level else existing_card.level
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
                    conjugations=conj,
                    example=example,
                    example_translation=ex_trans,
                    level=level
                )
                session.add(new_card)
                
        session.commit()
    session.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()

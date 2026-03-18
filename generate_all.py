import asyncio
import sqlite3
import os
import json
import sys
import random
import re
import warnings
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from datetime import datetime, timezone

# Suppress Pydantic warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

# Database Setup
DB_PATH = "/home/chris/wordhord/wordhord.db"
VOCAB_PATH = "/home/chris/wordhord/missing_vocab.json"

TARGETS = {
    'finnish': 6000,
    'swedish': 10000,
    'german': 20000,
    'spanish': 20000,
    'portuguese': 10000,
    'dutch': 10000,
    'scottish gaelic': 5000
}

# Increased frequency but smaller batches for stability
BATCHES_PER_LANG = 15
BATCH_TARGET = 15 

LANGUAGE_RULES = {
    'german': "Nouns MUST be capitalized and include article like 'Der Hund'. Other parts of speech MUST be lowercase.",
    'swedish': "Provide the base word without leading articles. Capitalize the first letter.",
    'portuguese': "Provide the base word ONLY. NEVER capitalize at the beginning (always lowercase).",
    'spanish': "Provide the base word ONLY. NEVER capitalize at the beginning (always lowercase).",
    'dutch': "Provide the base word without leading articles. Capitalize the first letter.",
    'finnish': "Provide basic A1-B2 words. Base word ONLY. Lowercase by default. ONLY capitalize if it is a town, country, or region name.",
    'scottish gaelic': "Provide the base word. Capitalize the first letter."
}

def load_google_api_key() -> str:
    key = os.getenv("GOOGLE_API_KEY")
    if key: return key
    try:
        api_key_file = os.path.expanduser("~/wordhord/wordhord_api.txt")
        if os.path.exists(api_key_file):
            with open(api_key_file, "r") as f: return f.read().strip()
    except Exception as e:
        print(f"Error loading key: {e}", flush=True)
    return None

GOOGLE_API_KEY = load_google_api_key()
if not GOOGLE_API_KEY:
    print("FATAL: No GOOGLE_API_KEY found.", flush=True)
    sys.exit(1)

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=GOOGLE_API_KEY, temperature=0.7)

class CardItem(BaseModel):
    model_config = ConfigDict(extra='ignore')
    term: Optional[str] = None
    translation: Optional[str] = None
    ipa: Optional[str] = "[]"
    gender: Optional[str] = "N/A"
    part_of_speech: Optional[str] = "unknown"
    example: Optional[str] = ""
    example_translation: Optional[str] = ""
    level: Optional[str] = "A1"
    plural: Optional[str] = ""

def cleanup_term(term, language):
    if not term: return term
    # Remove linguistic markers
    pos_terms = ['Adjective', 'Noun', 'Verb', 'Adverb', 'Adjektiivi', 'Substantiivi', 'Verbi', 'Adverbi']
    pattern = r'^(' + '|'.join([re.escape(t) for t in pos_terms]) + r')(\.?)\s+'
    term = re.sub(pattern, '', term, flags=re.IGNORECASE).strip()
    if language in ['portuguese', 'spanish']:
        term = term.lower()
    elif language == 'german':
        match = re.match(r'^(der|die|das)\s+(.*)', term, re.I)
        if match:
            term = f"{match.group(1).capitalize()} {match.group(2).capitalize()}"
        else:
            term = term.lower()
    elif language != 'finnish':
        term = term[0].upper() + term[1:]
    return term

async def generate_batch(language, existing_terms, specific_words=None):
    rule = LANGUAGE_RULES.get(language, "Capitalize the first letter.")
    
    if specific_words:
        print(f"  [LLM] Requesting {len(specific_words)} {language} words from sources...", flush=True)
        prompt = f"""
Provide full dictionary entries for the following {len(specific_words)} {language.capitalize()} words:
Words: {", ".join(specific_words)}

RULE: {rule}
Requirement: Provide translation, IPA, part of speech, gender, natural example sentence with English translation, and CEFR level (A1-C2).
For Finnish: If you recognize a word from a German source, provide the ENGLISH translation.

Return ONLY a JSON list of objects.
"""
    else:
        existing_list = list(existing_terms)
        sample = random.sample(existing_list, min(len(existing_list), 100)) if existing_list else []
        existing_str = ", ".join(sample)
        print(f"  [LLM] Generating {BATCH_TARGET} terms for {language} from frequency...", flush=True)
        prompt = f"""
Generate {BATCH_TARGET} unique {language.capitalize()} vocabulary entries (A1-B2).
Focus: High frequency words from News and Wikipedia.
RULE: {rule}
STRICTLY AVOID: {existing_str}...
Return ONLY a JSON list of objects with fields: term, translation, ipa, gender, part_of_speech, example, example_translation, level, plural.
"""
    
    try:
        response = await asyncio.wait_for(llm.ainvoke(prompt), timeout=120)
        content = response.content.strip()
        if content.startswith("```"):
            content = re.sub(r'^```(json)?\n', '', content)
            content = re.sub(r'\n```$', '', content)
        items = json.loads(content)
        
        # Robust Mapping
        standardized = []
        for item in items:
            # Map common LLM aliases
            term = item.get('term') or item.get('word') or item.get('german_word') or item.get('portuguese_word')
            translation = item.get('translation') or item.get('english_translation')
            example = item.get('example') or item.get('sentence')
            ex_trans = item.get('example_translation') or item.get('sentence_translation')
            level = item.get('level') or item.get('cefr_level') or item.get('cefr')
            
            if term and translation:
                standardized.append({
                    'term': str(term),
                    'translation': str(translation),
                    'ipa': str(item.get('ipa', '[]')),
                    'gender': str(item.get('gender', 'N/A')),
                    'part_of_speech': str(item.get('part_of_speech', 'unknown')),
                    'example': str(example or ""),
                    'example_translation': str(ex_trans or ""),
                    'level': str(level or "A1"),
                    'plural': str(item.get('plural', ""))
                })
        return standardized
    except Exception as e:
        print(f"  [!] LLM error generating {language}: {e}", flush=True)
        return []

async def process_language(language, target_count):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM cards WHERE language = ?", (language,))
    current_count = cursor.fetchone()[0]
    conn.close()

    if current_count >= target_count:
        print(f"{language.capitalize()} target met.", flush=True)
        return False
        
    print(f"\n--- {language.capitalize()} ({current_count}/{target_count}) ---", flush=True)
    
    for batch_num in range(BATCHES_PER_LANG):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT term FROM cards WHERE language = ?", (language,))
        existing_terms = set(row[0].lower() for row in cursor.fetchall())
        conn.close()
        
        specific_words = None
        if os.path.exists(VOCAB_PATH):
            try:
                with open(VOCAB_PATH, 'r', encoding='utf-8') as f:
                    all_missing = json.load(f)
                lang_missing = all_missing.get(language, [])
                lang_missing = [w for w in lang_missing if w.lower() not in existing_terms]
                if lang_missing:
                    specific_words = random.sample(lang_missing, min(len(lang_missing), BATCH_TARGET))
            except: pass

        batch = await generate_batch(language, existing_terms, specific_words)
        if not batch: continue
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        added = 0
        actually_added_words = []
        for item in batch:
            term = cleanup_term(item['term'], language)
            if not term or term.lower() in existing_terms: continue
            try:
                cursor.execute("""
                    INSERT INTO cards (language, term, translation, ipa, gender, part_of_speech, 
                                     example, example_translation, plural, level, next_review, ease_factor)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (language, term, item['translation'], item['ipa'], item['gender'], item['part_of_speech'],
                    item['example'], item['example_translation'], item['plural'], item['level'],
                    datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'), 2.5))
                existing_terms.add(term.lower())
                actually_added_words.append(item['term']) 
                added += 1
            except: continue
        conn.commit()
        conn.close()
        
        if specific_words and actually_added_words:
            try:
                with open(VOCAB_PATH, 'r', encoding='utf-8') as f:
                    all_missing = json.load(f)
                current_missing = all_missing.get(language, [])
                new_missing = [w for w in current_missing if w not in actually_added_words]
                all_missing[language] = new_missing
                with open(VOCAB_PATH, 'w', encoding='utf-8') as f:
                    json.dump(all_missing, f, ensure_ascii=False, indent=2)
            except: pass

        print(f"  [+] Added {added} cards (Batch {batch_num+1}/{BATCHES_PER_LANG}).", flush=True)
        await asyncio.sleep(1)
    return True

async def main():
    print(f"Starting generation pass at {datetime.now(timezone.utc)}", flush=True)
    langs = list(TARGETS.keys())
    random.shuffle(langs)
    for lang in langs:
        try:
            await process_language(lang, TARGETS[lang])
        except Exception as e:
            print(f"Error in pass for {lang}: {e}", flush=True)
    print("\nGeneration Pass complete.", flush=True)

if __name__ == "__main__":
    asyncio.run(main())

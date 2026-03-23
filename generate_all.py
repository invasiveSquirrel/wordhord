import asyncio
import sqlite3
import os
import json
import sys
import random
import re
import warnings
import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from datetime import datetime, timezone
from langdetect import detect, LangDetectException
from lingua import Language, LanguageDetectorBuilder

# Suppress Pydantic warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

# Lingua detector (N-gram analysis) setup for robust Dutch/German disambiguation
try:
    dutch_detector = LanguageDetectorBuilder.from_languages(Language.DUTCH, Language.GERMAN, Language.ENGLISH).build()
    finnish_detector = LanguageDetectorBuilder.from_languages(Language.FINNISH, Language.ENGLISH, Language.GERMAN, Language.SWEDISH).build()
except Exception as e:
    print(f"Failed to initialize Lingua detector: {e}")
    dutch_detector = None
    finnish_detector = None

# Load Dutch lexicon for highly accurate disambiguation
DUTCH_LEXICON = set()
try:
    with open("/home/chris/wordhord/dutch_lexicon.txt", "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split()
            if parts:
                DUTCH_LEXICON.add(parts[0].lower())
    print(f"Loaded {len(DUTCH_LEXICON)} words into Dutch lexicon.", flush=True)
except Exception as e:
    print(f"Warning: Could not load Dutch lexicon: {e}", flush=True)

# Database Setup
DB_PATH = "/home/chris/wordhord/wordhord.db"
VOCAB_PATH = "/home/chris/wordhord/missing_vocab.json"

TARGETS = {
    'finnish': 10000,
    'swedish': 20000,
    'german': 30000,
    'spanish': 30000,
    'portuguese': 20000,
    'dutch': 30000,
    'scottish gaelic': 5000
}

# Increased frequency but smaller batches for stability
BATCHES_PER_LANG = 1000 # Increased from 15 to ensure targets are met
BATCH_TARGET = 20 # Increased from 15 for slightly larger batches

LANGUAGE_RULES = {
    'german': "CRITICAL: Nouns MUST be capitalized and include article (der/die/das). MUST INCLUDE Lemma and POS. NOUNS MUST CONTAIN Nominative, Genitive, and Plural forms, noting irregular vowel/consonant changes. VERBS MUST CONTAIN 1st person singular, past, perfect forms, and irregular changes. For verbs, include Transitive/Intransitive tag. Explicitly note IRREGULAR Forms (e.g., masculine accusative forms). Use 'conjugations' field to store: Transitive/Intransitive tag, Verb Tense/Mood Examples, Irregular forms. Use 'example' field to include an unambiguous Example sentence, and Idiomatic Usage Notes (especially distinct phrasal verb forms, separable/inseparable, or nominative expressions). Always include IPA.",
    'swedish': "CRITICAL: Base word. MUST INCLUDE Lemma and POS. NOUNS MUST CONTAIN base form, definite suffix (-en/-ett), Genitive forms, and Plural forms, noting irregular changes. VERBS MUST CONTAIN present, past, supine forms, 1st person singular, and irregular changes. For verbs, include Transitive/Intransitive tag. Explicitly note IRREGULAR Forms. Use 'conjugations' field to store: Transitive/Intransitive tag, Verb Tense/Mood Examples, Irregular forms. Use 'example' field to include an unambiguous Example sentence, and Idiomatic Usage Notes (especially distinct phrasal/particle verb forms). Always include IPA.",
    'portuguese': "Provide the base word ONLY. NEVER capitalize at the beginning (always lowercase).",
    'spanish': "Provide the base word ONLY. NEVER capitalize at the beginning (always lowercase).",
    'dutch': "CRITICAL: Base word with article (de/het). MUST INCLUDE Lemma and POS. NOUNS MUST CONTAIN base form, Genitive (if applicable), and Plural forms, noting irregular changes. VERBS MUST CONTAIN 1st person singular, past, perfect forms, and irregular changes. For verbs, include Transitive/Intransitive tag. Explicitly note IRREGULAR Forms. Use 'conjugations' field to store: Transitive/Intransitive tag, Verb Tense/Mood Examples, Irregular forms. Use 'example' field to include an unambiguous Example sentence, and Idiomatic Usage Notes (especially distinct separable/inseparable phrasal verb forms). Always include IPA.",
    'finnish': "CRITICAL: Provide full vocabulary info. Lowercase by default. MUST INCLUDE Lemma and POS. NOUNS MUST CONTAIN NOMINATIVE AND GENITIVE FORMS (e.g. in 'term' or 'plural') AND IRREGULAR CONSONANT/VOWEL CHANGES. VERBS MUST CONTAIN 1ST PERSON SINGULAR AND IRREGULAR CHANGES. For Finnish, use the 'conjugations' field to store: Transitive/Intransitive Tag, All Cases (Nom, Gen, Part, Ill, Iness, El, All, Abl, Ess, Tra), Verb Person/Number Forms, Imperative/Conditional Moods, and Derivational Suffixes. Use the 'example' field to include an Example sentence, Verb Tense/Mood Examples, and Idiomatic Usage Notes. Always include Pronunciation/Phonetic Transcription (IPA).",
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
    conjugations: Optional[str] = ""

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

Return ONLY a JSON list of objects. Include fields: term, translation, ipa, gender, part_of_speech, example, example_translation, level, plural, conjugations.
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
Return ONLY a JSON list of objects with fields: term, translation, ipa, gender, part_of_speech, example, example_translation, level, plural, conjugations.
"""
    
    max_retries = 5
    base_delay = 2
    for attempt in range(max_retries):
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
                        'plural': str(item.get('plural', "")),
                        'conjugations': str(item.get('conjugations', ""))
                    })
            return standardized
        except Exception as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                print(f"  [!] LLM error generating {language}: {e}. Retrying in {delay:.2f}s...", flush=True)
                await asyncio.sleep(delay)
            else:
                print(f"  [!] LLM error generating {language} after {max_retries} attempts: {e}", flush=True)
                return []

def setup_logging():
    log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'generation_errors.log')
    logging.basicConfig(level=logging.ERROR, 
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        filename=log_file,
                        filemode='a')
    return logging.getLogger(__name__)

error_logger = setup_logging()

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
        if current_count >= target_count:
            print(f"{language.capitalize()} target now met. Moving to next language.", flush=True)
            break

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT lower(term) FROM cards WHERE language = ?", (language,))
        existing_terms = set(row[0] for row in cursor.fetchall())
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
            except Exception as e:
                error_logger.error(f"Failed to process missing vocab file for {language}: {e}")


        batch = await generate_batch(language, existing_terms, specific_words)
        if not batch:
            await asyncio.sleep(5) # Avoid rapid-fire failed generations
            continue
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        added_in_batch = 0
        
        for item in batch:
            # Ensure all values are strings to prevent type errors
            try:
                term = str(item.get('term', '')).strip()
                if not term:
                    continue

                # Normalize term for checking and insertion
                clean_term = cleanup_term(term, language)
                lower_term = clean_term.lower()

                if lower_term in existing_terms:
                    continue

                # Data validation & Language detection
                if language.lower() == 'dutch':
                    # Extremely robust Dutch validation using lexicon and n-gram analysis
                    lower_clean = clean_term.lower()
                    is_dutch = False
                    
                    # 1. Check against dedicated Dutch lexicon first
                    if lower_clean in DUTCH_LEXICON:
                        is_dutch = True
                    # 2. If not in lexicon, use Lingua n-gram analysis
                    elif dutch_detector:
                        detected = dutch_detector.detect_language_of(clean_term)
                        if detected == Language.DUTCH:
                            is_dutch = True
                    
                    if not is_dutch and not str(item.get('example', '')).strip():
                        print(f"  [!] Rejecting '{clean_term}' (Not verified as Dutch by lexicon/n-gram, missing example)", flush=True)
                        continue
                elif language.lower() == 'finnish':
                    if finnish_detector:
                        detected = finnish_detector.detect_language_of(clean_term)
                        if detected in [Language.ENGLISH, Language.GERMAN, Language.SWEDISH]:
                            example_text = str(item.get('example', '')).strip()
                            if not example_text or finnish_detector.detect_language_of(example_text) != Language.FINNISH:
                                print(f"  [!] Rejecting '{clean_term}' (Detected {detected.name} instead of FINNISH)", flush=True)
                                continue
                    if not str(item.get('example', '')).strip():
                        print(f"  [!] Rejecting '{clean_term}' (Missing example sentence for Finnish)", flush=True)
                        continue
                elif language.lower() not in ['english', 'german']:
                    try:
                        detected_lang = detect(clean_term)
                        if detected_lang in ['en', 'de'] and not str(item.get('example', '')).strip():
                            print(f"  [!] Rejecting '{clean_term}' (Detected {detected_lang}, missing example)", flush=True)
                            continue
                    except LangDetectException:
                        pass # Ignore detection errors for short/ambiguous terms
                
                # Use INSERT OR IGNORE to prevent race conditions with unique constraint
                cursor.execute("""
                    INSERT OR IGNORE INTO cards (language, term, translation, ipa, gender, part_of_speech, 
                                     example, example_translation, plural, level, conjugations, next_review, ease_factor)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (language, clean_term, str(item.get('translation', '')), str(item.get('ipa', '[]')), 
                      str(item.get('gender', 'N/A')), str(item.get('part_of_speech', 'unknown')),
                      str(item.get('example', '')), str(item.get('example_translation', '')), 
                      str(item.get('plural', '')), str(item.get('level', 'A1')),
                      str(item.get('conjugations', '')),
                      datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'), 2.5))
                
                if cursor.rowcount > 0:
                    added_in_batch += 1
                    existing_terms.add(lower_term)

            except sqlite3.Error as e:
                error_logger.error(f"DB insertion error for term '{item.get('term')}' in {language}: {e}")
            except Exception as e:
                error_logger.error(f"Unexpected error processing item '{item}' in {language}: {e}")
        
        conn.commit()
        conn.close()
        
        current_count += added_in_batch
        print(f"  [+] Added {added_in_batch} cards. Total for {language}: {current_count}/{target_count} (Batch {batch_num+1}/{BATCHES_PER_LANG})", flush=True)
        await asyncio.sleep(2) # Brief pause to avoid overwhelming API
    return True

async def main():
    while True:
        print(f"\n{'='*20}\nStarting new generation pass at {datetime.now(timezone.utc)}\n{'='*20}", flush=True)
        
        all_met = True
        
        # Get current counts for all languages first
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT language, COUNT(*) FROM cards GROUP BY language")
            current_counts = {lang: count for lang, count in cursor.fetchall()}
            conn.close()
        except sqlite3.Error as e:
            error_logger.error(f"Failed to get initial counts: {e}")
            await asyncio.sleep(60)
            continue

        langs = list(TARGETS.keys())
        random.shuffle(langs)

        for lang in langs:
            if current_counts.get(lang, 0) < TARGETS[lang]:
                all_met = False
                try:
                    await process_language(lang, TARGETS[lang])
                except Exception as e:
                    error_logger.error(f"Critical error in pass for {lang}: {e}")
                    print(f"  [!!!] Critical error for {lang}: {e}", flush=True)
        
        if all_met:
            print("\nAll vocabulary targets have been met or exceeded. Generation complete.", flush=True)
            break
        
        print("\nGeneration Pass complete. Will start next pass in 60 seconds...", flush=True)
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())

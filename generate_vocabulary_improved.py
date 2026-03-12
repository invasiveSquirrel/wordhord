#!/usr/bin/env python3
"""
Comprehensive Vocabulary Generator - Gemini API
Targets: German, Swedish, Spanish, Dutch, Finnish, Portuguese.
Strict linguistic rules for IPA, Tone, Gender, and Morphological changes.
"""

import os
import re
import time
import sys
import subprocess
import google.generativeai as genai

# Force line buffering for logs
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)

# Setup paths
VOCABULARY_DIR = "/home/chris/wordhord/vocabulary"
SOURCES_DIR = "/home/chris/vocabulary_sources"
API_KEY_FILE = "/home/chris/wordhord/wordhord_api.txt"
DB_PATH = "/home/chris/wordhord/wordhord.db"
MIGRATE_SCRIPT = "/home/chris/wordhord/migrate_to_sqlite.py"
VENV_PYTHON = "/home/chris/wordhord/backend/venv/bin/python"

# Load API Key
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key and os.path.exists(API_KEY_FILE):
    with open(API_KEY_FILE, "r") as f:
        api_key = f.read().strip()

if api_key:
    genai.configure(api_key=api_key)
else:
    print("❌ Error: GOOGLE_API_KEY not found in environment or file.")
    sys.exit(1)

model = genai.GenerativeModel('gemini-2.0-flash')

LANGUAGES = {
    "dutch": {"name": "Dutch", "sources": ["dutch_freq.txt"], "target": 10000, "articles": True, "start_line": 500},
    "german": {"name": "German", "sources": ["german_freq.txt", "german_using.txt"], "target": 10000, "articles": True, "start_line": 870},
    "swedish": {"name": "Swedish", "target": 10000, "articles": True, "method": "direct_graded"},
    "portuguese": {"name": "Portuguese", "sources": ["portuguese_freq.txt"], "target": 10000, "articles": True, "start_line": 500},
    "spanish": {"name": "Spanish", "sources": ["spanish_freq.txt", "spanish_using.txt"], "target": 10000, "articles": True, "start_line": 730},
    "finnish": {"name": "Finnish", "target": 3000, "articles": False, "method": "direct_graded"}
}

def get_db_count(lang_code):
    try:
        cmd = ["/usr/bin/sqlite3", DB_PATH, f"SELECT COUNT(*) FROM cards WHERE language='{lang_code}';"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return int(result.stdout.strip())
    except Exception as e:
        print(f"  ⚠ Error querying database for {lang_code}: {e}", flush=True)
        return 0

def run_migration():
    print(f"🔄 Triggering migration to database...", flush=True)
    try:
        subprocess.run([VENV_PYTHON, MIGRATE_SCRIPT], check=True)
        print(f"✅ Migration complete.", flush=True)
    except Exception as e:
        print(f"  ❌ Migration failed: {e}", flush=True)

def get_source_context(lang_code, start_rank):
    info = LANGUAGES[lang_code]
    source_files = info.get("sources", [])
    if not source_files: return "Direct generation requested (no source file)."
    
    context = []
    lines_to_skip = info.get("start_line", 0) + (start_rank * 4)
    
    for sf in source_files:
        path = os.path.join(SOURCES_DIR, sf)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    all_lines = f.readlines()
                    chunk = all_lines[lines_to_skip : lines_to_skip + 300]
                    context.append(f"--- Source: {sf} (Approx rank {start_rank}) ---\n" + "".join(chunk))
            except Exception as e:
                print(f"  ⚠ Error reading source {sf}: {e}", flush=True)
    return "\n\n".join(context)

def generate_batch(lang_code, lang_info):
    name = lang_info["name"]
    target = lang_info["target"]
    output_file = os.path.join(VOCABULARY_DIR, f"{lang_code}_vocab.md")
    
    print(f"Checking {name} progress in database...", flush=True)
    current_count = get_db_count(lang_code)
            
    if current_count >= target:
        print(f"✅ {name} complete ({current_count} words in DB).", flush=True)
        return

    print(f"\n🚀 Generating {name} ({current_count}/{target})...", flush=True)
    batch_size = 50
    
    while current_count < target:
        start_rank = current_count + 1
        
        if current_count < 1000: level_goal = "A1"
        elif current_count < 3000: level_goal = "A2"
        elif current_count < 6000: level_goal = "B1"
        else: level_goal = "B2/C1"

        if lang_info.get("method") == "direct_graded":
            instr = f"Generate {batch_size} common {name} vocabulary words for level {level_goal}, starting from frequency rank {start_rank}."
            context_block = ""
        else:
            instr = f"Extract and define the next {batch_size} unique words for {name} from the provided source text (Rank {start_rank}+)."
            context_block = f"SOURCE CONTEXT:\n{get_source_context(lang_code, start_rank)}"

        article_instr = ""
        if lang_info.get("articles"):
            if lang_code == "german":
                article_instr = f"MANDATORY: For EVERY noun, include the lowercase definite article directly in the bold header (e.g., **[{level_goal}] der Abend**)."
            else:
                article_instr = f"MANDATORY: For EVERY noun, include the definite article OF THE TARGET LANGUAGE directly in the bold header (e.g., Swedish: **[{level_goal}] Bilen** or **[{level_goal}] En bil**)."

        capitalization_instr = ""
        if lang_code == "german":
            capitalization_instr = "GERMAN RULES: ONLY nouns (Substantive) MUST be capitalized. All other parts of speech (verbs, adjectives, etc.) MUST be lowercase. Articles MUST be lowercase."
        elif lang_code == "spanish":
            capitalization_instr = "SPANISH RULES: Ensure you ONLY extract the Spanish word as the term. Example: 'año' not 'year'. Use lowercase for all terms unless proper nouns. Prepend articles for nouns."
        else:
            capitalization_instr = f"Lower-case all {name} words unless they are proper nouns."

        linguistic_instr = f"""STRICT LINGUISTIC RULES for {name}:
1. IPA: MUST include the primary stress mark 'ˈ' before the stressed syllable.
2. VERBS: Provide 'Present', 'Past', 'Future', and 'Participle' forms.
3. NOUNS: Provide Gender and Plural forms.
4. SWEDISH: Provide Tone (Accent 1 or 2). This is CRITICAL for pronunciation.
5. FINNISH: Explicitly state any sound changes (e.g., consonant gradation k/p/t changes) in the Conjugations or a 'Notes' field. Provide the partitive singular form for nouns.
6. EXAMPLES: Provide one clear example sentence in {name} with its English translation."""

        prompt = f"""You are a master linguistic database tool. {instr}
{context_block}

{article_instr}
{capitalization_instr}
{linguistic_instr}

FORMAT:
- **[{level_goal}] [Article] word_in_{lang_code}** (English translation)
  - IPA: [ipa with ˈ stress]
  - Part of Speech: [pos]
  - Gender: [gender]
  - Plural: [plural / Finnish: partitive]
  - Tone: [Swedish only]
  - Conjugations: [Verbs: Pres: x, Past: y, Fut: z, Part: a | Finnish: include gradation notes]
  - Example: "Example sentence in {name}" (English translation)

Output ONLY the markdown list. Every field is mandatory for every entry.
"""
        try:
            print(f"  ... Requesting {batch_size} {name} words (Rank {start_rank})...", flush=True)
            response = model.generate_content(prompt)
            text = response.text
            new_words_count = text.count("- **")
            if new_words_count > 0:
                with open(output_file, "a", encoding="utf-8") as f:
                    if not os.path.exists(output_file) or os.path.getsize(output_file) < 50: 
                        f.write(f"# {name} Vocabulary\n\n")
                    f.write("\n\n" + text.strip())
                
                # Sync to DB
                run_migration()
                
                # Re-query DB to get true count
                current_count = get_db_count(lang_code)
                print(f"  ✓ DB now has {current_count} {name} words (Target: {target})", flush=True)
                time.sleep(5)
            else:
                print("  ⚠ No words found. Retrying...", flush=True)
                time.sleep(10)
        except Exception as e:
            print(f"  ❌ Error: {e}", flush=True)
            if "429" in str(e): time.sleep(30)
            else: time.sleep(15)

def main():
    try:
        print("🚀 Starting Vocabulary Generation Script (Strict Linguistic Mode)...", flush=True)
        # Sequence requested: German, Swedish, Spanish, Dutch, Finnish, Portuguese
        order = ["german", "swedish", "spanish", "dutch", "finnish", "portuguese"]
        for code in order:
            # Special case: Even if German file is full, our enrichment script is handling it in DB.
            # We skip German here to move to Swedish/others faster.
            if code == 'german' and os.path.exists(os.path.join(VOCABULARY_DIR, "german_vocab.md")):
                if os.path.getsize(os.path.join(VOCABULARY_DIR, "german_vocab.md")) > 1000000:
                    print("✅ German file is large, skipping to Swedish. (DB enrichment running separately)", flush=True)
                    continue
            generate_batch(code, LANGUAGES[code])
    except Exception as e:
        print(f"CRITICAL ERROR IN MAIN: {e}", flush=True)

if __name__ == "__main__":
    main()

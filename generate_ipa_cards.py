#!/usr/bin/env python3
import os
import sqlite3
import google.generativeai as genai
import json

# Setup paths
DB_PATH = "/home/chris/wordhord/wordhord.db"
API_KEY_FILE = "/home/chris/wordhord/wordhord_api.txt"

# Load API Key
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key and os.path.exists(API_KEY_FILE):
    with open(API_KEY_FILE, "r") as f:
        api_key = f.read().strip()

if api_key:
    genai.configure(api_key=api_key)
else:
    print("❌ Error: GOOGLE_API_KEY not found.")
    exit(1)

model = genai.GenerativeModel('gemini-2.0-flash')

LANGUAGES = {
    "english": "English",
    "dutch": "Dutch",
    "german": "German",
    "spanish": "Spanish",
    "portuguese": "Portuguese",
    "finnish": "Finnish",
    "swedish": "Swedish"
}

def generate_ipa_for_language(lang_code, lang_name):
    prompt = f"""
    Generate a set of 10-15 IPA practice cards for {lang_name}. 
    Focus on specific phonetic nuances that distinguish it from other languages (e.g., aspirated vs unaspirated 't', dental vs alveolar 's', dialectal variations like 'g' in Dutch or 'j' in Spanish).
    
    For each card, provide:
    1. The IPA symbol (e.g., [tʰ]).
    2. A brief description of the sound and its nuance (e.g., "Aspirated 't' as in 'top', distinct from the unaspirated 't' in Spanish").
    3. An example word in {lang_name}.
    4. The translation of that word.
    5. The full IPA of that example word.

    Format the output as a JSON list of objects:
    [
      {{
        "term": "[tʰ]",
        "translation": "Aspirated voiceless alveolar plosive. Distinctive in English at the start of stressed syllables.",
        "example": "top",
        "example_translation": "top",
        "ipa": "[tʰɒp]"
      }},
      ...
    ]
    """
    
    print(f"🚀 Generating IPA cards for {lang_name}...")
    try:
        response = model.generate_content(prompt)
        # Extract JSON from response
        text = response.text
        json_str = re.search(r'\[.*\]', text, re.DOTALL).group()
        return json.loads(json_str)
    except Exception as e:
        print(f"❌ Error generating for {lang_name}: {e}")
        return []

import re

def save_to_db(cards, lang_code):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Ensure language code is prefixed with ipa_
    ipa_lang = f"ipa_{lang_code}"
    
    for card in cards:
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO cards 
                (language, term, translation, example, example_translation, ipa, level)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                ipa_lang, 
                card['term'], 
                card['translation'], 
                card['example'], 
                card['example_translation'], 
                card['ipa'],
                'Phonetics'
            ))
        except Exception as e:
            print(f"  ⚠ Error saving card {card['term']}: {e}")
            
    conn.commit()
    conn.close()
    print(f"✅ Saved {len(cards)} cards for {ipa_lang}.")

if __name__ == "__main__":
    for code, name in LANGUAGES.items():
        cards = generate_ipa_for_language(code, name)
        if cards:
            save_to_db(cards, code)

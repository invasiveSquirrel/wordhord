import asyncio
import sqlite3
import os
import json
import sys
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone

# Database Setup
DB_PATH = "/home/chris/wordhord/wordhord.db"

def load_google_api_key() -> str:
    key = os.getenv("GOOGLE_API_KEY")
    if key: return key
    try:
        api_key_file = os.getenv("API_KEY_FILE", "/home/chris/wordhord/wordhord_api.txt")
        if os.path.exists(api_key_file):
            with open(api_key_file, "r") as f: return f.read().strip()
    except Exception as e:
        print(f"Error loading key: {e}")
    return None

GOOGLE_API_KEY = load_google_api_key()
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=GOOGLE_API_KEY, temperature=0.3)

class CardItem(BaseModel):
    term: str
    translation: str
    ipa: str
    gender: str
    part_of_speech: str
    example: str
    example_translation: str
    level: str
    plural: Optional[str] = ""

async def get_existing_terms():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT term FROM cards WHERE language = 'german'")
    terms = set(row[0].lower() for row in cursor.fetchall())
    conn.close()
    return terms

async def generate_batch(existing_terms, count=20):
    import random
    existing_list = list(existing_terms)
    sample_size = min(len(existing_list), 100)
    sample = random.sample(existing_list, sample_size)
    existing_str = ", ".join(sample)
    
    prompt = f"""
Generate {count} unique, high-frequency German vocabulary entries based on internet frequency.
Avoid these existing terms: {existing_str}...

For each entry, provide:
1. term: The German word (Nouns MUST be capitalized and include article like "Der Hund", other parts of speech MUST be lowercase).
2. translation: English translation.
3. ipa: IPA pronunciation in brackets [].
4. gender: "Der", "Die", "Das" or "N/A".
5. part_of_speech: noun, verb, adjective, adverb, etc.
6. example: A natural German sentence using the word.
7. example_translation: English translation of the example.
8. level: CEFR level (A1, A2, B1, B2, C1, C2).
9. plural: Plural form if it's a noun.

Return the result as a JSON list of objects ONLY. No markdown formatting.
"""
    
    try:
        # Reduced timeout or wrap in wait_for
        response = await asyncio.wait_for(llm.ainvoke(prompt), timeout=30)
        content = response.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
             content = content.split("```")[1].split("```")[0]
        
        items = json.loads(content)
        return [CardItem(**item) for item in items]
    except Exception as e:
        print(f"Error: {e}")
        return []

async def run_once(count=20):
    existing_terms = await get_existing_terms()
    batch = await generate_batch(existing_terms, count=count)
    if not batch: return 0
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    added = 0
    for item in batch:
        if item.term.lower() in existing_terms: continue
        try:
            cursor.execute("""
                INSERT INTO cards (
                    language, term, translation, ipa, gender, part_of_speech, 
                    example, example_translation, plural, level, 
                    next_review, ease_factor
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                'german', item.term, item.translation, item.ipa, item.gender, item.part_of_speech,
                item.example, item.example_translation, item.plural, item.level,
                datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'), 2.5
            ))
            added += 1
        except sqlite3.IntegrityError: continue
    conn.commit()
    conn.close()
    return added

if __name__ == "__main__":
    import sys
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    added = loop.run_until_complete(run_once(count))
    print(f"Added {added}")

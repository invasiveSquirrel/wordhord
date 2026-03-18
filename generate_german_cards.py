import asyncio
import sqlite3
import os
import json
import sys
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
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
            with open(api_key_file, "r") as f: 
                k = f.read().strip()
                print(f"Loaded key from {api_key_file}")
                return k
    except Exception as e:
        print(f"Error loading key: {e}")
    return None

GOOGLE_API_KEY = load_google_api_key()
if not GOOGLE_API_KEY:
    print("FATAL: No GOOGLE_API_KEY found.")
    sys.exit(1)

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
    print("Fetching existing terms...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT term FROM cards WHERE language = 'german'")
    terms = set(row[0].lower() for row in cursor.fetchall())
    conn.close()
    print(f"Found {len(terms)} existing German terms.")
    return terms

async def generate_batch(existing_terms, count=50):
    # Just take a random sample of existing terms to help the LLM avoid them
    import random
    existing_list = list(existing_terms)
    sample_size = min(len(existing_list), 100)
    sample = random.sample(existing_list, sample_size)
    existing_str = ", ".join(sample)
    
    print(f"Calling LLM for {count} terms...")
    prompt = f"""
Generate {count} unique, high-frequency German vocabulary entries based on internet frequency.
Avoid these existing terms: {existing_str}... (and many others already in database).

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
        response = await llm.ainvoke(prompt)
        content = response.content.strip()
        
        # Clean markdown if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
             content = content.split("```")[1].split("```")[0]
        
        items = json.loads(content)
        print(f"LLM returned {len(items)} items.")
        return [CardItem(**item) for item in items]
    except Exception as e:
        print(f"Generation error: {e}")
        return []

async def main():
    existing_terms = await get_existing_terms()
    total_to_generate = 10000
    generated_count = 0
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("Starting generation loop...")
    while generated_count < total_to_generate:
        print(f"Generating batch... ({generated_count}/{total_to_generate})")
        batch = await generate_batch(existing_terms, count=50)
        
        if not batch:
            print("Failed to generate batch, retrying in 5s...")
            await asyncio.sleep(5)
            continue
            
        added_in_batch = 0
        for item in batch:
            if item.term.lower() in existing_terms:
                continue
            
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
                existing_terms.add(item.term.lower())
                generated_count += 1
                added_in_batch += 1
            except sqlite3.IntegrityError:
                continue
        
        conn.commit()
        print(f"Added {added_in_batch} cards in this batch. Total: {generated_count}")
        
        # Throttling to avoid rate limits
        await asyncio.sleep(2)

    conn.close()
    print(f"Successfully added {generated_count} new German cards.")

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import sqlite3
import os
import json
import sys
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from typing import List, Optional, Dict
from langchain_google_genai import ChatGoogleGenerativeAI
from datetime import datetime

def load_google_api_key() -> str:
    key = os.getenv("GOOGLE_API_KEY")
    if key: return key
    try:
        api_key_file = os.path.expanduser("~/wordhord/wordhord_api.txt")
        if os.path.exists(api_key_file):
            with open(api_key_file, "r") as f: return f.read().strip()
    except Exception as e:
        pass
    return None

GOOGLE_API_KEY = load_google_api_key()
if not GOOGLE_API_KEY:
    print("FATAL: No GOOGLE_API_KEY found.", flush=True)
    sys.exit(1)

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=GOOGLE_API_KEY, temperature=0.2)

class DutchEnrichedWord(BaseModel):
    model_config = ConfigDict(extra='ignore')
    lemma: str = Field(description="The base word.")
    pos: str = Field(description="Part of speech.")
    noun_cases: Optional[str] = Field(default="", description="Base form with article (de/het), diminutive, and plural forms, irregular changes.")
    verb_forms: Optional[str] = Field(default="", description="1st person singular, past, perfect forms, irregular changes.")
    example_sentence: str = Field(description="A clear, unambiguous example sentence.")
    example_translation: str = Field(description="English translation of the sentence.")
    transitivity: Optional[str] = Field(default="", description="Transitive/Intransitive tag if verb.")
    irregular_forms: Optional[str] = Field(default="", description="Explicitly note irregular plural or verb forms.")
    verb_tense_examples: Optional[Dict[str, str]] = Field(default={}, description="Present, Past, Perfect examples.")
    idiomatic_notes: Optional[str] = Field(default="", description="Idiomatic usage notes, distinct phrasal verb forms.")
    phrasal_verb_tag: Optional[str] = Field(default="", description="Separable/Inseparable tag.")
    nominative_expression_tag: Optional[str] = Field(default="", description="Identification of fixed phrases.")
    declension_patterns: Optional[str] = Field(default="", description="Standard and common deviations.")

async def enrich_batch(words: List[str]) -> List[dict]:
    prompt = f"""
    You are an expert Dutch linguistic corpus analyzer. Enrich the following Dutch words with deep morphological and syntactical data.
    Words to enrich: {", ".join(words)}

    For each word, provide a JSON object adhering to these rules:
    - lemma: The base word.
    - pos: Part of speech.
    - noun_cases: If a noun, provide base form with article (de/het), diminutive, and plural forms, noting irregular consonant/vowel changes.
    - verb_forms: If a verb, provide 1st person singular, past, perfect forms, and note irregular changes.
    - example_sentence: A clear, unambiguous example sentence.
    - example_translation: English translation of the sentence.
    - transitivity: If a verb, tag as Transitive or Intransitive.
    - irregular_forms: Explicitly note irregular plural forms, etc.
    - verb_tense_examples: If a verb, a dictionary with keys 'Present', 'Past', 'Perfect' and example values.
    - idiomatic_notes: Distinct phrasal verb forms or nominative expressions.
    - phrasal_verb_tag: Mark 'Separable' or 'Inseparable' if applicable.
    - nominative_expression_tag: Identify if it forms a fixed phrase.
    - declension_patterns: Note standard patterns and deviations.

    Return ONLY a JSON list of objects matching the fields described. Do not include markdown formatting like ```json ... ```.
    """
    
    try:
        response = await llm.ainvoke(prompt)
        content = response.content.strip()
        if content.startswith("```"):
            import re
            content = re.sub(r'^```(json)?\n', '', content)
            content = re.sub(r'\n```$', '', content)
        
        items = json.loads(content)
        validated_items = []
        for item in items:
            try:
                validated = DutchEnrichedWord(**item)
                validated_items.append(validated.model_dump())
            except ValidationError as ve:
                print(f"Validation error for {item.get('lemma', 'unknown')}: {ve}")
        return validated_items
    except Exception as e:
        print(f"Error enriching batch: {e}")
        return []

async def main():
    DB_PATH = "/home/chris/wordhord/wordhord.db"
    OUTPUT_FILE = "/home/chris/wordhord/enriched_dutch.json"
    
    # Fetch a sample of Dutch words from the database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT term FROM cards WHERE language = 'dutch' LIMIT 100")
    words = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    if not words:
        # Fallback to some high frequency words if DB is empty
        words = ["de hond", "gaan", "het huis", "zien", "mooi", "opendoen", "de mens"]
        
    print(f"Starting enrichment for {len(words)} Dutch words...")
    
    all_enriched = []
    batch_size = 10
    
    for i in range(0, len(words), batch_size):
        batch = words[i:i+batch_size]
        print(f"Processing batch {i//batch_size + 1}/{(len(words) + batch_size - 1)//batch_size}...")
        enriched = await enrich_batch(batch)
        all_enriched.extend(enriched)
        await asyncio.sleep(2) # rate limiting
        
    # Save to JSON
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_enriched, f, indent=2, ensure_ascii=False)
        
    print(f"Enrichment complete. Data saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())

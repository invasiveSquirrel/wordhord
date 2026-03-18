import asyncio
import sqlite3
import os
import json
import re
from langchain_google_genai import ChatGoogleGenerativeAI

# Database Setup
DB_PATH = "/home/chris/wordhord/wordhord.db"

def load_google_api_key() -> str:
    key = os.getenv("GOOGLE_API_KEY")
    if key: return key
    try:
        api_key_file = os.getenv("API_KEY_FILE", "/home/chris/wordhord/wordhord_api.txt")
        with open(api_key_file, "r") as f: return f.read().strip()
    except FileNotFoundError: return None

GOOGLE_API_KEY = load_google_api_key()
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=GOOGLE_API_KEY, temperature=0)

async def check_proper_nouns(terms):
    if not terms: return []
    
    prompt = f"""
Identify which of the following Finnish words are names of towns, countries, or regions.
Return a JSON object where the keys are the original words and the values are boolean (true if it's a town/country/region, false otherwise).

Words: {", ".join(terms)}
"""
    try:
        response = await llm.ainvoke(prompt)
        content = response.content.strip()
        if content.startswith("```json"):
            content = content.split("```json")[1].split("```")[0]
        elif content.startswith("```"):
            content = content.split("```")[1].split("```")[0]
        return json.loads(content)
    except Exception as e:
        print(f"LLM Error: {e}")
        # Default to False if error
        return {term: False for term in terms}

def cleanup_term_basic(term):
    if not term: return term
    
    # Remove POS
    pos_terms = [
        'Adjective', 'adj.', 'Noun', 'noun', 'Verb', 'verb', 'Adverb', 'adv.', 'Pronoun', 'pron.',
        'Adjektiivi', 'Substantiivi', 'Verbi', 'Adverbi', 'Pronomini', 'Numeraali', 'Partikkeli',
        'Prepositio', 'Postpositio', 'Konjunktio', 'Huudahdussana', 'subst.', 'v.'
    ]
    pos_pattern = r'^(' + '|'.join([re.escape(t) for t in pos_terms]) + r')(\.?)\s+'
    term = re.sub(pos_pattern, '', term, flags=re.IGNORECASE).strip()
    
    # Handle IPA junk
    if ' ' in term:
        parts = term.split(' ', 1)
        if parts[1].startswith("'") or re.search(r'[ɑʋɛɪɔʊæøœʉɟʝɲŋʃʒθðɬɮɹɻɥɰʁ]', parts[1]):
            term = parts[0]
            
    term = term.replace('ˈ', '').replace('ˌ', '')
    term = re.sub(r'\[.*?\]', '', term)
    term = re.sub(r'\(.*?\)', '', term)
    term = term.strip(" '\"[]()").strip()
    
    return term

async def cleanup_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, term, passed, failed FROM cards WHERE language = 'finnish'")
    rows = cursor.fetchall()
    
    print(f"Processing {len(rows)} Finnish cards...")
    
    # First pass: Basic cleaning and grouping for LLM check
    to_check = []
    card_map = {}
    
    for card_id, term, passed, failed in rows:
        clean = cleanup_term_basic(term)
        if clean:
            card_map[card_id] = {'original': term, 'clean': clean, 'passed': passed, 'failed': failed}
            to_check.append(clean)

    # Dedup check list
    unique_to_check = list(set(to_check))
    proper_noun_map = {}
    
    # Process in batches for LLM
    batch_size = 50
    for i in range(0, len(unique_to_check), batch_size):
        batch = unique_to_check[i:i+batch_size]
        print(f"Checking proper nouns batch {i//batch_size + 1}...")
        results = await check_proper_nouns(batch)
        proper_noun_map.update(results)

    # Final pass: Apply capitalization rules
    for card_id, data in card_map.items():
        clean = data['clean']
        is_proper = proper_noun_map.get(clean, False) or proper_noun_map.get(clean.capitalize(), False)
        
        if is_proper:
            final_term = clean[0].upper() + clean[1:] if clean else ""
        else:
            final_term = clean.lower()
            
        if final_term != data['original']:
            # Check for collisions
            cursor.execute("SELECT id, passed, failed FROM cards WHERE language = 'finnish' AND term = ? AND id != ?", (final_term, card_id))
            collision = cursor.fetchone()
            
            if collision:
                collision_id, c_passed, c_failed = collision
                cursor.execute("UPDATE cards SET passed = ?, failed = ? WHERE id = ?", ((data['passed'] or 0) + (c_passed or 0), (data['failed'] or 0) + (c_failed or 0), collision_id))
                cursor.execute("DELETE FROM cards WHERE id = ?", (card_id,))
                # print(f"Merged: '{data['original']}' -> '{final_term}'")
            else:
                try:
                    cursor.execute("UPDATE cards SET term = ? WHERE id = ?", (final_term, card_id))
                    # print(f"Fixed: '{data['original']}' -> '{final_term}'")
                except sqlite3.IntegrityError:
                    pass

    conn.commit()
    conn.close()
    print("Finnish cleanup complete.")

if __name__ == "__main__":
    asyncio.run(cleanup_database())

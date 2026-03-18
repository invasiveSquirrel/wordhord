import sqlite3
import re

DB_PATH = "/home/chris/wordhord/wordhord.db"

# List of German countries/regions that MUST have articles
COUNTRIES_WITH_ARTICLES = {
    "Schweiz": "Die Schweiz",
    "Niederlande": "Die Niederlande",
    "Türkei": "Die Türkei",
    "USA": "Die USA",
    "Iran": "Der Iran",
    "Irak": "Der Irak",
    "Libanon": "Der Libanon",
    "Ukraine": "Die Ukraine",
    "Slowakei": "Die Slowakei",
    "Mongolei": "Die Mongolei",
    "Philippinen": "Die Philippinen",
    "Vatikan": "Der Vatikan",
    "Sudan": "Der Sudan",
    "Tschad": "Der Tschad",
    "Kongo": "Der Kongo",
}

def fix_german():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, term, part_of_speech, translation FROM cards WHERE language = 'german'")
    rows = cursor.fetchall()
    
    for card_id, term, pos, translation in rows:
        new_term = term
        
        # 1. Restore country articles
        # Check if the term is in our country list (either exactly or as a base)
        base_term = term
        # Remove existing article if any to check base
        match_article = re.match(r'^(Der|Die|Das)\s+(.*)', term, re.I)
        if match_article:
            base_term = match_article.group(2)
            
        if base_term in COUNTRIES_WITH_ARTICLES:
            new_term = COUNTRIES_WITH_ARTICLES[base_term]
        else:
            # 2. Capitalization: Nouns capitalized, others lowercased
            is_noun = False
            if pos:
                p = pos.lower()
                if 'noun' in p or 'substantiv' in p:
                    is_noun = True
            
            # Heuristic if POS is missing: starts with Der/Die/Das or a known noun pattern?
            # But the user directive is "Only German NOUNS are capitalized".
            
            if is_noun:
                # Ensure capitalized
                if new_term:
                    new_term = new_term[0].upper() + new_term[1:]
            else:
                # Lowercase verbs, adjectives, etc.
                # Except if it's a fixed phrase? User said "Only German NOUNS are capitalized".
                if new_term:
                    # Don't lowercase if it's already a country with an article we just fixed
                    if base_term not in COUNTRIES_WITH_ARTICLES:
                        new_term = new_term[0].lower() + new_term[1:]

        if new_term != term:
            # Check for collisions
            cursor.execute("SELECT id FROM cards WHERE language = 'german' AND term = ? AND id != ?", (new_term, card_id))
            collision = cursor.fetchone()
            if collision:
                # Merge or delete duplicate
                cursor.execute("DELETE FROM cards WHERE id = ?", (card_id,))
                # print(f"Merged duplicate: {term} -> {new_term}")
            else:
                cursor.execute("UPDATE cards SET term = ? WHERE id = ?", (new_term, card_id))
                # print(f"Fixed: {term} -> {new_term}")

    conn.commit()
    conn.close()
    print("German capitalization and country articles fixed.")

if __name__ == "__main__":
    fix_german()

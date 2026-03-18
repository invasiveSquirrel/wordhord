import re
import sqlite3
import json

DB_PATH = "/home/chris/wordhord/wordhord.db"
FILE_PATH = "/home/chris/vocabulary_sources/portuguese_freq.txt"
OUT_PATH = "/home/chris/wordhord/pt_words.json"

def extract_words():
    with open(FILE_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    words = set()
    
    # Heuristic 1: "327\nfalta nf lack"
    # Heuristic 2: "coelho 3674 M rabbit"
    
    pos_tags = {'nm', 'nf', 'nc', 'v', 'adj', 'adv', 'conj', 'prep', 'pron', 'num'}
    
    for i in range(len(lines)):
        line = lines[i].strip()
        if not line: continue
        
        parts = line.split()
        if len(parts) >= 2:
            first_word = parts[0].lower()
            # Clean first word
            first_word = re.sub(r'[^a-zãáâêéíóôõúç]', '', first_word)
            
            if not first_word or len(first_word) < 2:
                continue
                
            # Check if second part is a POS tag or a number (rank)
            second_part = parts[1].lower()
            if second_part in pos_tags or second_part.isdigit():
                words.add(first_word)
                
    print(f"Extracted {len(words)} potential words.")
    
    # Filter against DB
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT term FROM cards WHERE language = 'portuguese'")
    existing = set(row[0].lower() for row in cursor.fetchall())
    conn.close()
    
    missing = list(words - existing)
    print(f"Found {len(missing)} words not in database.")
    
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(missing, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    extract_words()

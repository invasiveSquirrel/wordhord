import re
import sqlite3
import json
import os

DB_PATH = "/home/chris/wordhord/wordhord.db"

FILES = {
    'portuguese': '/home/chris/vocabulary_sources/portuguese_freq.txt',
    'german_sources': [
        '/home/chris/wordhord/german_a1_b2.txt',
        '/home/chris/wordhord/german_using_vocab.txt',
        '/home/chris/wordhord/german_freq.txt'
    ],
    'spanish': '/home/chris/wordhord/spanish_vocab.txt',
    'dutch': '/home/chris/wordhord/dutch_freq.txt',
    'swedish_sources': [
        '/home/chris/wordhord/swedish_freq.txt',
        '/home/chris/vocabulary_sources/swedish_source.txt'
    ],
    'finnish_sources': [
        '/home/chris/wordhord/finnish_kauderwelsch.txt',
        '/home/chris/wordhord/finnish_freq.txt',
        '/home/chris/wordhord/finnish_200.txt',
        '/home/chris/vocabulary_sources/finnish_source.txt',
        '/home/chris/wordhord/finnish_eng_freq.txt',
        '/home/chris/wordhord/finnish_source_combined.txt'
    ]
}

def extract_from_file(lang, path):
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return []
        
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    words = set()
    
    if 'german' in lang:
        matches = re.findall(r'\b(die|der|das)\s+([A-ZÄÖÜ][a-zäöüß]+)', content)
        for m in matches: words.add(f"{m[0]} {m[1]}")
        matches = re.findall(r'\b([A-ZÄÖÜ][a-zäöüß]{2,})\b', content)
        for m in matches: words.add(m)
        matches = re.findall(r'\b([a-zäöüß]{3,})\b', content)
        for m in matches: words.add(m)
    elif lang == 'spanish':
        matches = re.findall(r'\b([a-zñáéíóúü]{3,})\b', content, re.I)
        for m in matches: words.add(m.lower())
    elif lang == 'swedish':
        matches = re.findall(r'\b([a-zåäö]{3,})\b', content, re.I)
        for m in matches: words.add(m.lower())
    elif lang == 'finnish':
        # Finnish extraction
        # Basic Finnish words are a-z, ä, ö
        matches = re.findall(r'\b([a-zäö]{3,})\b', content, re.I)
        for m in matches: words.add(m.lower())
    else:
        matches = re.findall(r'\b([a-zãáâêéíóôõúç]{3,})\b', content, re.I)
        for m in matches: words.add(m.lower())
            
    return list(words)

def main():
    all_missing = {}
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for lang_key, paths in FILES.items():
        lang = lang_key.split('_')[0]
        
        if isinstance(paths, str):
            paths = [paths]
            
        combined_words = set()
        for path in paths:
            combined_words.update(extract_from_file(lang, path))
            
        cursor.execute("SELECT term FROM cards WHERE language = ?", (lang,))
        existing = set(row[0].lower() for row in cursor.fetchall())
        
        missing = [w for w in combined_words if w.lower() not in existing]
        print(f"Found {len(missing)} {lang} words not in database from {len(paths)} sources.")
        all_missing[lang] = missing
        
    conn.close()
    with open("/home/chris/wordhord/missing_vocab.json", "w", encoding="utf-8") as f:
        json.dump(all_missing, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()

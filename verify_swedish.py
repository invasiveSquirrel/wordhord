#!/usr/bin/env python3
import sqlite3

DB_PATH = "/home/chris/wordhord/wordhord.db"

def verify():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT term, ipa, tone, part_of_speech, gender, conjugations, example, example_translation FROM cards WHERE language = 'swedish' LIMIT 100")
    rows = cursor.fetchall()
    
    print(f"{'Term':<20} | {'IPA':<15} | {'Tone':<5} | {'PoS':<10} | {'Example':<30}")
    print("-" * 90)
    for row in rows:
        term, ipa, tone, pos, gender, conj, ex, ex_trans = row
        print(f"{str(term):<20} | {str(ipa):<15} | {str(tone):<5} | {str(pos):<10} | {str(ex)[:30]:<30}")
    
    conn.close()

if __name__ == "__main__":
    verify()

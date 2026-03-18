import sqlite3

DB_PATH = "/home/chris/wordhord/wordhord.db"

def lowercase_existing():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for lang in ['portuguese', 'spanish']:
        cursor.execute("SELECT id, term, passed, failed FROM cards WHERE language = ?", (lang,))
        rows = cursor.fetchall()
        print(f"Lowercasing {len(rows)} {lang} terms...")
        
        for card_id, term, passed, failed in rows:
            if not term: continue
            new_term = term.lower()
            
            if new_term != term:
                # Check for collision
                cursor.execute("SELECT id, passed, failed FROM cards WHERE language = ? AND term = ? AND id != ?", (lang, new_term, card_id))
                collision = cursor.fetchone()
                
                if collision:
                    c_id, c_passed, c_failed = collision
                    # Merge progress
                    cursor.execute("UPDATE cards SET passed = ?, failed = ? WHERE id = ?", 
                                 ((passed or 0) + (c_passed or 0), (failed or 0) + (c_failed or 0), c_id))
                    cursor.execute("DELETE FROM cards WHERE id = ?", (card_id,))
                else:
                    try:
                        cursor.execute("UPDATE cards SET term = ? WHERE id = ?", (new_term, card_id))
                    except sqlite3.IntegrityError:
                        pass
        conn.commit()
    conn.close()
    print("Lowercasing complete.")

if __name__ == "__main__":
    lowercase_existing()

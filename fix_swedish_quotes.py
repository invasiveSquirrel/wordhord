import sqlite3

DB_PATH = "/home/chris/wordhord/wordhord.db"

def fix_swedish_quotes():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check for Swedish terms starting with '
    cursor.execute("SELECT id, term FROM cards WHERE language = 'swedish' AND term LIKE \"'%\"")
    rows = cursor.fetchall()
    print(f"Found {len(rows)} Swedish terms starting with a single quote.")
    
    for card_id, term in rows:
        # Strip the leading quote
        new_term = term.lstrip("'")
        
        # Capitalize first letter (standard for this app)
        if new_term:
            new_term = new_term[0].upper() + new_term[1:]
        
        if new_term != term:
            # Check for collisions
            cursor.execute("SELECT id FROM cards WHERE language = 'swedish' AND term = ? AND id != ?", (new_term, card_id))
            collision = cursor.fetchone()
            if collision:
                # Merge or delete duplicate
                cursor.execute("DELETE FROM cards WHERE id = ?", (card_id,))
                print(f"Merged duplicate: {term} -> {new_term}")
            else:
                cursor.execute("UPDATE cards SET term = ? WHERE id = ?", (new_term, card_id))
                print(f"Fixed: {term} -> {new_term}")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    fix_swedish_quotes()

# retrain.py — Automated retraining pipeline
# Reads coder corrections and updates the learned_synonyms table
# Run this periodically (weekly or after every N corrections)

import psycopg2
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()

DB_URL = os.getenv("DATABASE_URL") + "?sslmode=require"

def run_retraining():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # Get all edit corrections that haven't been learned yet
    cur.execute("""
        SELECT 
            c.correction_id,
            c.corrected_icd_code,
            s.extracted_text
        FROM corrections c
        JOIN suggestions s ON s.suggestion_id = c.suggestion_id
        WHERE c.correction_type = 'edit'
        AND c.corrected_icd_code IS NOT NULL
        AND c.correction_id NOT IN (
            SELECT learned_from_correction_id 
            FROM learned_synonyms 
            WHERE learned_from_correction_id IS NOT NULL
        )
    """)

    corrections = cur.fetchall()
    learned = 0
    skipped = 0

    for correction_id, icd_code, phrase in corrections:
        if not phrase or not icd_code:
            skipped += 1
            continue

        phrase = phrase.lower().strip()

        # Check if this phrase is already in learned_synonyms
        cur.execute("""
            SELECT 1 FROM learned_synonyms 
            WHERE phrase = %s AND icd_code = %s
        """, (phrase, icd_code))

        if cur.fetchone():
            skipped += 1
            continue

        # Add to learned_synonyms
        cur.execute("""
            INSERT INTO learned_synonyms (phrase, icd_code, learned_from_correction_id, created_at)
            VALUES (%s, %s, %s, %s)
        """, (phrase, icd_code, correction_id, datetime.utcnow()))

        learned += 1

    conn.commit()
    cur.close()
    conn.close()

    print(f"Retraining complete. Learned: {learned}, Skipped: {skipped}")
    return {"learned": learned, "skipped": skipped}

if __name__ == "__main__":
    run_retraining()
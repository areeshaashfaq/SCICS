import pandas as pd
import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

# Load CSV
df = pd.read_csv("icd10_2019.csv")

# Clean up the chapter column (has \r\n in it)
df['chapter'] = df['chapter'].str.replace(r'\r\n', ' ', regex=True).str.strip()
df['domain'] = df['domain'].str.replace(r'\r\n', ' ', regex=True).str.strip()

# Connect to Supabase
conn = psycopg2.connect(os.getenv("DATABASE_URL") + "?sslmode=require")
cur = conn.cursor()

inserted = 0
skipped = 0

for _, row in df.iterrows():
    try:
        cur.execute("""
            INSERT INTO icd_codes (icd_code, description, chapter, category)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (icd_code) DO NOTHING
        """, (
            str(row['sub-code']).strip(),
            str(row['definition']).strip(),
            str(row['chapter']).strip(),
            str(row['domain']).strip()
        ))
        inserted += 1
    except Exception as e:
        print(f"Error on {row['sub-code']}: {e}")
        skipped += 1

conn.commit()
cur.close()
conn.close()

print(f"Done! Inserted: {inserted}, Skipped: {skipped}")
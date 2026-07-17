import pandas as pd
import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

df = pd.read_csv("Diagnosis.csv", sep='\t', encoding='utf-8', encoding_errors='replace')
df['Diagnosis_ID'] = df['Diagnosis_ID'].astype(str).str.strip()
df['Diagnosis'] = df['Diagnosis'].astype(str).str.strip()
df = df[df['Active'] == 1]

DB_URL = os.getenv("DATABASE_URL") + "?sslmode=require"

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

batch = []
inserted = 0

for _, row in df.iterrows():
    batch.append((row['Diagnosis_ID'], row['Diagnosis']))
    if len(batch) == 500:
        try:
            cur.executemany("""
                INSERT INTO icd_codes (icd_code, description)
                VALUES (%s, %s)
                ON CONFLICT (icd_code) DO NOTHING
            """, batch)
            conn.commit()
            inserted += len(batch)
            print(f"Inserted {inserted} rows...")
            batch = []
        except Exception as e:
            print(f"Batch error: {e}")
            conn = psycopg2.connect(DB_URL)
            cur = conn.cursor()
            batch = []

if batch:
    cur.executemany("""
        INSERT INTO icd_codes (icd_code, description)
        VALUES (%s, %s)
        ON CONFLICT (icd_code) DO NOTHING
    """, batch)
    conn.commit()
    inserted += len(batch)

cur.close()
conn.close()
print(f"Done! Inserted: {inserted}")
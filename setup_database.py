import argparse
import getpass
import os
import sys

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT = os.path.dirname(os.path.abspath(__file__))
SCHEMA_SQL = os.path.join(ROOT, "database", "schema.sql")
MIGRATIONS = os.path.join(ROOT, "database", "migrations")
DIAGNOSIS_CSV = os.path.join(ROOT, "Diagnosis.csv")
PROCEDURE_CSV = os.path.join(ROOT, "Procedure.csv")

BATCH = 2000


# ── connection ─────────────────────────────────────────────────────────────
def connect():
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        sys.exit(
            "DATABASE_URL is not set.\n"
            "Copy .env.example to .env and fill it in, then run this again."
        )
    try:
        return psycopg2.connect(url)
    except psycopg2.OperationalError as exc:
        sys.exit(f"Could not connect to the database:\n  {exc}")


def step(msg):
    print(f"\n── {msg}")


# ── 1. schema ──────────────────────────────────────────────────────────────
def create_schema(conn):
    step("Creating tables")
    with open(SCHEMA_SQL, encoding="utf-8") as fh:
        sql = fh.read()
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    print("   tables ready")


def run_migrations(conn):
    step("Applying migrations")
    if not os.path.isdir(MIGRATIONS):
        print("   none found")
        return
    files = sorted(f for f in os.listdir(MIGRATIONS) if f.endswith(".sql"))
    for name in files:
        with open(os.path.join(MIGRATIONS, name), encoding="utf-8") as fh:
            sql = fh.read()
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        print(f"   applied {name}")


# ── 2 & 3. ICD codes ───────────────────────────────────────────────────────
def _read_diagnoses():
    df = pd.read_csv(DIAGNOSIS_CSV, sep="\t", encoding="utf-8",
                     encoding_errors="replace", dtype=str)
    # Retired codes stay in SIUT's export with Active != 1. The NLP ignores
    # them, and loading them would let a retired code be saved as a correction.
    df = df[df["Active"].str.strip() == "1"]
    df["code"] = df["Diagnosis_ID"].astype(str).str.strip()
    df["desc"] = df["Diagnosis"].astype(str).str.strip()
    return df[["code", "desc"]]


def _read_procedures():
    df = pd.read_csv(PROCEDURE_CSV, encoding="utf-8-sig", dtype=str)
    df["code"] = df["ProcedureID"].astype(str).str.strip()
    df["desc"] = df["Procedures"].astype(str).str.strip()
    return df[["code", "desc"]]


def _clean(df):
    df = df[(df["code"] != "") & (df["code"].str.lower() != "nan")]
    df = df[(df["desc"] != "") & (df["desc"].str.lower() != "nan")]
    return df.drop_duplicates(subset=["code"])


def load_codes(conn, label, reader, path):
    step(f"Loading {label}")
    if not os.path.exists(path):
        print(f"   SKIPPED: {os.path.basename(path)} not found in the project folder")
        return 0
    df = _clean(reader())
    rows = list(df.itertuples(index=False, name=None))

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM icd_codes")
        before = cur.fetchone()[0]
        for i in range(0, len(rows), BATCH):
            execute_values(
                cur,
                "INSERT INTO icd_codes (icd_code, description) VALUES %s "
                "ON CONFLICT (icd_code) DO NOTHING",
                rows[i:i + BATCH],
            )
            done = min(i + BATCH, len(rows))
            print(f"\r   {done:,} / {len(rows):,}", end="", flush=True)
        cur.execute("SELECT COUNT(*) FROM icd_codes")
        after = cur.fetchone()[0]
    conn.commit()
    print(f"\n   {after - before:,} added ({len(rows) - (after - before):,} already present)")
    return after - before


# ── 4. accounts ────────────────────────────────────────────────────────────
def _hash(password):
    """Hash exactly the way the backend verifies logins."""
    try:
        sys.path.insert(0, ROOT)
        from routers.auth import hash_password
        return hash_password(password)
    except Exception:
        import bcrypt
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _ask_password(username):
    while True:
        pw = getpass.getpass(f"   password for '{username}': ")
        if len(pw) < 8 or not any(c.isupper() for c in pw) or not any(c.isdigit() for c in pw):
            print("   needs 8+ characters, one capital letter and one number")
            continue
        if getpass.getpass("   confirm: ") != pw:
            print("   passwords did not match")
            continue
        return pw


def create_users(conn):
    step("Creating accounts")
    with conn.cursor() as cur:
        cur.execute("SELECT username FROM users")
        existing = {r[0] for r in cur.fetchall()}

    wanted = [("admin", "Administrator", "admin"), ("coder", "Coder", "coder")]
    for username, name, role in wanted:
        if username in existing:
            print(f"   '{username}' already exists, leaving it")
            continue
        pw = _ask_password(username)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, password_hash, name, role) "
                "VALUES (%s, %s, %s, %s)",
                (username, _hash(pw), name, role),
            )
        conn.commit()
        print(f"   created '{username}' ({role})")


# ── report ─────────────────────────────────────────────────────────────────
def check(conn):
    step("Current state")
    tables = ["icd_codes", "documents", "suggestions", "corrections",
              "chat_messages", "learned_synonyms", "retraining_batches", "users"]
    with conn.cursor() as cur:
        for t in tables:
            cur.execute("SELECT to_regclass(%s)", (f"public.{t}",))
            if cur.fetchone()[0] is None:
                print(f"   {t:<20} MISSING")
                continue
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            print(f"   {t:<20} {cur.fetchone()[0]:>8,} rows")

        cur.execute("SELECT to_regclass('public.icd_codes')")
        if cur.fetchone()[0]:
            # Spot-check a code from each system the NLP relies on.
            for code in ("E11.9", "K27.9", "0DB98ZX", "30233N1"):
                cur.execute("SELECT 1 FROM icd_codes WHERE icd_code = %s", (code,))
                print(f"   {code:<20} {'present' if cur.fetchone() else 'MISSING'}")


# ── main ───────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="report only, change nothing")
    ap.add_argument("--migrate", action="store_true", help="upgrade an existing database")
    ap.add_argument("--no-users", action="store_true", help="skip creating accounts")
    args = ap.parse_args()

    conn = connect()
    try:
        if args.check:
            check(conn)
            return
        if args.migrate:
            run_migrations(conn)
            check(conn)
            return

        create_schema(conn)
        load_codes(conn, "diagnosis codes (ICD-10-CM)", _read_diagnoses, DIAGNOSIS_CSV)
        load_codes(conn, "procedure codes (ICD-10-PCS)", _read_procedures, PROCEDURE_CSV)
        if not args.no_users:
            create_users(conn)
        check(conn)
        print("\nDone. Start the backend with:  uvicorn main:app --port 8000")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
"""
load_procedure_codes.py — put the ICD-10-PCS codes into the icd_codes table.

Why this is needed
------------------
suggestions.icd_code has a foreign key onto icd_codes. That table was loaded
from Diagnosis.csv only, so every procedure code the NLP produces (0DB98ZX,
30233N1, 009U3ZX ...) is rejected on insert:

    ForeignKeyViolation: Key (icd_code)=(30233N1) is not present in icd_codes

Which means procedure coding cannot reach the database at all, no matter how
well the matcher works. This loads Procedure.csv into the same table so those
codes become insertable.

Usage
-----
    python load_procedure_codes.py --inspect     show table shape and counts
    python load_procedure_codes.py --dry-run     report what would be inserted
    python load_procedure_codes.py --load        insert the missing codes

Existing rows are never modified: only codes absent from the table are added.
"""

import argparse
import os
import sys

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

PROC_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Procedure.csv")


def get_engine():
    url = os.getenv("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL not found. Check your .env file.")
    if "sslmode" not in url:
        url += ("&" if "?" in url else "?") + "sslmode=require"
    return create_engine(url)


def table_columns(conn):
    """Column name -> (data_type, is_nullable, has_default)."""
    rows = conn.execute(text("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = 'icd_codes'
        ORDER BY ordinal_position
    """)).fetchall()
    return {r.column_name: (r.data_type, r.is_nullable == "YES", r.column_default is not None)
            for r in rows}


def read_procedures():
    df = pd.read_csv(PROC_CSV, encoding="utf-8-sig", dtype=str)
    df["code"] = df["ProcedureID"].astype(str).str.strip()
    df["desc"] = df["Procedures"].astype(str).str.strip()
    df = df[(df["code"] != "") & (df["code"].str.lower() != "nan")]
    return df[["code", "desc"]].drop_duplicates(subset=["code"])


def cmd_inspect(conn):
    cols = table_columns(conn)
    print("\nicd_codes columns:")
    for name, (dtype, nullable, default) in cols.items():
        flags = []
        if not nullable and not default:
            flags.append("REQUIRED")
        if default:
            flags.append("has default")
        print(f"  {name:<24} {dtype:<20} {' '.join(flags)}")

    total = conn.execute(text("SELECT COUNT(*) FROM icd_codes")).scalar()
    print(f"\nrows in icd_codes: {total:,}")

    df = read_procedures()
    print(f"codes in Procedure.csv: {len(df):,}")

    existing = {r[0] for r in conn.execute(text("SELECT icd_code FROM icd_codes")).fetchall()}
    missing = [c for c in df["code"] if c not in existing]
    print(f"missing from icd_codes: {len(missing):,}")
    if missing:
        print(f"  examples: {missing[:6]}")

    # The codes our matcher actually emits — these are the ones that matter now.
    known = ["0DB78ZX", "0DB98ZX", "0DBB8ZX", "0DBH8ZX",
             "0B9C8ZX", "0B9J8ZX", "0W993ZX", "009U3ZX", "30233N1"]
    print("\nprocedure codes the NLP emits:")
    for c in known:
        print(f"  {c}  {'present' if c in existing else 'MISSING'}")


def cmd_load(conn, dry_run):
    cols = table_columns(conn)
    if "icd_code" not in cols:
        sys.exit("icd_codes has no icd_code column — check the table name.")

    desc_col = "description" if "description" in cols else None
    if desc_col is None:
        sys.exit("icd_codes has no description column — cannot map Procedures text.")

    # Any other column that is NOT NULL and has no default would block the
    # insert, so surface it rather than failing halfway through.
    blocking = [
        name for name, (_, nullable, default) in cols.items()
        if not nullable and not default and name not in ("icd_code", desc_col)
    ]
    if blocking:
        print(f"\nThese columns are required but not supplied: {blocking}")
        print("Tell me their meaning and I'll extend the script.")
        return

    df = read_procedures()
    existing = {r[0] for r in conn.execute(text("SELECT icd_code FROM icd_codes")).fetchall()}
    to_add = df[~df["code"].isin(existing)]

    print(f"\n{len(df):,} codes in Procedure.csv, {len(to_add):,} not yet in icd_codes.")
    if to_add.empty:
        print("Nothing to do.")
        return

    if dry_run:
        print("\nwould insert, first 10:")
        for _, r in to_add.head(10).iterrows():
            print(f"  {r['code']:<10} {r['desc'][:60]}")
        return

    inserted = 0
    try:
        for _, r in to_add.iterrows():
            conn.execute(
                text(f"INSERT INTO icd_codes (icd_code, {desc_col}) "
                     f"VALUES (:code, :desc) ON CONFLICT (icd_code) DO NOTHING"),
                {"code": r["code"], "desc": r["desc"]},
            )
            inserted += 1
        conn.commit()
        print(f"Inserted {inserted:,} procedure codes.")
    except Exception as exc:
        conn.rollback()
        print(f"Insert failed, nothing changed: {exc}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inspect", action="store_true", help="show table shape and counts")
    ap.add_argument("--dry-run", action="store_true", help="report what would be inserted")
    ap.add_argument("--load", action="store_true", help="insert the missing codes")
    args = ap.parse_args()

    engine = get_engine()
    with engine.connect() as conn:
        if args.inspect:
            cmd_inspect(conn)
        elif args.load or args.dry_run:
            cmd_load(conn, args.dry_run)
        else:
            ap.print_help()


if __name__ == "__main__":
    main()
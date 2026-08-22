"""
reprocess.py — run the NLP pipeline locally and write suggestions to Supabase.

Why this exists
---------------
Uploading through Railway runs the NLP inside the container, which exceeds the
memory allocation and returns 502. Your laptop has no such limit. This script
does exactly what POST /documents/ does, but from here: reads each document's
raw_text out of the database, runs match_all_from_text on it, and writes the
suggestions back. Railway serves the same Supabase database, so the results
appear in the app immediately.

Usage
-----
    python reprocess.py --list                 show every document and its counts
    python reprocess.py --dry-run              process everything, write nothing
    python reprocess.py --all                  process documents that have none
    python reprocess.py --all --force          reprocess everything, replacing old
    python reprocess.py --ids 7 9 11           only these documents
    python reprocess.py --delete-empty         remove documents with no suggestions

Existing suggestions are only removed with --force, and only for the documents
being reprocessed. Coder decisions on those rows go with them, which is why it
asks before doing it.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "nlp"))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()


def get_engine():
    url = os.getenv("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL not found. Check your .env file.")
    if "sslmode" not in url:
        url += ("&" if "?" in url else "?") + "sslmode=require"
    return create_engine(url)


def fetch_documents(conn, ids=None):
    if ids:
        rows = conn.execute(text("""
            SELECT d.document_id, d.patient_ref, d.source_filename, d.raw_text,
                   COUNT(s.suggestion_id) AS n
            FROM documents d
            LEFT JOIN suggestions s ON s.document_id = d.document_id
            WHERE d.document_id = ANY(:ids)
            GROUP BY d.document_id
            ORDER BY d.document_id
        """), {"ids": ids}).fetchall()
    else:
        rows = conn.execute(text("""
            SELECT d.document_id, d.patient_ref, d.source_filename, d.raw_text,
                   COUNT(s.suggestion_id) AS n
            FROM documents d
            LEFT JOIN suggestions s ON s.document_id = d.document_id
            GROUP BY d.document_id
            ORDER BY d.document_id
        """)).fetchall()
    return rows


def cmd_list(conn):
    rows = fetch_documents(conn)
    print(f"\n{'id':>4}  {'patient_ref':<16} {'filename':<20} {'suggestions':>11}  chars")
    print("-" * 70)
    for r in rows:
        print(f"{r.document_id:>4}  {(r.patient_ref or '—'):<16} "
              f"{(r.source_filename or '—'):<20} {r.n:>11}  {len(r.raw_text or '')}")
    empty = [r.document_id for r in rows if r.n == 0]
    print(f"\n{len(rows)} documents, {len(empty)} with no suggestions: {empty or 'none'}")


def insert_suggestions(conn, document_id, entities):
    """Mirrors the INSERT in routers/documents.py so both paths agree."""
    for ent in entities:
        conn.execute(text("""
            INSERT INTO suggestions (
                document_id, suggestion_type, extracted_text,
                icd_code, confidence_score,
                source_char_start, source_char_end, source_snippet,
                is_ambiguous, ambiguity_reason
            ) VALUES (
                :document_id, :suggestion_type, :extracted_text,
                :icd_code, :confidence_score,
                :source_char_start, :source_char_end, :source_snippet,
                :is_ambiguous, :ambiguity_reason
            )
        """), {
            "document_id":       document_id,
            "suggestion_type":   ent.get("suggestion_type", "diagnosis_associative"),
            "extracted_text":    ent.get("extracted_text", ""),
            "icd_code":          ent.get("icd_code"),
            "confidence_score":  ent.get("confidence_score"),
            "source_char_start": ent.get("source_char_start", 0),
            "source_char_end":   ent.get("source_char_end", 0),
            "source_snippet":    ent.get("source_snippet", ""),
            "is_ambiguous":      ent.get("is_ambiguous", False),
            "ambiguity_reason":  ent.get("ambiguity_reason", ""),
        })


def cmd_process(conn, ids, force, dry_run):
    from fuzzy_match_icd import match_all_from_text

    rows = fetch_documents(conn, ids)
    if not rows:
        print("No matching documents.")
        return

    targets = [r for r in rows if force or r.n == 0]
    skipped = [r for r in rows if not force and r.n > 0]

    for r in skipped:
        print(f"  skip  doc {r.document_id} — already has {r.n} suggestions (use --force to replace)")

    if not targets:
        print("\nNothing to do.")
        return

    replacing = [r for r in targets if r.n > 0]
    if replacing and not dry_run:
        total = sum(r.n for r in replacing)
        print(f"\n--force will DELETE {total} existing suggestions on documents "
              f"{[r.document_id for r in replacing]}, including any coder decisions on them.")
        if input("Type 'yes' to continue: ").strip().lower() != "yes":
            print("Cancelled.")
            return

    print()
    grand_total = 0
    for r in targets:
        if not (r.raw_text or "").strip():
            print(f"  skip  doc {r.document_id} — empty raw_text")
            continue

        label = f"doc {r.document_id} ({r.patient_ref or r.source_filename or '—'})"
        try:
            entities = match_all_from_text(r.raw_text)
        except Exception as exc:
            print(f"  FAIL  {label} — NLP error: {exc}")
            continue

        coded = sum(1 for e in entities if e.get("icd_code"))
        grand_total += len(entities)

        if dry_run:
            print(f"  would write {len(entities):>3} suggestions ({coded} coded)  {label}")
            continue

        # One commit per document: a failure mid-write rolls that document
        # back rather than leaving it half-populated. SQLAlchemy 2.x opens the
        # transaction itself on first execute, so we commit/rollback directly
        # instead of calling begin().
        try:
            if r.n > 0:
                conn.execute(text("DELETE FROM suggestions WHERE document_id = :d"),
                             {"d": r.document_id})
            insert_suggestions(conn, r.document_id, entities)
            conn.commit()
            print(f"  wrote {len(entities):>3} suggestions ({coded} coded)  {label}")
        except Exception as exc:
            conn.rollback()
            print(f"  FAIL  {label} — write error: {exc}")

    verb = "would write" if dry_run else "wrote"
    print(f"\n{verb} {grand_total} suggestions across {len(targets)} documents.")


def cmd_delete_empty(conn):
    rows = fetch_documents(conn)
    empty = [r for r in rows if r.n == 0]
    if not empty:
        print("No empty documents.")
        return

    print("\nThese documents have no suggestions:")
    for r in empty:
        print(f"  {r.document_id:>4}  {(r.patient_ref or '—'):<16} {r.source_filename or '—'}")
    print(f"\nThis permanently deletes {len(empty)} documents.")
    if input("Type 'delete' to confirm: ").strip().lower() != "delete":
        print("Cancelled.")
        return

    ids = [r.document_id for r in empty]
    try:
        # Children first — chat and corrections reference documents.
        conn.execute(text("DELETE FROM chat_messages WHERE document_id = ANY(:ids)"), {"ids": ids})
        conn.execute(text("DELETE FROM corrections   WHERE document_id = ANY(:ids)"), {"ids": ids})
        conn.execute(text("DELETE FROM suggestions   WHERE document_id = ANY(:ids)"), {"ids": ids})
        conn.execute(text("DELETE FROM documents     WHERE document_id = ANY(:ids)"), {"ids": ids})
        conn.commit()
        print(f"Deleted {len(ids)} documents.")
    except Exception as exc:
        conn.rollback()
        print(f"Delete failed, nothing changed: {exc}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="show documents and counts")
    ap.add_argument("--all", action="store_true", help="process all documents")
    ap.add_argument("--ids", nargs="+", type=int, help="process only these document ids")
    ap.add_argument("--force", action="store_true", help="replace existing suggestions")
    ap.add_argument("--dry-run", action="store_true", help="show what would happen")
    ap.add_argument("--delete-empty", action="store_true",
                    help="delete documents that have no suggestions")
    args = ap.parse_args()

    engine = get_engine()
    with engine.connect() as conn:
        if args.list:
            cmd_list(conn)
        elif args.delete_empty:
            cmd_delete_empty(conn)
        elif args.all or args.ids:
            cmd_process(conn, args.ids, args.force, args.dry_run)
        else:
            ap.print_help()


if __name__ == "__main__":
    main()
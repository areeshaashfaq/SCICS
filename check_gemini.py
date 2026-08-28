"""
check_gemini.py — confirm the Gemini key works and show which models it can use.

Free-tier model IDs change often enough that hardcoding one is a liability.
This asks Google what this key can actually reach, then sends one real request
so you know the whole path works before wiring it into the chatbot.

    python check_gemini.py
"""

import os
import sys

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

KEY = os.getenv("GEMINI_API_KEY", "").strip()
BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def main():
    if not KEY:
        sys.exit("GEMINI_API_KEY not set. Add it to your .env file.")

    print(f"key loaded, {len(KEY)} characters\n")

    # 1. What can this key see?
    try:
        r = requests.get(BASE, headers={"x-goog-api-key": KEY}, timeout=20)
        r.raise_for_status()
    except Exception as exc:
        sys.exit(f"Could not list models: {exc}")

    models = [
        m["name"].replace("models/", "")
        for m in r.json().get("models", [])
        if "generateContent" in m.get("supportedGenerationMethods", [])
    ]
    flash = sorted(m for m in models if "flash" in m and "preview" not in m)

    print(f"{len(models)} models support generateContent")
    print("\nflash models (the ones worth using here):")
    for m in flash[:12]:
        print(f"  {m}")

    # 2. Does the configured model actually answer?
    chosen = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
    print(f"\ntesting GEMINI_MODEL = {chosen}")
    if chosen not in models:
        print(f"  WARNING: {chosen} is not in the list above.")
        if flash:
            print(f"  Set GEMINI_MODEL={flash[0]} in .env instead.")

    try:
        r = requests.post(
            f"{BASE}/{chosen}:generateContent",
            headers={"Content-Type": "application/json", "x-goog-api-key": KEY},
            json={"contents": [{"parts": [{"text":
                  "Reply with exactly: Khidmat chat is working."}]}]},
            timeout=30,
        )
        if r.status_code == 429:
            sys.exit("  Rate limited (429). The key works; try again in a minute.")
        r.raise_for_status()
        parts = r.json()["candidates"][0]["content"]["parts"]
        print("  response:", "".join(p.get("text", "") for p in parts).strip())
        print("\nGemini path is working.")
    except Exception as exc:
        print(f"  FAILED: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()

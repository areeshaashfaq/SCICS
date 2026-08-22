"""
llm_client.py — the LLM half of the coding assistant's chat.

Why this exists
---------------
The chatbot answers code-specific questions from the database (deterministic,
always correct) and hands everything else to a language model. That model used
to be Ollama on localhost, which works on a developer machine and cannot work
on Railway: the container has neither Ollama installed nor the ~3GB of RAM
llama3.2 needs resident.

So the order is now Gemini first, Ollama second:

  * Gemini runs on Google's servers, so the deployed backend can use it and the
    container stays small.
  * Ollama is kept as a local fallback, which means the chat still works with
    no internet and no API key while developing.
  * If neither answers, the caller falls back to its rule-based reply. The chat
    never goes silent.

Configuration (environment, or .env)
------------------------------------
    GEMINI_API_KEY   required for the Gemini path
    GEMINI_MODEL     optional, defaults to gemini-2.5-flash
    OLLAMA_URL       optional, defaults to http://localhost:11434
    OLLAMA_MODEL     optional, defaults to llama3.2

Free-tier model IDs change; run `python check_gemini.py` to see what the key
can actually reach, then set GEMINI_MODEL if the default is unavailable.
"""

import os

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
GEMINI_URL     = "https://generativelanguage.googleapis.com/v1beta/models"

OLLAMA_URL   = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

# Enough for a coder's question; keeps latency and token use down.
MAX_OUTPUT_TOKENS = 2048

# A clinical tool must not invent codes. The model may explain and summarise,
# but producing the code list is the database's job, not the model's.
SYSTEM_RULES = (
    "You are a clinical ICD coding assistant supporting a professional coder. "
    "Only discuss ICD codes that appear in the ICD SUGGESTIONS list you are "
    "given. Never propose a code that is not in that list. If the question "
    "cannot be answered from the discharge summary and the suggestions, say so "
    "plainly rather than guessing. Be concise and specific, and quote the text "
    "evidence you are relying on."
)


def _ask_gemini(prompt, timeout=30):
    """Return the model's answer, or None if unavailable."""
    if not GEMINI_API_KEY:
        return None
    try:
        r = requests.post(
            f"{GEMINI_URL}/{GEMINI_MODEL}:generateContent",
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": GEMINI_API_KEY,
            },
            json={
                "system_instruction": {"parts": [{"text": SYSTEM_RULES}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "maxOutputTokens": MAX_OUTPUT_TOKENS,
                    "temperature": 0.2,
                },
            },
            timeout=timeout,
        )
        if r.status_code == 429:
            print("[llm] Gemini rate limit reached, falling back")
            return None
        r.raise_for_status()
        data = r.json()
        parts = data["candidates"][0]["content"]["parts"]
        answer = "".join(p.get("text", "") for p in parts).strip()
        return answer or None
    except Exception as exc:
        print(f"[llm] Gemini error: {exc}")
        return None


def _ask_ollama(prompt, timeout=120):
    """Local fallback. Absent on Railway, which is expected."""
    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": f"{SYSTEM_RULES}\n\n{prompt}",
                "stream": False,
                "options": {"num_predict": 300},
                "keep_alive": "10m",
            },
            timeout=timeout,
        )
        r.raise_for_status()
        return (r.json().get("response") or "").strip() or None
    except Exception as exc:
        print(f"[llm] Ollama error: {exc}")
        return None


def build_prompt(message, suggestions, raw_text):
    """Assemble the coder's question with the evidence the model may use."""
    sugg_context = "\n".join(
        f"- {s.get('icd_code', '?')} ({s.get('icd_description', '')}) - "
        f"found: \"{s.get('source_snippet', '')}\" - "
        f"confidence: {int((s.get('confidence_score') or 0) * 100)}%"
        for s in (suggestions or [])[:10]
    ) or "(no coded suggestions for this document)"

    return (
        f"DISCHARGE SUMMARY (excerpt):\n{(raw_text or '')[:1500]}\n\n"
        f"ICD SUGGESTIONS:\n{sugg_context}\n\n"
        f"CODER QUESTION: {message}"
    )


def ask_llm(message, suggestions, raw_text):
    """Gemini, then Ollama, then None so the caller can use its own fallback."""
    prompt = build_prompt(message, suggestions, raw_text)

    answer = _ask_gemini(prompt)
    if answer:
        return answer

    answer = _ask_ollama(prompt)
    if answer:
        return answer

    return None


def status():
    """Which backends are configured. Used by check_gemini.py."""
    return {
        "gemini_key_set": bool(GEMINI_API_KEY),
        "gemini_model":   GEMINI_MODEL,
        "ollama_url":     OLLAMA_URL,
        "ollama_model":   OLLAMA_MODEL,
    }

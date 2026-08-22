# api_client.py
import functools
import os
import requests

import fake_data

USE_FAKE = False
BASE_URL = "https://scics-production.up.railway.app"

# Every call used to end in a bare raise_for_status(). When the backend
# returned an error the exception travelled all the way up and closed the
# application, losing the coder's place in the document. Each function is now
# wrapped: on failure it shows a dialog, records the reason in LAST_ERROR and
# returns a safe empty value of the right type, so callers keep working.
LAST_ERROR = None


def _describe(exc):
    """Turn an exception into something a coder can act on."""
    if isinstance(exc, requests.Timeout):
        return "The server took too long to respond. Please try again."
    if isinstance(exc, requests.ConnectionError):
        return "Could not reach the server. Check your internet connection."
    response = getattr(exc, "response", None)
    if response is not None:
        detail = ""
        try:
            body = response.json()
            detail = body.get("detail", "") if isinstance(body, dict) else ""
        except Exception:
            detail = (response.text or "")[:200]
        if response.status_code >= 500:
            return f"Server error ({response.status_code}). {detail}".strip()
        return f"Request rejected ({response.status_code}). {detail}".strip()
    return str(exc)


def _show_dialog(message):
    """Best-effort popup. Never let the reporting itself raise."""
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox

        if QApplication.instance() is None:
            return
        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Khidmat")
        box.setText(message)
        box.exec()
    except Exception:
        pass


def _safe(default):
    """Catch network/HTTP failures and return `default` instead of crashing."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            global LAST_ERROR
            try:
                result = func(*args, **kwargs)
                LAST_ERROR = None
                return result
            except requests.RequestException as exc:
                LAST_ERROR = _describe(exc)
                print(f"[api_client] {func.__name__} failed: {LAST_ERROR}")
                _show_dialog(LAST_ERROR)
                return default() if callable(default) else default
        return wrapper
    return decorator


@_safe(list)
def get_documents():
    if USE_FAKE:
        return fake_data.get_documents()
    r = requests.get(f"{BASE_URL}/documents/", timeout=10)
    r.raise_for_status()
    return r.json().get("documents", [])


@_safe(list)
def get_suggestions(document_id: int):
    if USE_FAKE:
        return fake_data.get_suggestions(document_id)
    r = requests.get(f"{BASE_URL}/suggestions/documents/{document_id}", timeout=10)
    r.raise_for_status()
    return r.json().get("suggestions", [])


@_safe("")
def get_raw_text(document_id: int):
    # raw_text comes from the documents row — in real backend fetch it from get_documents()
    if USE_FAKE:
        return fake_data.get_raw_text(document_id)
    r = requests.get(f"{BASE_URL}/documents/", timeout=10)
    r.raise_for_status()
    docs = r.json().get("documents", [])
    match = next((d for d in docs if d["document_id"] == document_id), {})
    return match.get("raw_text", "")


@_safe(lambda: {"error": LAST_ERROR})
def submit_decision(suggestion_id: int, decision: str):
    # decision must be "approved" or "rejected"
    if USE_FAKE:
        return fake_data.submit_decision(suggestion_id, decision)
    r = requests.patch(
        f"{BASE_URL}/suggestions/{suggestion_id}",
        params={"decision": decision},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


@_safe(lambda: {"error": LAST_ERROR})
def submit_correction(suggestion_id: int, corrected_icd_code: str):
    if USE_FAKE:
        return fake_data.submit_correction(suggestion_id, corrected_icd_code)
    r = requests.post(
        f"{BASE_URL}/corrections/",
        json={"suggestion_id": suggestion_id, "corrected_icd_code": corrected_icd_code,
              "correction_type": "reclassified"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


@_safe(list)
def get_chat_history(document_id: int):
    if USE_FAKE:
        return fake_data.get_chat_history(document_id)
    r = requests.get(f"{BASE_URL}/chat/documents/{document_id}", timeout=10)
    r.raise_for_status()
    return r.json().get("messages", [])


@_safe(lambda: {"error": LAST_ERROR, "answer": "Sorry, I could not reach the server."})
def send_chat(document_id: int, message: str):
    if USE_FAKE:
        return fake_data.send_chat(document_id, message)
    # backend expects query params, not a JSON body
    r = requests.post(
        f"{BASE_URL}/chat/documents/{document_id}",
        params={"sender": "coder", "message_text": message},
        timeout=120,   # the LLM fallback can be slow on a cold model
    )
    r.raise_for_status()
    return r.json()


@_safe(lambda: {"error": "connection_failed", "message": LAST_ERROR})
def login(username: str, password: str):
    if USE_FAKE:
        return fake_data.login(username, password)
    r = requests.post(
        f"{BASE_URL}/auth/login",
        json={"username": username, "password": password},
        timeout=10,
    )
    if r.status_code == 401:
        return {"error": "invalid_credentials"}
    r.raise_for_status()
    return r.json()


@_safe(dict)
def get_analytics():
    if USE_FAKE:
        return fake_data.get_analytics()
    r = requests.get(f"{BASE_URL}/analytics/", timeout=10)
    r.raise_for_status()
    return r.json()


@_safe(list)
def get_corrections():
    if USE_FAKE:
        return fake_data.get_corrections()
    r = requests.get(f"{BASE_URL}/corrections/", timeout=10)
    r.raise_for_status()
    return r.json()


@_safe(lambda: {"error": LAST_ERROR})
def mark_complete(document_id: int):
    if USE_FAKE:
        return fake_data.mark_complete(document_id)
    r = requests.patch(f"{BASE_URL}/documents/{document_id}/complete", timeout=10)
    r.raise_for_status()
    return r.json()


@_safe(lambda: {"error": LAST_ERROR})
def upload_document(filepath: str, patient_ref: str = ""):
    if USE_FAKE:
        return fake_data.upload_document(filepath, patient_ref)
    with open(filepath, "rb") as f:
        r = requests.post(
            f"{BASE_URL}/documents/",
            files={"file": (os.path.basename(filepath), f, "text/plain")},
            params={"patient_ref": patient_ref},
            timeout=120,   # NLP pipeline takes time
        )
    r.raise_for_status()
    return r.json()
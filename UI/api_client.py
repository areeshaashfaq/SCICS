# api_client.py
import functools
import os

import requests

import json

import fake_data
import session

USE_FAKE = True

_DEFAULT_API_URL = "http://localhost:8000"
_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def _resolve_base_url():
    env = os.getenv("KHIDMAT_API_URL", "").strip()
    if env:
        return env.rstrip("/")
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as fh:
            url = str(json.load(fh).get("api_url", "")).strip()
            if url:
                return url.rstrip("/")
    except (OSError, ValueError):
        pass
    return _DEFAULT_API_URL


BASE_URL = _resolve_base_url()

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
        # Colours are literals here: api_client must not import the UI theme.
        box.setStyleSheet(
            "QMessageBox { background: #162230; }"
            "QLabel { color: #E8EDF2; font-size: 12px; }"
            "QPushButton { background: #1C2D3E; color: #E8EDF2;"
            " border: 1px solid #253D52; border-radius: 4px;"
            " padding: 5px 18px; min-width: 60px; }"
        )
        box.exec()
    except Exception:
        pass


def _safe(default, show_dialog=True):
    """Catch network/HTTP failures and return `default` instead of crashing.

    Loading calls pass show_dialog=False: the screen shows its own "couldn't
    reach the server" message instead, so a failed load never stacks popups.
    Actions the coder takes keep the popup so they know their click didn't save.
    """
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
                if show_dialog:
                    _show_dialog(LAST_ERROR)
                return default() if callable(default) else default
        return wrapper
    return decorator


@_safe(list, show_dialog=False)
def get_documents():
    if USE_FAKE:
        return fake_data.get_documents()
    r = requests.get(f"{BASE_URL}/documents/", timeout=10)
    r.raise_for_status()
    return r.json().get("documents", [])


@_safe(list, show_dialog=False)
def get_suggestions(document_id: int):
    if USE_FAKE:
        return fake_data.get_suggestions(document_id)
    r = requests.get(f"{BASE_URL}/suggestions/documents/{document_id}", timeout=10)
    r.raise_for_status()
    return r.json().get("suggestions", [])


@_safe("", show_dialog=False)
def get_raw_text(document_id: int):
    # raw_text comes from the documents row — in real backend fetch it from get_documents()
    if USE_FAKE:
        return fake_data.get_raw_text(document_id)
    r = requests.get(f"{BASE_URL}/documents/", timeout=10)
    r.raise_for_status()
    docs = r.json().get("documents", [])
    match = next((d for d in docs if d["document_id"] == document_id), {})
    return match.get("raw_text", "")


def _coder_name():
    """Name of the logged-in coder, saved with every decision for the admin view."""
    return session.current_user.get("name") or "coder"


@_safe(lambda: {"error": LAST_ERROR})
def submit_decision(suggestion_id: int, decision: str):
    # decision must be "approved" or "rejected"
    if USE_FAKE:
        return fake_data.submit_decision(suggestion_id, decision, _coder_name())
    r = requests.patch(
        f"{BASE_URL}/suggestions/{suggestion_id}",
        params={"decision": decision, "coder_name": _coder_name()},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


@_safe(lambda: {"error": LAST_ERROR})
def submit_correction(suggestion_id: int, corrected_icd_code: str):
    if USE_FAKE:
        return fake_data.submit_correction(suggestion_id, corrected_icd_code, _coder_name())
    r = requests.post(
        f"{BASE_URL}/corrections/",
        json={"suggestion_id": suggestion_id, "corrected_icd_code": corrected_icd_code,
              "correction_type": "reclassified", "coder_name": _coder_name()},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


@_safe(list, show_dialog=False)
def get_chat_history(document_id: int):
    if USE_FAKE:
        return fake_data.get_chat_history(document_id)
    r = requests.get(f"{BASE_URL}/chat/documents/{document_id}", timeout=10)
    r.raise_for_status()
    return r.json().get("messages", [])


@_safe(lambda: {"error": LAST_ERROR, "answer": "Sorry, I could not reach the server."}, show_dialog=False)
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


@_safe(lambda: {"error": "connection_failed", "message": LAST_ERROR}, show_dialog=False)
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


@_safe(dict, show_dialog=False)
def get_analytics():
    if USE_FAKE:
        return fake_data.get_analytics()
    r = requests.get(f"{BASE_URL}/analytics/", timeout=10)
    r.raise_for_status()
    return r.json()


@_safe(list, show_dialog=False)
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
    """Send a PDF or TXT file. Only the file's own name goes to the server."""
    if USE_FAKE:
        return fake_data.upload_document(filepath, patient_ref)
    filename = os.path.basename(filepath)
    mime = "application/pdf" if filename.lower().endswith(".pdf") else "text/plain"
    with open(filepath, "rb") as f:
        r = requests.post(
            f"{BASE_URL}/documents/",
            files={"file": (filename, f, mime)},
            data={"patient_ref": patient_ref},
            timeout=180,   # NLP pipeline takes time
        )
    r.raise_for_status()
    return r.json()


@_safe(lambda: {"error": LAST_ERROR})
def upload_text(raw_text: str, patient_ref: str = ""):
    """Send a discharge summary the coder pasted in, with no file involved."""
    if USE_FAKE:
        return fake_data.upload_document("pasted.txt", patient_ref)
    r = requests.post(
        f"{BASE_URL}/documents/",
        data={"raw_text": raw_text, "patient_ref": patient_ref},
        timeout=180,
    )
    r.raise_for_status()
    return r.json()
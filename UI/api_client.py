# api_client.py
import requests
import fake_data

USE_FAKE = False
BASE_URL = "https://scics-production.up.railway.app"


def get_documents():
    if USE_FAKE:
        return fake_data.get_documents()
    r = requests.get(f"{BASE_URL}/documents/", timeout=10)
    r.raise_for_status()
    return r.json().get("documents", [])


def get_suggestions(document_id: int):
    if USE_FAKE:
        return fake_data.get_suggestions(document_id)
    r = requests.get(f"{BASE_URL}/suggestions/documents/{document_id}", timeout=10)
    r.raise_for_status()
    return r.json().get("suggestions", [])


def get_raw_text(document_id: int):
    # raw_text comes from the documents row — in real backend fetch it from get_documents()
    if USE_FAKE:
        return fake_data.get_raw_text(document_id)
    r = requests.get(f"{BASE_URL}/documents/", timeout=10)
    r.raise_for_status()
    docs = r.json().get("documents", [])
    match = next((d for d in docs if d["document_id"] == document_id), {})
    return match.get("raw_text", "")


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


def submit_correction(suggestion_id: int, corrected_icd_code: str):
    # stubbed — wire to POST /corrections/ once endpoint exists
    if USE_FAKE:
        return fake_data.submit_correction(suggestion_id, corrected_icd_code)
    r = requests.post(
        f"{BASE_URL}/corrections/",
        json={"suggestion_id": suggestion_id, "corrected_icd_code": corrected_icd_code,
              "correction_type": "edit"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def get_chat_history(document_id: int):
    if USE_FAKE:
        return fake_data.get_chat_history(document_id)
    r = requests.get(f"{BASE_URL}/chat/documents/{document_id}", timeout=10)
    r.raise_for_status()
    return r.json().get("messages", [])


def send_chat(document_id: int, message: str):
    if USE_FAKE:
        return fake_data.send_chat(document_id, message)
    # backend expects query params, not a JSON body
    r = requests.post(
        f"{BASE_URL}/chat/documents/{document_id}",
        params={"sender": "coder", "message_text": message},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


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


def get_analytics():
    if USE_FAKE:
        return fake_data.get_analytics()
    r = requests.get(f"{BASE_URL}/analytics/", timeout=10)
    r.raise_for_status()
    return r.json()


def get_corrections():
    if USE_FAKE:
        return fake_data.get_corrections()
    r = requests.get(f"{BASE_URL}/corrections/", timeout=10)
    r.raise_for_status()
    return r.json()


def mark_complete(document_id: int):
    # stubbed — wire to PATCH /documents/{id}/complete once endpoint exists
    if USE_FAKE:
        return fake_data.mark_complete(document_id)
    r = requests.patch(f"{BASE_URL}/documents/{document_id}/complete", timeout=10)
    r.raise_for_status()
    return r.json()


def upload_document(filepath: str, patient_ref: str = ""):
    if USE_FAKE:
        return fake_data.upload_document(filepath, patient_ref)
    with open(filepath, "rb") as f:
        r = requests.post(
            f"{BASE_URL}/documents/",
            files={"file": (filepath, f, "text/plain")},
            params={"patient_ref": patient_ref},
            timeout=30,   # NLP pipeline takes time
        )
    r.raise_for_status()
    return r.json()

## Setup

1. `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and fill in `DATABASE_URL`
3. `python setup_database.py` (creates the tables and loads the ICD codes)
4. `uvicorn main:app --host 0.0.0.0 --port 8000`
5. Set the server address in `UI/config.json`, then run `python UI/ui_main.py`

To use a local Ollama for the chat, leave `GEMINI_API_KEY` empty in `.env`.
# SCICS
SIUT Clinical ICD Coding System 

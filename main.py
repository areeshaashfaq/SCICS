from fastapi import FastAPI
from dotenv import load_dotenv
from routers import documents, suggestions, chat

load_dotenv()

app = FastAPI(title="Khidmat API")

app.include_router(documents.router)
app.include_router(suggestions.router)
app.include_router(chat.router)

@app.get("/")
def root():
    return {"message": "Khidmat API is running"}
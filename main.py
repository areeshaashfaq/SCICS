from fastapi import FastAPI
from dotenv import load_dotenv
from routers import documents, suggestions, chat, analytics, auth, corrections, retrain

load_dotenv()

app = FastAPI(title="Khidmat API")


app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(suggestions.router)
app.include_router(chat.router)
app.include_router(analytics.router)
app.include_router(corrections.router)
app.include_router(retrain.router)


@app.get("/")
def root():
    return {"message": "Khidmat API is running"}
from fastapi import FastAPI
from dotenv import load_dotenv
from routers import documents

load_dotenv()

app = FastAPI(title="Khidmat API")

app.include_router(documents.router)

@app.get("/")
def root():
    return {"message": "Khidmat API is running"}
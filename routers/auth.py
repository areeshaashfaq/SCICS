from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db
from fastapi import Depends
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["auth"])

SECRET_KEY = "khidmat_secret_key_2026"
ALGORITHM = "HS256"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.execute(text("""
        SELECT * FROM users WHERE username = :username
    """), {"username": request.username}).fetchone()

    if not user or not pwd_context.verify(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail={"error": "invalid_credentials"})

    token = jwt.encode({
        "user_id": user.user_id,
        "name": user.name,
        "role": user.role,
        "exp": datetime.utcnow() + timedelta(hours=8)
    }, SECRET_KEY, algorithm=ALGORITHM)

    return {
        "token": token,
        "role": user.role,
        "name": user.name
    }

@router.post("/register")
def register(username: str, password: str, name: str, role: str = "coder", db: Session = Depends(get_db)):
    hashed = pwd_context.hash(password)
    try:
        db.execute(text("""
            INSERT INTO users (username, password_hash, name, role)
            VALUES (:username, :password_hash, :name, :role)
        """), {"username": username, "password_hash": hashed, "name": name, "role": role})
        db.commit()
        return {"message": "User created successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail="Username already exists")
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db
from jose import jwt
from datetime import datetime, timedelta
from pydantic import BaseModel
import bcrypt

router = APIRouter(prefix="/auth", tags=["auth"])

SECRET_KEY = "khidmat_secret_key_2026"
ALGORITHM = "HS256"

class LoginRequest(BaseModel):
    username: str
    password: str

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def validate_password(password: str):
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if not any(c.isupper() for c in password):
        raise HTTPException(status_code=400, detail="Password must contain at least one uppercase letter")
    if not any(c.isdigit() for c in password):
        raise HTTPException(status_code=400, detail="Password must contain at least one number")

@router.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.execute(text("""
        SELECT * FROM users WHERE username = :username
    """), {"username": request.username}).fetchone()

    if not user or not verify_password(request.password, user.password_hash):
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
    validate_password(password)
    hashed = hash_password(password)
    try:
        db.execute(text("""
            INSERT INTO users (username, password_hash, name, role)
            VALUES (:username, :password_hash, :name, :role)
        """), {"username": username, "password_hash": hashed, "name": name, "role": role})
        db.commit()
        return {"message": "User created successfully"}
    except Exception:
        raise HTTPException(status_code=400, detail="Username already exists")
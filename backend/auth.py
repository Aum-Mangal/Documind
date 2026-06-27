from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
from database import get_db
from models import User
from dotenv import load_dotenv
import os

load_dotenv()

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"

# ── Schemas ──────────────────────────────────────────
class UserCreate(BaseModel):
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

# ── Helpers ──────────────────────────────────────────
def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str):
    return pwd_context.verify(plain, hashed)

def create_token(user_id: int):
    expire = datetime.utcnow() + timedelta(hours=24)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

# ── Routes ───────────────────────────────────────────
@router.post("/signup")
def signup(user: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    new_user = User(
        email=user.email,
        password=hash_password(user.password)
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "Account created successfully"}

@router.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    token = create_token(db_user.id)
    return {"access_token": token, "token_type": "bearer"}
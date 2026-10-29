from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime, timedelta, timezone
from database import get_db
from models import User
from config import SECRET_KEY, JWT_ALGORITHM, ACCESS_TOKEN_TTL_HOURS
import bcrypt
import jwt

router = APIRouter()
bearer_scheme = HTTPBearer(auto_error=False)

# ── Schemas ──────────────────────────────────────────
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

# ── Helpers ──────────────────────────────────────────
def _password_bytes(password: str) -> bytes:
    # bcrypt only uses the first 72 bytes. Truncate on a character boundary, exactly as the
    # earlier passlib-based code did, so hashes created before this change still verify.
    return password.encode("utf-8")[:72].decode("utf-8", errors="ignore").encode("utf-8")

def hash_password(password: str) -> str:
    return bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_password_bytes(plain), hashed.encode("utf-8"))
    except ValueError:
        return False

# Compared against when the email doesn't exist, so login takes the same time either way
_DUMMY_HASH = hash_password("dummy-password-for-timing")

def create_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "iat": now, "exp": now + timedelta(hours=ACCESS_TOKEN_TTL_HOURS)}
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)

def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=401, detail="Not authenticated", headers={"WWW-Authenticate": "Bearer"}
    )
    if credentials is None:
        raise unauthorized
    try:
        payload = jwt.decode(
            credentials.credentials,
            SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, ValueError):
        raise unauthorized

    user = db.get(User, user_id)
    if not user:
        raise unauthorized
    return user

def _find_user(db: Session, email: str) -> User | None:
    return db.query(User).filter(func.lower(User.email) == email.lower()).first()

# ── Routes ───────────────────────────────────────────
@router.post("/signup")
def signup(user: UserCreate, db: Session = Depends(get_db)):
    if _find_user(db, user.email):
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(
        email=user.email.lower(),
        password=hash_password(user.password)
    )
    db.add(new_user)
    db.commit()
    return {"message": "Account created successfully"}

@router.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = _find_user(db, user.email)
    if not db_user:
        verify_password(user.password, _DUMMY_HASH)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not verify_password(user.password, db_user.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_token(db_user.id)
    return {"access_token": token, "token_type": "bearer"}

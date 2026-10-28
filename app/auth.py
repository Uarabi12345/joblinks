from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta
import os

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(email: str) -> str:
    payload = {
        "sub": email,
        "exp": datetime.utcnow() + timedelta(days=TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> str | None:
    try:
        data = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return data.get("sub")
    except JWTError:
        return None


def current_user(request, db):
    from app.models import User

    token = request.cookies.get("access_token")
    if not token:
        return None
    email = decode_token(token)
    if not email:
        return None
    return db.query(User).filter(User.email == email).first()
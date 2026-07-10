from datetime import datetime, timedelta
from typing import Optional

from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database import get_db
from config import settings

SECRET_KEY = settings.JWT_SECRET
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(user_id: int, username: str, role: str, expires_delta: timedelta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)) -> str:
    expire = datetime.utcnow() + expires_delta
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的或已过期的 Token",
        )


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail="未登录")
    payload = decode_token(credentials.credentials)
    user_id = int(payload.get("sub")) if payload.get("sub") else None
    if user_id is None:
        raise HTTPException(status_code=401, detail="无效的 Token")
    # Return token payload — no DB lookup needed for most endpoints
    return {
        "id": user_id,
        "username": payload.get("username"),
        "role": payload.get("role", "user"),
    }


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("role") not in ("admin", "creator"):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user


def require_creator(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """检查制作者权限 — 查数据库实时状态，防止 JWT 过期导致权限不一致"""
    # admin 直接放行
    if current_user.get("role") == "admin":
        return current_user
    
    # 查数据库确认真实角色
    from database import engine
    import models as m
    
    user = db.query(m.User).filter(m.User.id == current_user["id"]).first()
    if not user or user.role != "creator":
        raise HTTPException(status_code=403, detail="需要制作者权限")
    
    # 检查申请状态必须是 approved
    app = db.query(m.CreatorApplication).filter(
        m.CreatorApplication.user_id == current_user["id"]
    ).first()
    if not app or app.status != "approved":
        raise HTTPException(status_code=403, detail="制作者申请尚未批准，无法操作")
    
    return current_user

"""认证路由：注册、登录、获取当前用户"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
import models
from auth import hash_password, verify_password, create_token, get_current_user
from commission import resolve_ref_parent, update_parent_team_sizes
from schemas import AuthLoginReq, AuthRegisterReq

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register")
async def auth_register(req: AuthRegisterReq, db: Session = Depends(get_db)):
    """用户注册（带密码）"""
    if db.query(models.User).filter(models.User.username == req.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少6位")

    parent_id = resolve_ref_parent(req.ref_code, db)

    new_user = models.User(
        username=req.username, role="user", parent_id=parent_id,
        password_hash=hash_password(req.password),
    )
    db.add(new_user)
    db.flush()

    if parent_id:
        update_parent_team_sizes(parent_id, db)

    db.commit()
    token = create_token(new_user.id, new_user.username, new_user.role)
    return {
        "token": token,
        "user": {"id": new_user.id, "username": new_user.username, "role": new_user.role},
    }


@router.post("/login")
async def auth_login(req: AuthLoginReq, db: Session = Depends(get_db)):
    """用户登录"""
    user = db.query(models.User).filter(models.User.username == req.username).first()
    if not user or not user.password_hash or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_token(user.id, user.username, user.role)
    return {
        "token": token,
        "user": {"id": user.id, "username": user.username, "role": user.role},
    }


@router.get("/me")
async def auth_me(current_user: dict = Depends(get_current_user)):
    """获取当前用户信息"""
    return current_user

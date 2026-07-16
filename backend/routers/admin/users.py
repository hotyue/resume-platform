"""管理员路由 — 用户管理"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
import models as m
from auth import require_admin

router = APIRouter()


@router.get("/users")
async def list_users(
    search: str | None = None,
    role: str | None = None,
    page: int = Query(1),
    page_size: int = Query(50),
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """管理员查看用户列表"""
    query = db.query(m.User)
    if search:
        query = query.filter(m.User.username.ilike(f"%{search}%"))
    if role:
        query = query.filter(m.User.role == role)
    total = query.count()
    results = query.order_by(m.User.id).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "users": [{
        "id": u.id, "username": u.username, "role": u.role,
        "wallet_balance": round(u.wallet_balance, 2),
        "deposit_frozen": round(u.deposit_frozen, 2),
        "team_size": u.team_size, "parent_id": u.parent_id,
        "created_at": str(u.created_at) if u.created_at else "N/A",
    } for u in results]}


@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    req_body: dict,
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """管理员更新用户信息"""
    user = db.query(m.User).filter(m.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if req_body.get("role") and req_body["role"] in ("user", "admin"):
        user.role = req_body["role"]
    if req_body.get("wallet_balance") is not None and req_body["wallet_balance"] >= 0:
        user.wallet_balance = req_body["wallet_balance"]
    db.commit()
    return {"id": user.id, "role": user.role, "wallet_balance": round(user.wallet_balance, 2)}

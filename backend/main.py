from fastapi import FastAPI, Depends, HTTPException, Header, Request, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
import os
import uuid
import logging
from datetime import datetime, timedelta

from database import engine, Base, get_db, SessionLocal
import models
import payjs
from auth import (
    hash_password, verify_password, create_token,
    get_current_user, require_admin,
)

ASSETS_DIR = os.getenv("ASSETS_DIR", "/root/assets")
app = FastAPI(title="Resume Platform API", version="1.0.0")


# ================= Pydantic 请求体 =================

class CreateOrderReq(BaseModel):
    template_id: int
    ref_user_id: Optional[int] = None
    order_type: str = "download"
    custom_requirements: Optional[str] = None

class MockPayReq(BaseModel):
    order_no: str

class PayReq(BaseModel):
    order_no: str

class TakeOrderReq(BaseModel):
    order_no: str

class AuthLoginReq(BaseModel):
    username: str
    password: str

class AuthRegisterReq(BaseModel):
    username: str
    password: str
    ref_code: Optional[str] = None

class RegisterReq(BaseModel):
    username: str
    ref_code: Optional[str] = None

class CreatorApplyReq(BaseModel):
    user_id: int
    real_name: str
    phone: str
    wechat: str
    specialty: Optional[str] = ""
    portfolio_desc: Optional[str] = ""
    experience: Optional[str] = ""

class ReviewApplyReq(BaseModel):
    application_id: int
    status: str                   # approved / rejected
    remark: Optional[str] = ""

class WithdrawReq(BaseModel):
    user_id: int
    amount: float
    payment_info: str

class ReviewWithdrawReq(BaseModel):
    request_id: int
    status: str                   # approved / rejected
    remark: Optional[str] = ""

class UpdateUserReq(BaseModel):
    role: Optional[str] = None
    wallet_balance: Optional[float] = None

class UpdateCommissionConfigReq(BaseModel):
    level: int
    rate: float


# ================= 三级分佣核心 =================

def load_commission_rates(db: Session) -> dict:
    """从数据库加载分佣比例"""
    configs = db.query(models.CommissionConfig).all()
    return {c.level: c.rate for c in configs}

def get_ref_chain(ref_user_id: int, db: Session) -> list:
    rates = load_commission_rates(db)
    chain = []
    current_id = ref_user_id
    for level in range(1, 4):
        if current_id is None: break
        user = db.query(models.User).filter(models.User.id == current_id).first()
        if not user: break
        rate = rates.get(level, 0)
        chain.append((user.id, level, rate))
        current_id = user.parent_id
    return chain

def distribute_commission(order, db: Session):
    if not order.ref_user_id: return
    chain = get_ref_chain(order.ref_user_id, db)
    records = []
    for user_id, level, rate in chain:
        if level > 3: break
        commission = round(order.amount * rate, 2)
        if commission <= 0: continue
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if user: user.wallet_balance += commission
        records.append(models.CommissionRecord(
            order_no=order.order_no, user_id=user_id, level=level,
            amount=commission, rate=rate,
        ))
    if records: db.add_all(records)


# ================= 启动初始化 =================

@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    if db.query(models.CommissionConfig).count() == 0:
        db.add_all([
            models.CommissionConfig(level=1, rate=0.15),
            models.CommissionConfig(level=2, rate=0.08),
            models.CommissionConfig(level=3, rate=0.05),
        ])

    if db.query(models.User).count() == 0:
        default_pwd = hash_password("admin123")
        db.add(models.User(id=1, username="高校合伙人_王老师", role="promoter", wallet_balance=158.50, password_hash=default_pwd))
        db.add(models.User(id=2, username="校园大使_李同学", role="promoter", wallet_balance=50.00, parent_id=1, password_hash=default_pwd))
        db.add(models.User(id=3, username="推广员_张同学", role="promoter", wallet_balance=20.00, parent_id=2, password_hash=default_pwd))
        db.add(models.User(id=4, username="简历制作者_赵老师", role="creator", wallet_balance=0.00, password_hash=default_pwd))
        db.add(models.User(id=5, username="待审核制作者", role="user", wallet_balance=0.00, password_hash=default_pwd))
        db.add(models.User(id=6, username="admin", role="admin", wallet_balance=0.00, password_hash=hash_password("admin123")))
        db.commit()
        for u in [1, 2]:
            u_ = db.query(models.User).filter(models.User.id == u).first()
            u_.team_size = db.query(models.User).filter(models.User.parent_id == u).count()
        db.commit()

    if db.query(models.Template).count() == 0 and os.path.exists(ASSETS_DIR):
        print("开始扫描模板仓库...")
        templates_to_add = []
        for root, dirs, files in os.walk(ASSETS_DIR):
            images = [f for f in files if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
            docs = [f for f in files if f.lower().endswith(('.doc', '.docx'))]
            if images and docs:
                rel_root = os.path.relpath(root, ASSETS_DIR)
                cat = rel_root.split(os.sep)[0] if os.sep in rel_root else "其他"
                templates_to_add.append(models.Template(
                    category=cat, name=os.path.basename(root),
                    jpg_path=os.path.join(rel_root, images[0]),
                    doc_path=os.path.join(rel_root, docs[0])
                ))
        if templates_to_add:
            db.add_all(templates_to_add)
            db.commit()
    db.close()


# ================= 静态文件 =================

if os.path.exists(ASSETS_DIR):
    app.mount("/static", StaticFiles(directory=ASSETS_DIR), name="static")


# ================= 健康检查 & 模板浏览 =================

@app.get("/api/v1/health")
async def health_check(db: Session = Depends(get_db)):
    return {"status": "ok", "templates_count": db.query(models.Template).count()}

@app.get("/api/v1/templates")
async def get_templates(skip: int = 0, limit: int = 50, category: str = None, db: Session = Depends(get_db)):
    query = db.query(models.Template).filter(models.Template.is_active == True)
    if category: query = query.filter(models.Template.category == category)
    return query.offset(skip).limit(limit).all()


# ================= 用户注册（含分销邀请） =================

@app.post("/api/v1/auth/register")
async def auth_register(req: AuthRegisterReq, db: Session = Depends(get_db)):
    """用户注册（带密码）"""
    if db.query(models.User).filter(models.User.username == req.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少6位")

    parent_id = None
    if req.ref_code:
        try:
            ref_user_id = int(req.ref_code.replace("INVITE_", ""))
            parent = db.query(models.User).filter(models.User.id == ref_user_id).first()
            if parent: parent_id = parent.id
        except (ValueError, AttributeError): pass

    new_user = models.User(
        username=req.username, role="user", parent_id=parent_id,
        password_hash=hash_password(req.password),
    )
    db.add(new_user)
    db.flush()

    if parent_id:
        current = parent_id
        for _ in range(3):
            u = db.query(models.User).filter(models.User.id == current).first()
            if u:
                u.team_size = db.query(models.User).filter(models.User.parent_id == current).count()
                current = u.parent_id
            else: break

    db.commit()
    token = create_token(new_user.id, new_user.username, new_user.role)
    return {
        "token": token,
        "user": {"id": new_user.id, "username": new_user.username, "role": new_user.role},
    }


@app.post("/api/v1/auth/login")
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


@app.get("/api/v1/auth/me")
async def auth_me(current_user: dict = Depends(get_current_user)):
    """获取当前用户信息"""
    return current_user


# ================= 用户注册（兼容旧版，无密码） =================

@app.post("/api/v1/user/register")
async def register(req: RegisterReq, db: Session = Depends(get_db)):
    """兼容旧版注册（无密码，仅用于测试）"""
    if db.query(models.User).filter(models.User.username == req.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")

    parent_id = None
    if req.ref_code:
        try:
            ref_user_id = int(req.ref_code.replace("INVITE_", ""))
            parent = db.query(models.User).filter(models.User.id == ref_user_id).first()
            if parent: parent_id = parent.id
        except (ValueError, AttributeError): pass

    new_user = models.User(username=req.username, role="user", parent_id=parent_id)
    db.add(new_user)
    db.flush()

    if parent_id:
        current = parent_id
        for _ in range(3):
            u = db.query(models.User).filter(models.User.id == current).first()
            if u:
                u.team_size = db.query(models.User).filter(models.User.parent_id == current).count()
                current = u.parent_id
            else: break

    db.commit()
    return {"id": new_user.id, "username": new_user.username, "parent_id": parent_id}


# ================= 分销团队 & 佣金查询 =================

@app.get("/api/v1/user/profile")
async def get_user_profile(db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == 2).first()
    invite_code = f"INVITE_{user.id}"
    return {
        "id": user.id, "username": user.username, "role": user.role,
        "wallet_balance": round(user.wallet_balance, 2),
        "team_size": user.team_size,
        "invite_code": invite_code,
        "invite_url": f"https://resume.example.com/register?ref={invite_code}",
    }

@app.get("/api/v1/user/team")
async def get_team(db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == 2).first()
    children = db.query(models.User).filter(models.User.parent_id == 2).all()
    grandchildren = []
    for child in children:
        gcs = db.query(models.User).filter(models.User.parent_id == child.id).all()
        for gc in gcs: grandchildren.append(gc)
    great_grandchildren = []
    for gc in grandchildren:
        ggcs = db.query(models.User).filter(models.User.parent_id == gc.id).all()
        for ggc in ggcs: great_grandchildren.append(ggc)

    def user_info(u):
        return {"id": u.id, "username": u.username, "role": u.role, "wallet_balance": round(u.wallet_balance, 2)}

    return {
        "level_0": user_info(user),
        "level_1": [user_info(c) for c in children],
        "level_2": [user_info(gc) for gc in grandchildren],
        "level_3": [user_info(ggc) for ggc in great_grandchildren],
    }

@app.get("/api/v1/user/commission-history")
async def get_commission_history(limit: int = 20, db: Session = Depends(get_db)):
    records = (
        db.query(models.CommissionRecord)
        .filter(models.CommissionRecord.user_id == 2)
        .order_by(models.CommissionRecord.created_at.desc())
        .limit(limit).all()
    )
    return [{
        "id": r.id, "order_no": r.order_no, "level": r.level,
        "amount": r.amount, "rate": r.rate, "created_at": str(r.created_at),
    } for r in records]

@app.get("/api/v1/user/stats/{user_id}")
async def get_user_stats(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user: raise HTTPException(status_code=404, detail="用户不存在")
    total_commission = (
        db.query(models.CommissionRecord)
        .filter(models.CommissionRecord.user_id == user_id)
        .with_entities(models.CommissionRecord.amount, models.CommissionRecord.level).all()
    )
    by_level = {1: 0, 2: 0, 3: 0}
    total = 0
    for amt, lv in total_commission:
        by_level[lv] = round(by_level[lv] + amt, 2)
        total += amt
    direct_count = db.query(models.User).filter(models.User.parent_id == user_id).count()
    return {
        "user_id": user_id, "username": user.username, "role": user.role,
        "wallet_balance": round(user.wallet_balance, 2),
        "team_size": user.team_size, "direct_count": direct_count,
        "total_commission": round(total, 2), "commission_by_level": by_level,
    }


# ================= 提现申请 =================

@app.post("/api/v1/user/withdraw")
async def submit_withdraw(req: WithdrawReq, db: Session = Depends(get_db)):
    """用户提交提现申请"""
    user = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not user: raise HTTPException(status_code=404, detail="用户不存在")
    if req.amount < 50: raise HTTPException(status_code=400, detail="最低提现金额为50元")
    if req.amount > user.wallet_balance: raise HTTPException(status_code=400, detail="余额不足")

    # 冻结金额
    user.wallet_balance -= req.amount
    withdraw = models.WithdrawRequest(
        user_id=req.user_id, amount=req.amount, payment_info=req.payment_info, status="pending"
    )
    db.add(withdraw)
    db.commit()
    return {"id": withdraw.id, "status": "pending", "message": "提现申请已提交，等待管理员审核"}


# ================= 制作者入驻申请 API =================

@app.post("/api/v1/creator/apply")
async def creator_apply(req: CreatorApplyReq, db: Session = Depends(get_db)):
    """提交制作者入驻申请"""
    user = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not user: raise HTTPException(status_code=404, detail="用户不存在")

    existing = db.query(models.CreatorApplication).filter(models.CreatorApplication.user_id == req.user_id).first()
    if existing:
        if existing.status == "pending":
            raise HTTPException(status_code=400, detail="已有待审核的申请，请等待审核结果")
        elif existing.status == "approved":
            raise HTTPException(status_code=400, detail="你已经是制作者了")
        # rejected → 覆盖旧申请
        existing.real_name = req.real_name
        existing.phone = req.phone
        existing.wechat = req.wechat
        existing.specialty = req.specialty
        existing.portfolio_desc = req.portfolio_desc
        existing.experience = req.experience
        existing.status = "pending"
        existing.review_remark = None
        existing.reviewed_at = None
        existing.created_at = datetime.now()
        db.commit()
        return {"id": existing.id, "status": "pending", "message": "申请已重新提交，等待管理员审核"}
    else:
        app_record = models.CreatorApplication(
            user_id=req.user_id, real_name=req.real_name, phone=req.phone,
            wechat=req.wechat, specialty=req.specialty, portfolio_desc=req.portfolio_desc,
            experience=req.experience, status="pending"
        )
        db.add(app_record)
        db.commit()
        return {"id": app_record.id, "status": "pending", "message": "申请已提交，等待管理员审核"}

@app.get("/api/v1/creator/application-status/{user_id}")
async def get_application_status(user_id: int, db: Session = Depends(get_db)):
    """查看自己的申请状态"""
    app_record = db.query(models.CreatorApplication).filter(models.CreatorApplication.user_id == user_id).first()
    if not app_record:
        return {"has_applied": False}
    return {
        "has_applied": True, "id": app_record.id, "status": app_record.status,
        "real_name": app_record.real_name, "phone": app_record.phone,
        "wechat": app_record.wechat, "specialty": app_record.specialty,
        "portfolio_desc": app_record.portfolio_desc, "experience": app_record.experience,
        "review_remark": app_record.review_remark,
        "created_at": str(app_record.created_at),
        "reviewed_at": str(app_record.reviewed_at) if app_record.reviewed_at else None,
    }


# ================= 管理员审核 API =================

@app.get("/api/v1/admin/applications")
async def list_applications(status: Optional[str] = None, db: Session = Depends(get_db), admin_user: dict = Depends(require_admin)):
    """管理员查看入驻申请列表"""
    query = db.query(models.CreatorApplication, models.User).join(models.User)
    if status: query = query.filter(models.CreatorApplication.status == status)
    results = query.order_by(models.CreatorApplication.created_at.desc()).all()

    return [{
        "id": a.id, "user_id": a.user_id, "username": u.username,
        "real_name": a.real_name, "phone": a.phone, "wechat": a.wechat,
        "specialty": a.specialty, "portfolio_desc": a.portfolio_desc,
        "experience": a.experience, "status": a.status,
        "review_remark": a.review_remark,
        "created_at": str(a.created_at),
        "reviewed_at": str(a.reviewed_at) if a.reviewed_at else None,
    } for a, u in results]

@app.post("/api/v1/admin/applications/review")
async def review_application(req: ReviewApplyReq, db: Session = Depends(get_db), admin_user: dict = Depends(require_admin)):
    """管理员审核入驻申请"""
    if req.status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="状态必须是 approved 或 rejected")

    a = db.query(models.CreatorApplication).filter(models.CreatorApplication.id == req.application_id).first()
    if not a: raise HTTPException(status_code=404, detail="申请不存在")
    if a.status != "pending": raise HTTPException(status_code=400, detail=f"该申请已处理（当前状态: {a.status}）")

    a.status = req.status
    a.review_remark = req.remark
    a.reviewed_at = datetime.now()

    if req.status == "approved":
        user = db.query(models.User).filter(models.User.id == a.user_id).first()
        if user: user.role = "creator"

    db.commit()
    return {"id": a.id, "status": a.status, "message": "审核完成"}


# ================= 管理员：订单管理 =================

@app.get("/api/v1/admin/orders")
async def admin_orders(
    status: Optional[str] = Query(None, description="按状态筛选"),
    search: Optional[str] = Query(None, description="搜索订单号/模板名"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """管理员订单列表"""
    query = db.query(models.Order, models.Template, models.User).outerjoin(
        models.Template, models.Order.template_id == models.Template.id
    ).outerjoin(
        models.User, models.Order.user_id == models.User.id
    )

    if status:
        query = query.filter(models.Order.status == status)
    if search:
        query = query.filter(
            models.Order.order_no.ilike(f"%{search}%") |
            models.Template.name.ilike(f"%{search}%")
        )

    total = query.count()
    results = (
        query.order_by(models.Order.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "orders": [{
            "id": o.id, "order_no": o.order_no, "amount": o.amount,
            "status": o.status, "order_type": o.order_type,
            "template_name": t.name if t else "N/A",
            "template_category": t.category if t else "N/A",
            "user_name": u.username if u else "N/A",
            "creator_id": o.creator_id,
            "ref_user_id": o.ref_user_id,
            "created_at": str(o.created_at),
        } for o, t, u in results],
    }

@app.get("/api/v1/admin/orders/{order_no}")
async def admin_order_detail(order_no: str, db: Session = Depends(get_db), admin_user: dict = Depends(require_admin)):
    """订单详情"""
    order = db.query(models.Order).filter(models.Order.order_no == order_no).first()
    if not order: raise HTTPException(status_code=404, detail="订单不存在")

    template = db.query(models.Template).filter(models.Template.id == order.template_id).first()
    user = db.query(models.User).filter(models.User.id == order.user_id).first()
    creator = db.query(models.User).filter(models.User.id == order.creator_id).first() if order.creator_id else None
    ref_user = db.query(models.User).filter(models.User.id == order.ref_user_id).first() if order.ref_user_id else None

    # 该订单的分佣记录
    commissions = db.query(models.CommissionRecord).filter(
        models.CommissionRecord.order_no == order_no
    ).all()

    return {
        "order": {
            "id": order.id, "order_no": order.order_no, "amount": order.amount,
            "status": order.status, "order_type": order.order_type,
            "custom_requirements": order.custom_requirements,
            "created_at": str(order.created_at),
            "template": {"id": template.id, "name": template.name, "category": template.category} if template else None,
            "user": {"id": user.id, "username": user.username, "role": user.role} if user else None,
            "creator": {"id": creator.id, "username": creator.username} if creator else None,
            "ref_user": {"id": ref_user.id, "username": ref_user.username} if ref_user else None,
        },
        "commissions": [{
            "id": c.id, "user_id": c.user_id, "level": c.level,
            "amount": c.amount, "rate": c.rate,
        } for c in commissions],
    }


# ================= 管理员：提现管理 =================

@app.get("/api/v1/admin/withdrawals")
async def admin_withdrawals(
    status: Optional[str] = Query(None, description="pending/approved/rejected"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """提现列表"""
    query = db.query(models.WithdrawRequest, models.User).join(models.User)
    if status:
        query = query.filter(models.WithdrawRequest.status == status)

    total = query.count()
    results = (
        query.order_by(models.WithdrawRequest.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total, "page": page, "page_size": page_size,
        "withdrawals": [{
            "id": w.id, "user_id": w.user_id, "username": u.username,
            "amount": w.amount, "payment_info": w.payment_info,
            "status": w.status, "admin_remark": w.admin_remark,
            "created_at": str(w.created_at),
            "reviewed_at": str(w.reviewed_at) if w.reviewed_at else None,
        } for w, u in results],
    }

@app.post("/api/v1/admin/withdrawals/review")
async def review_withdraw(req: ReviewWithdrawReq, db: Session = Depends(get_db), admin_user: dict = Depends(require_admin)):
    """审核提现"""
    if req.status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="状态必须是 approved 或 rejected")

    w = db.query(models.WithdrawRequest).filter(models.WithdrawRequest.id == req.request_id).first()
    if not w: raise HTTPException(status_code=404, detail="提现申请不存在")
    if w.status != "pending": raise HTTPException(status_code=400, detail=f"已处理（当前: {w.status}）")

    w.status = req.status
    w.admin_remark = req.remark
    w.reviewed_at = datetime.now()

    # 拒绝时退回余额
    if req.status == "rejected":
        user = db.query(models.User).filter(models.User.id == w.user_id).first()
        if user: user.wallet_balance += w.amount

    db.commit()
    return {"id": w.id, "status": w.status, "message": "审核完成"}


# ================= 管理员：分佣配置 =================

@app.get("/api/v1/admin/commission-config")
async def get_commission_config(db: Session = Depends(get_db), admin_user: dict = Depends(require_admin)):
    """获取当前分佣比例"""
    configs = db.query(models.CommissionConfig).order_by(models.CommissionConfig.level).all()
    return {
        "level_1_rate": configs[0].rate if len(configs) > 0 else 0.15,
        "level_2_rate": configs[1].rate if len(configs) > 1 else 0.08,
        "level_3_rate": configs[2].rate if len(configs) > 2 else 0.05,
    }

@app.put("/api/v1/admin/commission-config")
async def update_commission_config(req: UpdateCommissionConfigReq, db: Session = Depends(get_db), admin_user: dict = Depends(require_admin)):
    """修改分佣比例"""
    if req.level not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="级别必须是 1/2/3")
    if not (0 <= req.rate <= 1):
        raise HTTPException(status_code=400, detail="比例必须在 0~1 之间")

    config = db.query(models.CommissionConfig).filter(models.CommissionConfig.level == req.level).first()
    if not config:
        config = models.CommissionConfig(level=req.level, rate=req.rate)
        db.add(config)
    else:
        config.rate = req.rate
        config.updated_at = datetime.now()

    db.commit()
    return {"level": req.level, "rate": req.rate, "message": f"第{req.level}级分佣比例已更新为 {req.rate*100:.0f}%"}


# ================= 管理员：用户管理 =================

@app.get("/api/v1/admin/users")
async def admin_users(
    search: Optional[str] = Query(None, description="搜索用户名"),
    role: Optional[str] = Query(None, description="按角色筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """用户列表"""
    query = db.query(models.User)
    if search:
        query = query.filter(models.User.username.ilike(f"%{search}%"))
    if role:
        query = query.filter(models.User.role == role)

    total = query.count()
    results = query.order_by(models.User.id).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total, "page": page, "page_size": page_size,
        "users": [{
            "id": u.id, "username": u.username, "role": u.role,
            "wallet_balance": round(u.wallet_balance, 2),
            "team_size": u.team_size, "parent_id": u.parent_id,
            "created_at": str(u.created_at) if hasattr(u, 'created_at') and u.created_at else "N/A",
        } for u in results],
    }

@app.put("/api/v1/admin/users/{user_id}")
async def admin_update_user(user_id: int, req: UpdateUserReq, db: Session = Depends(get_db), admin_user: dict = Depends(require_admin)):
    """修改用户角色/调整余额"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user: raise HTTPException(status_code=404, detail="用户不存在")

    if req.role and req.role in ("user", "promoter", "creator", "admin"):
        user.role = req.role
    if req.wallet_balance is not None and req.wallet_balance >= 0:
        user.wallet_balance = req.wallet_balance

    db.commit()
    return {"id": user.id, "role": user.role, "wallet_balance": round(user.wallet_balance, 2)}


# ================= 管理员：数据看板 =================

@app.get("/api/v1/admin/dashboard")
async def admin_dashboard(db: Session = Depends(get_db), admin_user: dict = Depends(require_admin)):
    """数据看板"""
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # 总数据
    total_users = db.query(models.User).count()
    total_orders = db.query(models.Order).count()
    total_revenue = db.query(func.coalesce(func.sum(models.Order.amount), 0)).filter(
        models.Order.status.in_(["paid", "processing", "completed"])
    ).scalar() or 0.0

    # 今日
    today_orders = db.query(models.Order).filter(models.Order.created_at >= today_start).count()
    today_revenue = db.query(func.coalesce(func.sum(models.Order.amount), 0)).filter(
        models.Order.created_at >= today_start,
        models.Order.status.in_(["paid", "processing", "completed"])
    ).scalar() or 0.0

    # 本月
    month_orders = db.query(models.Order).filter(models.Order.created_at >= month_start).count()
    month_revenue = db.query(func.coalesce(func.sum(models.Order.amount), 0)).filter(
        models.Order.created_at >= month_start,
        models.Order.status.in_(["paid", "processing", "completed"])
    ).scalar() or 0.0

    # 佣金支出
    total_commission = db.query(func.coalesce(func.sum(models.CommissionRecord.amount), 0)).scalar() or 0.0

    # 待处理
    pending_orders = db.query(models.Order).filter(models.Order.status == "pending").count()
    pending_withdrawals = db.query(models.WithdrawRequest).filter(models.WithdrawRequest.status == "pending").count()
    pending_apps = db.query(models.CreatorApplication).filter(models.CreatorApplication.status == "pending").count()

    # 角色分布
    role_stats = {}
    for r in ["user", "promoter", "creator"]:
        role_stats[r] = db.query(models.User).filter(models.User.role == r).count()

    # 订单状态分布
    status_stats = {}
    for s in ["pending", "paid", "processing", "completed"]:
        status_stats[s] = db.query(models.Order).filter(models.Order.status == s).count()

    # 最近7天订单趋势
    trend = []
    for i in range(6, -1, -1):
        day = today_start - timedelta(days=i)
        next_day = day + timedelta(days=1)
        count = db.query(models.Order).filter(
            models.Order.created_at >= day, models.Order.created_at < next_day
        ).count()
        revenue = db.query(func.coalesce(func.sum(models.Order.amount), 0)).filter(
            models.Order.created_at >= day, models.Order.created_at < next_day,
            models.Order.status.in_(["paid", "processing", "completed"])
        ).scalar() or 0.0
        trend.append({
            "date": day.strftime("%m-%d"),
            "orders": count,
            "revenue": round(revenue, 2),
        })

    return {
        "total_users": total_users,
        "total_orders": total_orders,
        "total_revenue": round(total_revenue, 2),
        "today_orders": today_orders,
        "today_revenue": round(today_revenue, 2),
        "month_orders": month_orders,
        "month_revenue": round(month_revenue, 2),
        "total_commission_paid": round(total_commission, 2),
        "pending_orders": pending_orders,
        "pending_withdrawals": pending_withdrawals,
        "pending_applications": pending_apps,
        "role_stats": role_stats,
        "order_status_stats": status_stats,
        "daily_trend": trend,
    }


# ================= 管理员统计（兼容旧版） =================

@app.get("/api/v1/admin/stats")
async def admin_stats(db: Session = Depends(get_db), admin_user: dict = Depends(require_admin)):
    """管理后台数据概览（兼容旧版）"""
    pending_count = db.query(models.CreatorApplication).filter(models.CreatorApplication.status == "pending").count()
    approved_count = db.query(models.CreatorApplication).filter(models.CreatorApplication.status == "approved").count()
    rejected_count = db.query(models.CreatorApplication).filter(models.CreatorApplication.status == "rejected").count()
    creator_count = db.query(models.User).filter(models.User.role == "creator").count()
    promoter_count = db.query(models.User).filter(models.User.role == "promoter").count()
    total_users = db.query(models.User).count()
    total_revenue = db.query(func.coalesce(func.sum(models.Order.amount), 0)).filter(
        models.Order.status.in_(["paid", "processing", "completed"])
    ).scalar() or 0.0
    total_commission = db.query(func.coalesce(func.sum(models.CommissionRecord.amount), 0)).scalar() or 0.0
    pending_withdrawals = db.query(models.WithdrawRequest).filter(models.WithdrawRequest.status == "pending").count()

    return {
        "total_users": total_users, "creator_count": creator_count,
        "promoter_count": promoter_count,
        "pending_approvals": pending_count,
        "approved_approvals": approved_count,
        "rejected_approvals": rejected_count,
        "total_revenue": round(total_revenue, 2),
        "total_commission": round(total_commission, 2),
        "pending_withdrawals": pending_withdrawals,
    }


# ================= 订单与交易 =================

@app.post("/api/v1/orders")
async def create_order(req: CreateOrderReq, db: Session = Depends(get_db)):
    template = db.query(models.Template).filter(models.Template.id == req.template_id).first()
    if not template: raise HTTPException(status_code=404, detail="模板不存在")
    amount = 19.99 if req.order_type == "custom_service" else template.price
    order_no = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    db.add(models.Order(
        order_no=order_no, template_id=template.id, amount=amount,
        ref_user_id=req.ref_user_id, order_type=req.order_type,
        custom_requirements=req.custom_requirements
    ))
    db.commit()
    return {"order_no": order_no, "amount": amount, "type": req.order_type}

@app.post("/api/v1/payments/mock-callback")
async def mock_payment_callback(req: MockPayReq, db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(models.Order.order_no == req.order_no).first()
    if not order or order.status != "pending": return {"status": "error"}
    order.status = "paid"
    distribute_commission(order, db)
    db.commit()
    return {"status": "success"}

@app.post("/api/v1/payments/payjs-qrcode")
async def payjs_qrcode(req: PayReq, db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(models.Order.order_no == req.order_no).first()
    if not order: raise HTTPException(status_code=404, detail="订单不存在")
    if order.status != "pending": raise HTTPException(status_code=400, detail="订单状态异常")
    total_fee = int(order.amount * 100)
    result = payjs.create_native_qrcode(
        out_trade_no=order.order_no, total_fee=total_fee,
        body="简历模板下载", attach=str(order.template_id or ""),
    )
    if not result["success"]:
        return {"success": False, "message": result["message"], "qrcode": None}
    return {
        "success": True, "message": "请使用微信扫码支付",
        "qrcode": result["data"]["qrcode"], "code_url": result["data"]["code_url"],
        "payjs_order_id": result["data"]["payjs_order_id"], "amount": order.amount,
    }

@app.post("/api/v1/payments/payjs-notify")
async def payjs_notify(request: Request, db: Session = Depends(get_db)):
    body = await request.form()
    params = dict(body)
    if not payjs.verify_sign(params, payjs.PAYJS_KEY):
        logging.warning(f"PayJS 回调签名验证失败: {params}")
        return "sign error"
    if params.get("return_code") != "1": return "fail"
    out_trade_no = params.get("out_trade_no", "")
    order = db.query(models.Order).filter(models.Order.order_no == out_trade_no).first()
    if not order: return "order not found"
    if order.status == "paid": return "success"
    order.status = "paid"
    distribute_commission(order, db)
    db.commit()
    return "success"

@app.get("/api/v1/orders/status/{order_no}")
async def get_order_status(order_no: str, db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(models.Order.order_no == order_no).first()
    if not order: raise HTTPException(status_code=404, detail="订单不存在")
    return {"order_no": order.order_no, "status": order.status, "amount": order.amount, "order_type": order.order_type}

@app.get("/api/v1/orders/download/{order_no}")
async def download_by_order(order_no: str, db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(models.Order.order_no == order_no).first()
    if not order or order.status not in ["paid", "processing", "completed"]:
        raise HTTPException(status_code=403, detail="未支付或无权下载")
    template = db.query(models.Template).filter(models.Template.id == order.template_id).first()
    full_path = os.path.abspath(os.path.join(ASSETS_DIR, template.doc_path))
    return FileResponse(full_path, media_type='application/msword', filename=f"{template.name}.doc")


# ================= 众包大厅（支持制作者角色） =================

@app.get("/api/v1/creator/orders")
async def get_creator_orders(tab: str = "pending", db: Session = Depends(get_db)):
    query = db.query(models.Order, models.Template).join(models.Template).filter(models.Order.order_type == "custom_service")
    if tab == "pending":
        results = query.filter(models.Order.status == "paid", models.Order.creator_id == None).all()
    elif tab == "mine":
        results = query.filter(models.Order.creator_id == 2).all()
    else:
        results = query.filter(models.Order.creator_id == 2).all()

    return [{
        "order_no": o.order_no, "amount": o.amount, "status": o.status,
        "requirements": o.custom_requirements, "created_at": str(o.created_at),
        "template_name": f"{t.category}-{t.name}",
    } for o, t in results]

@app.post("/api/v1/creator/take")
async def take_order(req: TakeOrderReq, db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(
        models.Order.order_no == req.order_no, models.Order.status == "paid",
        models.Order.creator_id == None
    ).first()
    if not order: raise HTTPException(status_code=400, detail="订单已被抢走或状态错误")
    order.creator_id = 2
    order.status = "processing"
    db.commit()
    return {"status": "success"}

@app.post("/api/v1/creator/deliver")
async def deliver_order(req: TakeOrderReq, db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(
        models.Order.order_no == req.order_no, models.Order.creator_id == 2,
        models.Order.status == "processing"
    ).first()
    if not order: raise HTTPException(status_code=400, detail="订单异常")
    order.status = "completed"
    creator = db.query(models.User).filter(models.User.id == 2).first()
    creator.wallet_balance += (order.amount * 0.30)
    db.commit()
    return {"status": "success"}

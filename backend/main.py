"""
简历模板市场 — FastAPI 后端
"""
import os
import uuid
import logging
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import SessionLocal, engine, get_db
import models as m
import auth

# ---------------------------------------------------------------------------
# 初始化
# ---------------------------------------------------------------------------
m.Base.metadata.create_all(bind=engine)

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PayJS 配置
# ---------------------------------------------------------------------------
PAYJS_MCHID = os.getenv("PAYJS_MCHID", "")
PAYJS_KEY = os.getenv("PAYJS_KEY", "")

import urllib.parse
import requests as req_lib


def create_native_qrcode(out_trade_no: str, total_fee: int, body: str = "简历模板下载", attach: str = ""):
    """创建 PayJS Native 支付二维码"""
    if not PAYJS_MCHID or not PAYJS_KEY:
        return {"success": False, "message": "PayJS 未配置，使用模拟支付", "data": {}}
    url = "https://payjs.cn/api/native"
    params = {
        "mchid": PAYJS_MCHID, "out_trade_no": out_trade_no,
        "total_fee": str(total_fee), "body": body, "attach": attach,
        "notify_url": "http://your-domain.com/api/v1/payments/payjs-notify",
    }
    sign_str = urllib.parse.urlencode(params) + f"&key={PAYJS_KEY}"
    params["sign"] = hashlib.md5(sign_str.encode()).hexdigest()
    resp = req_lib.post(url, data=params, timeout=10)
    result = resp.json()
    if result.get("return_code") == 1 and result.get("result_code") == 1:
        return {"success": True, "data": {"qrcode": result.get("code_url"),
                "code_url": result.get("code_url"), "payjs_order_id": result.get("payjs_order_id")}}
    return {"success": False, "message": result.get("return_msg", "PayJS 创建失败")}


def verify_payjs_sign(params: dict, key: str) -> bool:
    if not key:
        return False
    params_copy = {k: v for k, v in params.items() if k != "sign"}
    sign_str = urllib.parse.urlencode(sorted(params_copy.items())) + f"&key={key}"
    expected = hashlib.md5(sign_str.encode()).hexdigest()
    return hmac.compare_digest(params.get("sign", ""), expected)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------
class LoginReq(BaseModel):
    username: str
    password: str

class RegisterReq(BaseModel):
    username: str
    password: str
    ref_user_id: Optional[int] = None

class CreateOrderReq(BaseModel):
    template_id: int
    order_type: str = "download"
    ref_user_id: Optional[int] = None
    custom_requirements: Optional[str] = None

class MockPayReq(BaseModel):
    order_no: str

class PayReq(BaseModel):
    order_no: str

class TakeOrderReq(BaseModel):
    order_no: str

class DeliverReq(BaseModel):
    order_no: str
    file_url: str
    remark: str = ""

class ReviewReq(BaseModel):
    order_no: str
    result: str
    buyer_remark: str = ""

class ReviewWithdrawReq(BaseModel):
    request_id: int
    status: str
    remark: str = ""

class ReviewApplicationReq(BaseModel):
    request_id: int
    status: str
    remark: str = ""

class UpdateCommissionConfigReq(BaseModel):
    level: int
    rate: float

class UpdateUserReq(BaseModel):
    role: Optional[str] = None
    wallet_balance: Optional[float] = None

class CreatorAppReq(BaseModel):
    real_name: str
    phone: str
    wechat: str
    specialty: str = ""
    portfolio_desc: str = ""
    experience: str = ""

class WithdrawReq(BaseModel):
    amount: float
    payment_info: str
    account_type: str = "alipay"

class UpdateProfileReq(BaseModel):
    alipay_account: Optional[str] = None
    wechat_account: Optional[str] = None

class UpdatePasswordReq(BaseModel):
    old_password: str
    new_password: str

class RechargeReq(BaseModel):
    amount: float
    method: str = "manual"

class RefundReq(BaseModel):
    order_no: str
    reason: str = ""

class ReviewRefundReq(BaseModel):
    refund_id: int
    status: str
    remark: str = ""

class UpdateSystemConfigReq(BaseModel):
    key: str
    value: float


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="Resume Platform API")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# 复用 auth 模块
require_admin = auth.require_admin
require_creator = auth.require_creator
get_current_user = auth.get_current_user


# ---------------------------------------------------------------------------
# 系统配置读写
# ---------------------------------------------------------------------------
def is_custom_order(order_type: str) -> bool:
    return order_type in ("custom_service", "custom")


def get_config(db: Session, key: str, default: float = 0.0) -> float:
    cfg = db.query(m.SystemConfig).filter(m.SystemConfig.key == key).first()
    if cfg:
        return cfg.value
    descriptions = {
        "download_price": "下载订单金额", "custom_price": "定制订单金额",
        "creator_rate": "制作者分佣比例", "level1_rate": "一级推广分佣比例",
        "level2_rate": "二级推广分佣比例", "level3_rate": "三级推广分佣比例",
        "deposit_amount": "制作者保证金金额",
    }
    cfg = m.SystemConfig(key=key, value=default, description=descriptions.get(key, key))
    db.add(cfg)
    db.commit()
    return default


def load_all_configs(db: Session) -> dict:
    return {
        "download_price": get_config(db, "download_price", 1.99),
        "custom_price": get_config(db, "custom_price", 19.99),
        "creator_rate": get_config(db, "creator_rate", 0.30),
        "level1_rate": get_config(db, "level1_rate", 0.15),
        "level2_rate": get_config(db, "level2_rate", 0.08),
        "level3_rate": get_config(db, "level3_rate", 0.05),
        "deposit_amount": get_config(db, "deposit_amount", 20.0),
    }


def get_deposit_amount(db: Session) -> float:
    return get_config(db, "deposit_amount", 20.0)


# ---------------------------------------------------------------------------
# 分销链
# ---------------------------------------------------------------------------
def get_ref_chain(ref_user_id: int, db: Session) -> list:
    configs = load_all_configs(db)
    rates = [configs["level1_rate"], configs["level2_rate"], configs["level3_rate"]]
    chain = []
    uid = ref_user_id
    for level in range(1, 4):
        if uid is None:
            break
        user = db.query(m.User).filter(m.User.id == uid).first()
        if not user:
            break
        chain.append((uid, level, rates[level - 1]))
        uid = user.parent_id
    return chain


# ---------------------------------------------------------------------------
# 佣金结算
# ---------------------------------------------------------------------------
def distribute_commission(order: m.Order, db: Session):
    """下载订单佣金 — 即时到账（无冻结）"""
    if order.commission_distributed:
        return
    amount = order.amount
    if order.ref_user_id:
        chain = get_ref_chain(order.ref_user_id, db)
        for user_id, level, rate in chain:
            if level > 3:
                break
            commission = round(amount * rate, 2)
            if commission <= 0:
                continue
            user = db.query(m.User).filter(m.User.id == user_id).first()
            if user:
                user.wallet_balance += commission
            rec = m.CommissionRecord(
                order_no=order.order_no, user_id=user_id,
                level=level, amount=commission, rate=rate,
            )
            db.add(rec)
    order.commission_distributed = True


def settle_custom_commission(order: m.Order, db: Session):
    """定制订单佣金 — 验收通过后冻结 7 天"""
    if order.commission_distributed:
        return
    configs = load_all_configs(db)
    amount = order.amount
    freeze_until = datetime.now() + timedelta(days=7)
    pending_records = []
    if order.creator_id:
        creator_amt = round(amount * configs["creator_rate"], 2)
        pending_records.append(m.CommissionPending(
            order_no=order.order_no, user_id=order.creator_id,
            role_type="creator", amount=creator_amt, rate=configs["creator_rate"],
            freeze_until=freeze_until,
        ))
        db.add(m.CommissionRecord(
            order_no=order.order_no, user_id=order.creator_id,
            level=0, amount=creator_amt, rate=configs["creator_rate"],
        ))
    if order.ref_user_id:
        chain = get_ref_chain(order.ref_user_id, db)
        for user_id, level, rate in chain:
            if level > 3:
                break
            commission = round(amount * rate, 2)
            if commission <= 0:
                continue
            pending_records.append(m.CommissionPending(
                order_no=order.order_no, user_id=user_id,
                role_type=f"level{level}", amount=commission, rate=rate,
                freeze_until=freeze_until,
            ))
            db.add(m.CommissionRecord(
                order_no=order.order_no, user_id=user_id,
                level=level, amount=commission, rate=rate,
            ))
    if pending_records:
        db.add_all(pending_records)
    order.commission_distributed = True


# ================= 认证 =================

@app.post("/api/v1/auth/login")
async def login(req: LoginReq, db: Session = Depends(get_db)):
    user = db.query(m.User).filter(m.User.username == req.username).first()
    if not user or not auth.verify_password(req.password, user.password_hash or ""):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = auth.create_token(user.id, user.username, user.role)
    return {
        "access_token": token, "token_type": "bearer",
        "user": {"id": user.id, "username": user.username, "role": user.role,
                 "wallet_balance": round(user.wallet_balance, 2),
                 "deposit_frozen": round(user.deposit_frozen, 2)},
    }


@app.post("/api/v1/auth/register")
async def register(req: RegisterReq, db: Session = Depends(get_db)):
    if db.query(m.User).filter(m.User.username == req.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = m.User(username=req.username, password_hash=auth.hash_password(req.password))
    if req.ref_user_id:
        parent = db.query(m.User).filter(m.User.id == req.ref_user_id).first()
        if parent:
            user.parent_id = parent.id
    db.add(user)
    db.commit()
    token = auth.create_token(user.id, user.username, user.role)
    return {
        "access_token": token, "token_type": "bearer",
        "user": {"id": user.id, "username": user.username, "role": user.role,
                 "wallet_balance": round(user.wallet_balance, 2),
                 "deposit_frozen": round(user.deposit_frozen, 2)},
    }


@app.get("/api/v1/user/me")
async def get_me(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取当前用户完整信息（含钱包、邀请等）"""
    user = db.query(m.User).filter(m.User.id == current_user["id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    invite_code = f"INV{user.id:06d}"
    invite_url = f"{os.getenv('APP_BASE_URL', 'http://localhost:5173')}/?ref={invite_code}"
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "wallet_balance": round(user.wallet_balance, 2),
        "deposit_frozen": round(user.deposit_frozen, 2),
        "available_balance": round(user.available_balance, 2),
        "invite_code": invite_code,
        "invite_url": invite_url,
        "alipay_account": user.alipay_account,
        "wechat_account": user.wechat_account,
        "total_withdrawn": round(user.total_withdrawn, 2),
        "team_size": user.team_size,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@app.put("/api/v1/user/profile")
async def update_profile(req: UpdateProfileReq, db: Session = Depends(get_db),
                         current_user: dict = Depends(get_current_user)):
    user = db.query(m.User).filter(m.User.id == current_user["id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if req.alipay_account is not None:
        user.alipay_account = req.alipay_account
    if req.wechat_account is not None:
        user.wechat_account = req.wechat_account
    db.commit()
    return {"message": "资料已更新"}


@app.put("/api/v1/user/password")
async def update_password(req: UpdatePasswordReq, db: Session = Depends(get_db),
                          current_user: dict = Depends(get_current_user)):
    user = db.query(m.User).filter(m.User.id == current_user["id"]).first()
    if not auth.verify_password(req.old_password, user.password_hash or ""):
        raise HTTPException(status_code=400, detail="旧密码错误")
    user.password_hash = auth.hash_password(req.new_password)
    db.commit()
    return {"message": "密码已更新"}


# ================= 充值 =================

@app.post("/api/v1/user/recharge")
async def recharge(req: RechargeReq, db: Session = Depends(get_db),
                   current_user: dict = Depends(get_current_user)):
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="充值金额必须大于0")
    user = db.query(m.User).filter(m.User.id == current_user["id"]).first()
    user.wallet_balance += req.amount
    db.add(m.RechargeRecord(user_id=user.id, amount=req.amount, method=req.method, status="completed"))
    db.commit()
    return {"message": "充值成功", "amount": req.amount, "wallet_balance": round(user.wallet_balance, 2)}


# ================= 钱包 & 提现 =================

@app.get("/api/v1/user/wallet")
async def get_wallet(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    user = db.query(m.User).filter(m.User.id == current_user["id"]).first()
    return {
        "wallet_balance": round(user.wallet_balance, 2),
        "deposit_frozen": round(user.deposit_frozen, 2),
        "available_balance": round(user.available_balance, 2),
        "deposit_amount": round(get_deposit_amount(db), 2),
        "total_withdrawn": round(user.total_withdrawn, 2),
    }


@app.post("/api/v1/user/withdraw")
async def withdraw(req: WithdrawReq, db: Session = Depends(get_db),
                   current_user: dict = Depends(get_current_user)):
    user = db.query(m.User).filter(m.User.id == current_user["id"]).first()
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="提现金额必须大于0")
    if user.available_balance < req.amount:
        raise HTTPException(status_code=400, detail=f"可提现余额不足（当前: {round(user.available_balance, 2)}）")
    w = m.WithdrawRequest(user_id=user.id, amount=req.amount, payment_info=req.payment_info)
    db.add(w)
    user.wallet_balance -= req.amount
    db.commit()
    return {"id": w.id, "amount": req.amount, "status": "pending"}


# ================= 制作者申请 =================

@app.post("/api/v1/creator/apply")
async def apply_creator(req: CreatorAppReq, db: Session = Depends(get_db),
                        current_user: dict = Depends(get_current_user)):
    if db.query(m.CreatorApplication).filter(
        m.CreatorApplication.user_id == current_user["id"],
        m.CreatorApplication.status == "pending"
    ).first():
        raise HTTPException(status_code=400, detail="已有待审核申请")
    deposit_amt = get_deposit_amount(db)
    user = db.query(m.User).filter(m.User.id == current_user["id"]).first()
    if user.wallet_balance < deposit_amt:
        raise HTTPException(status_code=400,
            detail=f"余额不足（需要保证金 {deposit_amt} 元，当前: {round(user.wallet_balance, 2)} 元）")
    user.deposit_frozen += deposit_amt
    db.add(m.CreatorApplication(
        user_id=current_user["id"], real_name=req.real_name, phone=req.phone,
        wechat=req.wechat, specialty=req.specialty,
        portfolio_desc=req.portfolio_desc, experience=req.experience,
    ))
    db.commit()
    return {"status": "pending", "message": "申请已提交，保证金已冻结"}


@app.get("/api/v1/creator/application")
async def get_application(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    a = db.query(m.CreatorApplication).filter(
        m.CreatorApplication.user_id == current_user["id"]
    ).order_by(m.CreatorApplication.created_at.desc()).first()
    if not a:
        return None
    return {"id": a.id, "status": a.status, "review_remark": a.review_remark,
            "real_name": a.real_name, "created_at": str(a.created_at)}


@app.post("/api/v1/creator/resign")
async def resign_creator(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    user = db.query(m.User).filter(m.User.id == current_user["id"]).first()
    if user.role != "creator":
        raise HTTPException(status_code=400, detail="当前不是制作者")
    deposit = user.deposit_frozen
    user.deposit_frozen = 0.0
    user.role = "user"
    db.commit()
    return {"message": "已退出制作者", "deposit_refunded": round(deposit, 2)}


# ================= 管理员 =================

@app.get("/api/v1/admin/applications")
async def admin_applications(
    status: Optional[str] = Query(None), page: int = Query(1), page_size: int = Query(20),
    db: Session = Depends(get_db), admin_user: dict = Depends(require_admin)):
    query = db.query(m.CreatorApplication).join(m.User)
    if status:
        query = query.filter(m.CreatorApplication.status == status)
    total = query.count()
    results = query.order_by(m.CreatorApplication.created_at.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "applications": [{
        "id": a.id, "user_id": a.user_id, "username": a.user.username,
        "real_name": a.real_name, "phone": a.phone, "wechat": a.wechat,
        "specialty": a.specialty, "portfolio_desc": a.portfolio_desc,
        "experience": a.experience, "status": a.status, "created_at": str(a.created_at),
        "review_remark": a.review_remark, "reviewed_at": str(a.reviewed_at) if a.reviewed_at else None,
    } for a in results]}


@app.post("/api/v1/admin/applications/review")
async def review_application(
    req: ReviewApplicationReq, db: Session = Depends(get_db), admin_user: dict = Depends(require_admin)):
    if req.status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="状态必须是 approved 或 rejected")
    a = db.query(m.CreatorApplication).filter(m.CreatorApplication.id == req.request_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="申请不存在")
    if a.status != "pending":
        raise HTTPException(status_code=400, detail="已处理")
    a.status = req.status
    a.review_remark = req.remark
    a.reviewed_at = datetime.now()
    if req.status == "approved":
        user = db.query(m.User).filter(m.User.id == a.user_id).first()
        if user:
            user.role = "creator"
    db.commit()
    return {"id": a.id, "status": a.status}


@app.get("/api/v1/admin/orders")
async def admin_orders(
    status: Optional[str] = Query(None), search: Optional[str] = Query(None),
    page: int = Query(1), page_size: int = Query(20),
    db: Session = Depends(get_db), admin_user: dict = Depends(require_admin)):
    query = db.query(m.Order, m.Template, m.User).outerjoin(
        m.Template, m.Order.template_id == m.Template.id
    ).outerjoin(m.User, m.Order.user_id == m.User.id)
    if status:
        query = query.filter(m.Order.status == status)
    if search:
        query = query.filter(m.Order.order_no.ilike(f"%{search}%") | m.Template.name.ilike(f"%{search}%"))
    total = query.count()
    results = query.order_by(m.Order.created_at.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "orders": [{
        "id": o.id, "order_no": o.order_no, "amount": o.amount,
        "status": o.status, "order_type": o.order_type,
        "template_name": t.name if t else "N/A", "user_name": u.username if u else "N/A",
        "creator_id": o.creator_id, "created_at": str(o.created_at),
    } for o, t, u in results]}


@app.get("/api/v1/admin/orders/{order_no}")
async def admin_order_detail(
    order_no: str, db: Session = Depends(get_db), admin_user: dict = Depends(require_admin)):
    order = db.query(m.Order).filter(m.Order.order_no == order_no).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    template = db.query(m.Template).filter(m.Template.id == order.template_id).first()
    user = db.query(m.User).filter(m.User.id == order.user_id).first() if order.user_id else None
    creator = db.query(m.User).filter(m.User.id == order.creator_id).first() if order.creator_id else None
    ref_user = db.query(m.User).filter(m.User.id == order.ref_user_id).first() if order.ref_user_id else None
    commissions = db.query(m.CommissionRecord).filter(m.CommissionRecord.order_no == order_no).all()
    refunds = db.query(m.RefundRequest).filter(m.RefundRequest.order_no == order_no).all()
    return {
        "order": {
            "id": order.id, "order_no": order.order_no, "amount": order.amount,
            "status": order.status, "order_type": order.order_type,
            "custom_requirements": order.custom_requirements,
            "commission_distributed": order.commission_distributed,
            "created_at": str(order.created_at),
            "template": {"id": template.id, "name": template.name} if template else None,
            "user": {"id": user.id, "username": user.username} if user else None,
            "creator": {"id": creator.id, "username": creator.username} if creator else None,
            "ref_user": {"id": ref_user.id, "username": ref_user.username} if ref_user else None,
        },
        "commissions": [{"user_id": c.user_id, "level": c.level, "amount": c.amount} for c in commissions],
        "refunds": [{"id": r.id, "refund_amount": r.refund_amount, "creator_deduction": r.creator_deduction,
                     "reason": r.reason, "status": r.status, "created_at": str(r.created_at)} for r in refunds],
    }


@app.get("/api/v1/admin/withdrawals")
async def admin_withdrawals(
    status: Optional[str] = Query(None), page: int = Query(1), page_size: int = Query(20),
    db: Session = Depends(get_db), admin_user: dict = Depends(require_admin)):
    query = db.query(m.WithdrawRequest, m.User).join(m.User)
    if status:
        query = query.filter(m.WithdrawRequest.status == status)
    total = query.count()
    results = query.order_by(m.WithdrawRequest.created_at.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "withdrawals": [{
        "id": w.id, "user_id": w.user_id, "username": u.username,
        "amount": w.amount, "payment_info": w.payment_info,
        "status": w.status, "created_at": str(w.created_at),
    } for w, u in results]}


@app.post("/api/v1/admin/withdrawals/review")
async def review_withdraw(
    req: ReviewWithdrawReq, db: Session = Depends(get_db), admin_user: dict = Depends(require_admin)):
    if req.status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="状态必须是 approved 或 rejected")
    w = db.query(m.WithdrawRequest).filter(m.WithdrawRequest.id == req.request_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="提现申请不存在")
    if w.status != "pending":
        raise HTTPException(status_code=400, detail="已处理")
    w.status = req.status
    w.admin_remark = req.remark
    w.reviewed_at = datetime.now()
    if req.status == "rejected":
        user = db.query(m.User).filter(m.User.id == w.user_id).first()
        if user:
            user.wallet_balance += w.amount
    else:
        user = db.query(m.User).filter(m.User.id == w.user_id).first()
        if user:
            user.total_withdrawn += w.amount
    db.commit()
    return {"id": w.id, "status": w.status}


# 分佣配置（兼容旧版）
@app.get("/api/v1/admin/commission-config")
async def get_commission_config(db: Session = Depends(get_db), admin_user: dict = Depends(require_admin)):
    return load_all_configs(db)


@app.put("/api/v1/admin/commission-config")
async def update_commission_config(
    req: UpdateCommissionConfigReq, db: Session = Depends(get_db), admin_user: dict = Depends(require_admin)):
    if req.level not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="级别必须是 1/2/3")
    key_map = {1: "level1_rate", 2: "level2_rate", 3: "level3_rate"}
    cfg = db.query(m.SystemConfig).filter(m.SystemConfig.key == key_map[req.level]).first()
    if not cfg:
        cfg = m.SystemConfig(key=key_map[req.level], value=req.rate)
        db.add(cfg)
    else:
        cfg.value = req.rate
        cfg.updated_at = datetime.now()
    db.commit()
    return {"level": req.level, "rate": req.rate, "message": f"第{req.level}级分佣比例已更新为 {req.rate*100:.0f}%"}


# 系统配置（新版统一）
@app.get("/api/v1/admin/config")
async def get_system_config(db: Session = Depends(get_db), admin_user: dict = Depends(require_admin)):
    return load_all_configs(db)


@app.put("/api/v1/admin/config")
async def update_system_config(
    req: UpdateSystemConfigReq, db: Session = Depends(get_db), admin_user: dict = Depends(require_admin)):
    valid_keys = ["download_price", "custom_price", "creator_rate",
                  "level1_rate", "level2_rate", "level3_rate", "deposit_amount"]
    if req.key not in valid_keys:
        raise HTTPException(status_code=400, detail=f"无效的配置项: {req.key}")
    if req.value < 0:
        raise HTTPException(status_code=400, detail="配置值不能为负数")
    cfg = db.query(m.SystemConfig).filter(m.SystemConfig.key == req.key).first()
    if not cfg:
        cfg = m.SystemConfig(key=req.key, value=req.value)
        db.add(cfg)
    else:
        cfg.value = req.value
        cfg.updated_at = datetime.now()
    db.commit()
    return {"key": req.key, "value": req.value, "message": "配置已更新"}


# 退款审核
@app.get("/api/v1/admin/refunds")
async def admin_refunds(
    status: Optional[str] = Query(None), page: int = Query(1), page_size: int = Query(20),
    db: Session = Depends(get_db), admin_user: dict = Depends(require_admin)):
    query = db.query(m.RefundRequest)
    if status:
        query = query.filter(m.RefundRequest.status == status)
    total = query.count()
    results = query.order_by(m.RefundRequest.created_at.desc()).offset((page-1)*page_size).limit(page_size).all()
    items = []
    for r in results:
        buyer = db.query(m.User).filter(m.User.id == r.buyer_id).first()
        creator = db.query(m.User).filter(m.User.id == r.creator_id).first() if r.creator_id else None
        items.append({"id": r.id, "order_no": r.order_no,
            "buyer": buyer.username if buyer else "未知",
            "creator": creator.username if creator else "无",
            "refund_amount": r.refund_amount, "creator_deduction": r.creator_deduction,
            "reason": r.reason, "status": r.status, "created_at": str(r.created_at)})
    return {"total": total, "page": page, "page_size": page_size, "refunds": items}


@app.post("/api/v1/admin/refunds/review")
async def review_refund(
    req: ReviewRefundReq, db: Session = Depends(get_db), admin_user: dict = Depends(require_admin)):
    if req.status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="状态必须是 approved 或 rejected")
    r = db.query(m.RefundRequest).filter(m.RefundRequest.id == req.refund_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="退款申请不存在")
    if r.status != "pending":
        raise HTTPException(status_code=400, detail="已处理")
    r.status = req.status
    r.admin_remark = req.remark
    r.reviewed_at = datetime.now()
    if req.status == "approved":
        order = db.query(m.Order).filter(m.Order.order_no == r.order_no).first()
        buyer = db.query(m.User).filter(m.User.id == r.buyer_id).first()
        if order:
            order.status = "refunded"
        if buyer:
            buyer.wallet_balance += r.refund_amount
        if r.creator_id:
            creator = db.query(m.User).filter(m.User.id == r.creator_id).first()
            if creator:
                creator.wallet_balance -= r.creator_deduction
    db.commit()
    return {"id": r.id, "status": r.status}


@app.get("/api/v1/admin/users")
async def admin_users(
    search: Optional[str] = Query(None), role: Optional[str] = Query(None),
    page: int = Query(1), page_size: int = Query(50),
    db: Session = Depends(get_db), admin_user: dict = Depends(require_admin)):
    query = db.query(m.User)
    if search:
        query = query.filter(m.User.username.ilike(f"%{search}%"))
    if role:
        query = query.filter(m.User.role == role)
    total = query.count()
    results = query.order_by(m.User.id).offset((page-1)*page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "users": [{
        "id": u.id, "username": u.username, "role": u.role,
        "wallet_balance": round(u.wallet_balance, 2),
        "deposit_frozen": round(u.deposit_frozen, 2),
        "team_size": u.team_size, "parent_id": u.parent_id,
        "created_at": str(u.created_at) if u.created_at else "N/A",
    } for u in results]}


@app.put("/api/v1/admin/users/{user_id}")
async def admin_update_user(
    user_id: int, req: UpdateUserReq, db: Session = Depends(get_db), admin_user: dict = Depends(require_admin)):
    user = db.query(m.User).filter(m.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if req.role and req.role in ("user", "promoter", "creator", "admin"):
        user.role = req.role
    if req.wallet_balance is not None and req.wallet_balance >= 0:
        user.wallet_balance = req.wallet_balance
    db.commit()
    return {"id": user.id, "role": user.role, "wallet_balance": round(user.wallet_balance, 2)}


@app.get("/api/v1/admin/dashboard")
async def admin_dashboard(db: Session = Depends(get_db), admin_user: dict = Depends(require_admin)):
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    paid_statuses = ["paid", "processing", "completed", "accepted", "in_progress", "delivered", "awaiting_claim"]
    total_users = db.query(m.User).count()
    total_orders = db.query(m.Order).count()
    total_revenue = (db.query(func.coalesce(func.sum(m.Order.amount), 0)).filter(
        m.Order.status.in_(paid_statuses)).scalar()) or 0.0
    today_orders = db.query(m.Order).filter(m.Order.created_at >= today_start).count()
    today_revenue = (db.query(func.coalesce(func.sum(m.Order.amount), 0)).filter(
        m.Order.created_at >= today_start, m.Order.status.in_(paid_statuses)).scalar()) or 0.0
    month_orders = db.query(m.Order).filter(m.Order.created_at >= month_start).count()
    month_revenue = (db.query(func.coalesce(func.sum(m.Order.amount), 0)).filter(
        m.Order.created_at >= month_start, m.Order.status.in_(paid_statuses)).scalar()) or 0.0
    total_commission = (db.query(func.coalesce(func.sum(m.CommissionRecord.amount), 0)).scalar()) or 0.0
    pending_orders = db.query(m.Order).filter(m.Order.status == "pending").count()
    pending_withdrawals = db.query(m.WithdrawRequest).filter(m.WithdrawRequest.status == "pending").count()
    pending_apps = db.query(m.CreatorApplication).filter(m.CreatorApplication.status == "pending").count()
    pending_refunds = db.query(m.RefundRequest).filter(m.RefundRequest.status == "pending").count()
    role_stats = {r: db.query(m.User).filter(m.User.role == r).count() for r in ["user", "promoter", "creator"]}
    status_stats = {s: db.query(m.Order).filter(m.Order.status == s).count() for s in
                    ["pending", "paid", "awaiting_claim", "in_progress", "delivered", "accepted", "refunded"]}
    trend = []
    for i in range(6, -1, -1):
        day = today_start - timedelta(days=i)
        nd = day + timedelta(days=1)
        count = db.query(m.Order).filter(m.Order.created_at >= day, m.Order.created_at < nd).count()
        rev = (db.query(func.coalesce(func.sum(m.Order.amount), 0)).filter(
            m.Order.created_at >= day, m.Order.created_at < nd, m.Order.status.in_(paid_statuses)).scalar()) or 0.0
        trend.append({"date": day.strftime("%m-%d"), "orders": count, "revenue": round(rev, 2)})
    return {
        "total_users": total_users, "total_orders": total_orders,
        "total_revenue": round(total_revenue, 2), "today_orders": today_orders,
        "today_revenue": round(today_revenue, 2), "month_orders": month_orders,
        "month_revenue": round(month_revenue, 2), "total_commission_paid": round(total_commission, 2),
        "pending_orders": pending_orders, "pending_withdrawals": pending_withdrawals,
        "pending_applications": pending_apps, "pending_refunds": pending_refunds,
        "role_stats": role_stats, "order_status_stats": status_stats, "daily_trend": trend,
    }


@app.get("/api/v1/admin/stats")
async def admin_stats(db: Session = Depends(get_db), admin_user: dict = Depends(require_admin)):
    paid_statuses = ["paid", "processing", "completed", "accepted", "in_progress", "delivered", "awaiting_claim"]
    return {
        "total_users": db.query(m.User).count(),
        "creator_count": db.query(m.User).filter(m.User.role == "creator").count(),
        "promoter_count": db.query(m.User).filter(m.User.role == "promoter").count(),
        "pending_approvals": db.query(m.CreatorApplication).filter(m.CreatorApplication.status == "pending").count(),
        "total_revenue": round((db.query(func.coalesce(func.sum(m.Order.amount), 0)).filter(
            m.Order.status.in_(paid_statuses)).scalar()) or 0.0, 2),
        "total_commission": round((db.query(func.coalesce(func.sum(m.CommissionRecord.amount), 0)).scalar()) or 0.0, 2),
        "pending_withdrawals": db.query(m.WithdrawRequest).filter(m.WithdrawRequest.status == "pending").count(),
    }


# ================= 模板 =================

@app.get("/api/v1/templates")
async def list_templates(
    category: Optional[str] = Query(None), search: Optional[str] = Query(None),
    page: int = Query(1), page_size: int = Query(20), db: Session = Depends(get_db)):
    query = db.query(m.Template).filter(m.Template.is_active == True)
    if category:
        query = query.filter(m.Template.category == category)
    if search:
        query = query.filter(m.Template.name.ilike(f"%{search}%"))
    total = query.count()
    results = query.order_by(m.Template.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "templates": [{
        "id": t.id, "name": t.name, "category": t.category, "price": t.price, "jpg_path": t.jpg_path,
    } for t in results]}


@app.get("/api/v1/templates/{template_id}")
async def get_template(template_id: int, db: Session = Depends(get_db)):
    t = db.query(m.Template).filter(m.Template.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="模板不存在")
    return {"id": t.id, "name": t.name, "category": t.category,
            "price": t.price, "jpg_path": t.jpg_path, "doc_path": t.doc_path}


# ================= 订单 =================

@app.post("/api/v1/orders")
async def create_order(
    req: CreateOrderReq, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    template = db.query(m.Template).filter(m.Template.id == req.template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    configs = load_all_configs(db)
    amount = configs["custom_price"] if is_custom_order(req.order_type) else configs["download_price"]
    order_no = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    order = m.Order(
        order_no=order_no, user_id=current_user["id"], template_id=template.id,
        amount=amount, ref_user_id=req.ref_user_id, order_type=req.order_type,
        custom_requirements=req.custom_requirements,
    )
    db.add(order)
    db.commit()
    return {"order_no": order_no, "amount": amount, "type": req.order_type, "template_name": template.name}


@app.post("/api/v1/payments/mock-callback")
async def mock_payment_callback(req: MockPayReq, db: Session = Depends(get_db)):
    order = db.query(m.Order).filter(m.Order.order_no == req.order_no).first()
    if not order or order.status != "pending":
        return {"status": "error"}
    if is_custom_order(order.order_type):
        order.status = "awaiting_claim"
    else:
        order.status = "completed"
        distribute_commission(order, db)
    db.commit()
    return {"status": "success"}


@app.post("/api/v1/payments/payjs-qrcode")
async def payjs_qrcode(req: PayReq, db: Session = Depends(get_db)):
    order = db.query(m.Order).filter(m.Order.order_no == req.order_no).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status != "pending":
        raise HTTPException(status_code=400, detail="订单状态异常")
    total_fee = int(order.amount * 100)
    result = create_native_qrcode(order.order_no, total_fee, "简历模板下载", str(order.template_id or ""))
    if not result["success"]:
        return {"success": False, "message": result["message"], "qrcode": None}
    return {"success": True, "message": "请使用微信扫码支付",
            "qrcode": result["data"]["qrcode"], "code_url": result["data"]["code_url"],
            "payjs_order_id": result["data"]["payjs_order_id"], "amount": order.amount}


@app.post("/api/v1/payments/payjs-notify")
async def payjs_notify(request: Request, db: Session = Depends(get_db)):
    body = await request.form()
    params = dict(body)
    if not verify_payjs_sign(params, PAYJS_KEY):
        logger.warning(f"PayJS 回调签名验证失败: {params}")
        return "sign error"
    if params.get("return_code") != "1":
        return "fail"
    order = db.query(m.Order).filter(m.Order.order_no == params.get("out_trade_no", "")).first()
    if not order:
        return "order not found"
    if order.status in ("paid", "completed", "awaiting_claim"):
        return "success"
    if is_custom_order(order.order_type):
        order.status = "awaiting_claim"
    else:
        order.status = "completed"
        distribute_commission(order, db)
    db.commit()
    return "success"


@app.get("/api/v1/orders/status/{order_no}")
async def get_order_status(order_no: str, db: Session = Depends(get_db)):
    order = db.query(m.Order).filter(m.Order.order_no == order_no).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return {"order_no": order.order_no, "status": order.status, "amount": order.amount, "order_type": order.order_type}


@app.get("/api/v1/orders/download/{order_no}")
async def download_by_order(order_no: str, db: Session = Depends(get_db)):
    order = db.query(m.Order).filter(m.Order.order_no == order_no).first()
    if not order or order.status not in ["paid", "processing", "completed"]:
        raise HTTPException(status_code=403, detail="未支付或无权下载")
    template = db.query(m.Template).filter(m.Template.id == order.template_id).first()
    full_path = os.path.abspath(os.path.join(ASSETS_DIR, template.doc_path))
    return FileResponse(full_path, media_type="application/msword", filename=f"{template.name}.doc")


# ================= 众包大厅 =================

@app.get("/api/v1/creator/orders")
async def get_creator_orders(
    tab: str = "pending", db: Session = Depends(get_db), current_user: dict = Depends(require_creator)):
    query = db.query(m.Order, m.Template).join(m.Template).filter(
        m.Order.order_type.in_(("custom_service", "custom"))
    )
    if tab == "pending":
        results = query.filter(m.Order.status == "awaiting_claim", m.Order.creator_id == None).all()
    else:
        results = query.filter(m.Order.creator_id == current_user["id"]).all()
    return [{"order_no": o.order_no, "amount": o.amount, "status": o.status,
             "requirements": o.custom_requirements, "created_at": str(o.created_at),
             "template_name": f"{t.category}-{t.name}"} for o, t in results]


@app.post("/api/v1/creator/take")
async def take_order(
    req: TakeOrderReq, db: Session = Depends(get_db), current_user: dict = Depends(require_creator)):
    order = db.query(m.Order).filter(
        m.Order.order_no == req.order_no, m.Order.status == "awaiting_claim", m.Order.creator_id == None).first()
    if not order:
        raise HTTPException(status_code=400, detail="订单已被抢走或状态错误")
    user = db.query(m.User).filter(m.User.id == current_user["id"]).first()
    deposit_amt = get_deposit_amount(db)
    if user.wallet_balance < deposit_amt:
        raise HTTPException(status_code=400,
            detail=f"余额不足（需要 ≥ {deposit_amt} 元保证金，当前: {round(user.wallet_balance, 2)} 元）")
    order.creator_id = current_user["id"]
    order.status = "in_progress"
    order.claimed_at = datetime.now()
    order.penalty_count = 0
    order.penalty_deducted = 0.0
    db.commit()
    return {"status": "success", "message": "抢单成功"}


@app.post("/api/v1/creator/deliver")
async def deliver_order(
    req: DeliverReq, db: Session = Depends(get_db), current_user: dict = Depends(require_creator)):
    order = db.query(m.Order).filter(
        m.Order.order_no == req.order_no, m.Order.creator_id == current_user["id"],
        m.Order.status == "in_progress").first()
    if not order:
        raise HTTPException(status_code=400, detail="订单异常或无权操作")
    db.add(m.Delivery(order_no=req.order_no, file_url=req.file_url, remark=req.remark))
    order.status = "delivered"
    order.delivered_at = datetime.now()
    order.freeze_until = datetime.now() + timedelta(days=7)
    db.commit()
    return {"status": "success", "message": "已交付，等待买家验收"}


# ================= 买家验收 =================

@app.post("/api/v1/orders/review")
async def review_delivery(
    req: ReviewReq, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    order = db.query(m.Order).filter(
        m.Order.order_no == req.order_no, m.Order.user_id == current_user["id"],
        m.Order.status == "delivered").first()
    if not order:
        raise HTTPException(status_code=400, detail="订单异常或无权操作")
    db.add(m.Review(order_no=req.order_no, result=req.result, buyer_remark=req.buyer_remark))
    if req.result == "accepted":
        order.status = "accepted"
        order.accepted_at = datetime.now()
        settle_custom_commission(order, db)
    elif req.result == "rejected":
        order.status = "in_progress"
    else:
        raise HTTPException(status_code=400, detail="验收结果必须是 accepted 或 rejected")
    db.commit()
    msg = "验收通过，佣金将进入冻结期" if req.result == "accepted" else "已退回制作者重新制作"
    return {"status": "success", "message": msg}


# ================= 退款申请 =================

@app.post("/api/v1/orders/refund")
async def request_refund(
    req: RefundReq, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    order = db.query(m.Order).filter(
        m.Order.order_no == req.order_no, m.Order.user_id == current_user["id"],
        m.Order.order_type.in_(("custom_service", "custom"))).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status not in ("delivered", "in_progress"):
        raise HTTPException(status_code=400, detail="仅拒收场景可退款")
    if db.query(m.RefundRequest).filter(
        m.RefundRequest.order_no == req.order_no, m.RefundRequest.status.in_(["approved", "pending"])).first():
        raise HTTPException(status_code=400, detail="该订单已有退款申请")
    refund_amount = round(order.amount / 2, 2)
    creator_deduction = round(order.amount / 2, 2)
    r = m.RefundRequest(
        order_no=req.order_no, buyer_id=current_user["id"], creator_id=order.creator_id,
        refund_amount=refund_amount, creator_deduction=creator_deduction, reason=req.reason,
    )
    db.add(r)
    order.status = "refund_requested"
    db.commit()
    return {"id": r.id, "refund_amount": refund_amount, "creator_deduction": creator_deduction,
            "status": "pending", "message": "退款申请已提交，等待管理员审核"}


# ================= 冻结期扫描 =================

@app.post("/api/v1/admin/commission/release-frozen")
async def release_frozen_commissions(db: Session = Depends(get_db), admin_user: dict = Depends(require_admin)):
    now = datetime.now()
    pending = db.query(m.CommissionPending).filter(
        m.CommissionPending.status == "pending", m.CommissionPending.freeze_until <= now).all()
    count = 0
    for p in pending:
        user = db.query(m.User).filter(m.User.id == p.user_id).first()
        if user:
            user.wallet_balance += p.amount
            count += 1
        p.status = "released"
        p.released_at = now
    auto_accept = db.query(m.Order).filter(m.Order.status == "delivered", m.Order.freeze_until <= now).all()
    auto_count = 0
    for order in auto_accept:
        order.status = "accepted"
        order.accepted_at = now
        settle_custom_commission(order, db)
        auto_count += 1
    db.commit()
    return {"released_commissions": count, "auto_accepted_orders": auto_count,
            "message": f"释放 {count} 笔佣金，自动验收 {auto_count} 个订单"}


# ================= 买家订单列表 =================

@app.get("/api/v1/orders/my")
async def get_my_orders(
    order_type: str = "custom_service", db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)):
    orders = db.query(m.Order).filter(
        m.Order.user_id == current_user["id"], m.Order.order_type == order_type
    ).order_by(m.Order.created_at.desc()).all()
    result = []
    for o in orders:
        template = db.query(m.Template).filter(m.Template.id == o.template_id).first()
        result.append({"order_no": o.order_no,
            "template_name": template.name if template else "未知模板",
            "order_type": o.order_type, "amount": o.amount, "status": o.status,
            "custom_requirements": o.custom_requirements, "creator_id": o.creator_id,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "delivered_at": o.delivered_at.isoformat() if o.delivered_at else None,
            "freeze_until": o.freeze_until.isoformat() if o.freeze_until else None,
            "accepted_at": o.accepted_at.isoformat() if o.accepted_at else None,
        })
    return result


# ================= 健康检查 =================

@app.get("/api/v1/health")
async def health(db: Session = Depends(get_db)):
    return {"status": "ok", "templates_count": db.query(m.Template).count()}


# ================= 用户端端点 =================

@app.get("/api/v1/user/team")
async def get_team(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取用户团队信息（1/2/3 级）"""
    uid = current_user["id"]
    user = db.query(m.User).filter(m.User.id == uid).first()
    if not user:
        raise HTTPException(404, "用户不存在")

    # 0 级（自己）
    level_0 = {"id": user.id, "username": user.username, "role": user.role, "wallet_balance": user.wallet_balance}

    # 1 级（直接下级）
    l1 = db.query(m.User).filter(m.User.parent_id == uid).all()
    level_1 = [{"id": u.id, "username": u.username, "role": u.role, "wallet_balance": u.wallet_balance} for u in l1]
    l1_ids = {u.id for u in l1}

    # 2 级（1 级的下级）
    level_2 = []
    if l1_ids:
        l2 = db.query(m.User).filter(m.User.parent_id.in_(l1_ids)).all()
        level_2 = [{"id": u.id, "username": u.username, "role": u.role, "wallet_balance": u.wallet_balance} for u in l2]
        l2_ids = {u.id for u in l2}
    else:
        l2_ids = set()

    # 3 级（2 级的下级）
    level_3 = []
    if l2_ids:
        l3 = db.query(m.User).filter(m.User.parent_id.in_(l2_ids)).all()
        level_3 = [{"id": u.id, "username": u.username, "role": u.role, "wallet_balance": u.wallet_balance} for u in l3]

    return {"level_0": level_0, "level_1": level_1, "level_2": level_2, "level_3": level_3}


@app.get("/api/v1/user/commission-history")
async def get_commission_history(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取用户佣金明细"""
    uid = current_user["id"]
    records = db.query(m.CommissionRecord).filter(m.CommissionRecord.user_id == uid).order_by(m.CommissionRecord.created_at.desc()).all()
    return [{
        "id": r.id,
        "order_no": r.order_no,
        "level": r.level,
        "amount": r.amount,
        "rate": r.rate,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in records]


@app.get("/api/v1/user/stats/{user_id}")
async def get_user_stats(user_id: int, db: Session = Depends(get_db)):
    """获取用户统计信息"""
    user = db.query(m.User).filter(m.User.id == user_id).first()
    if not user:
        raise HTTPException(404, "用户不存在")

    total_commission = db.query(func.sum(m.CommissionRecord.amount)).filter(m.CommissionRecord.user_id == user_id).scalar() or 0.0
    team_count = db.query(m.User).filter(m.User.parent_id == user_id).count()
    order_count = db.query(m.Order).filter(m.Order.user_id == user_id).count()

    return {
        "user_id": user_id,
        "total_commission": total_commission,
        "team_count": team_count,
        "order_count": order_count,
    }


# ================= 静态文件服务 =================

app.mount("/static", StaticFiles(directory="/root/assets"), name="static")

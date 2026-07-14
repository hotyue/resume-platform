"""业务逻辑层 — 配置、分佣、交付、PayJS、OAuth"""
import os
import hashlib
import hmac
import urllib.parse
import urllib.request
import json as _json
import subprocess
import base64
import time
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

import models as m


# ---------------------------------------------------------------------------
# 系统配置
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
        "level2_rate": "二级推广分佣比例", "level3_rate": "三级推广分佣比例(已停用)",
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
        "level1_rate": get_config(db, "level1_rate", 0.30),
        "level2_rate": get_config(db, "level2_rate", 0.10),
        "level3_rate": get_config(db, "level3_rate", 0.00),
        "deposit_amount": get_config(db, "deposit_amount", 20.0),
        "auto_accept_hours": get_config(db, "auto_accept_hours", 168),
    }


def get_deposit_amount(db: Session) -> float:
    return get_config(db, "deposit_amount", 20.0)


def get_auto_accept_hours(db: Session) -> int:
    cfg = db.query(m.SystemConfig).filter(m.SystemConfig.key == "auto_accept_hours").first()
    if cfg:
        try:
            return int(cfg.value)
        except (ValueError, TypeError):
            pass
    return 168


# ---------------------------------------------------------------------------
# 审计日志
# ---------------------------------------------------------------------------
def audit_log(db: Session, user_id: int, order_no: str, action: str, detail: str = None, penalty_amount: float = 0.0):
    log = m.CreatorAuditLog(
        user_id=user_id,
        order_no=order_no,
        action=action,
        detail=detail,
        penalty_amount=penalty_amount,
        created_at=datetime.now(),
    )
    db.add(log)


def reset_delivery_cycle(order, db: Session):
    order.claimed_at = datetime.now()
    audit_log(db, order.creator_id, order.order_no, "cycle_reset",
              "交付周期重置，重新计时24小时")


# ---------------------------------------------------------------------------
# 交付超时检查
# ---------------------------------------------------------------------------
def check_delivery_penalties(db: Session) -> list:
    now = datetime.now()
    in_progress_orders = db.query(m.Order).filter(
        m.Order.status == "in_progress",
        m.Order.claimed_at != None,
        m.Order.creator_id != None,
    ).all()

    results = []
    for order in in_progress_orders:
        if not order.claimed_at:
            continue

        elapsed = now - order.claimed_at
        elapsed_hours = elapsed.total_seconds() / 3600

        if elapsed_hours >= 72:
            creator_id = order.creator_id
            order_no = order.order_no
            order.status = "awaiting_claim"
            order.creator_id = None
            order.claimed_at = None
            order.penalty_count = 5
            order.penalty_deducted = round(order.amount * 0.50, 2)
            audit_log(db, creator_id, order_no, "order_republished",
                      f"72h超时重新发布至众包大厅（累计违约金 ¥{order.penalty_deducted}）")
            results.append({
                "order_no": order_no,
                "creator_id": creator_id,
                "action": "republished",
                "reason": "72h超时",
            })
            continue

        if elapsed_hours < 24:
            continue

        overdue_hours = elapsed_hours - 24
        expected_penalty_count = int(overdue_hours / 8) + 1
        expected_penalty_count = min(expected_penalty_count, 5)

        current_count = order.penalty_count or 0
        if expected_penalty_count > current_count:
            new_penalties = expected_penalty_count - current_count
            penalty_per_unit = round(order.amount * 0.10, 2)
            total_new_penalty = round(penalty_per_unit * new_penalties, 2)

            creator = db.query(m.User).filter(m.User.id == order.creator_id).first()
            if creator:
                can_deduct = min(total_new_penalty, creator.wallet_balance)
                creator.wallet_balance -= can_deduct
                if can_deduct < total_new_penalty:
                    audit_log(db, order.creator_id, order.order_no, "penalty_insufficient",
                              f"余额不足以支付违约金：需 ¥{total_new_penalty}，仅扣 ¥{can_deduct}")

            order.penalty_count = expected_penalty_count
            order.penalty_deducted = round((order.penalty_deducted or 0) + total_new_penalty, 2)
            audit_log(db, order.creator_id, order.order_no, "penalty_deducted",
                      f"超时违约金：已逾期 {elapsed_hours:.1f}h，第 {expected_penalty_count} 个周期，"
                      f"扣除 ¥{total_new_penalty}（累计 ¥{order.penalty_deducted}）",
                      penalty_amount=total_new_penalty)
            results.append({
                "order_no": order.order_no,
                "creator_id": order.creator_id,
                "penalty": total_new_penalty,
                "total_deducted": order.penalty_deducted,
            })

    if results:
        db.commit()
    return results


# ---------------------------------------------------------------------------
# 分销链 & 分佣
# ---------------------------------------------------------------------------
def _update_team_size(user_id: int, db: Session):
    user = db.query(m.User).filter(m.User.id == user_id).first()
    if not user:
        return
    user.team_size = (user.team_size or 0) + 1
    if user.parent_id:
        _update_team_size(user.parent_id, db)


def get_ref_chain(ref_user_id: int, db: Session, rates: list = None) -> list:
    if rates is None:
        rates = [0.30, 0.10]
    chain = []
    uid = ref_user_id
    for level in range(len(rates)):
        if uid is None:
            break
        user = db.query(m.User).filter(m.User.id == uid).first()
        if not user:
            break
        chain.append((uid, level, rates[level]))
        uid = user.parent_id
    return chain


REFERRAL_RATES = [0.30, 0.10]


def distribute_commission(order: m.Order, db: Session):
    """下载订单 — 推荐分佣即时到账"""
    if order.commission_distributed:
        return
    amount = order.amount
    user = db.query(m.User).filter(m.User.id == order.user_id).first()
    if not user or not user.parent_id:
        order.commission_distributed = True
        return

    chain = get_ref_chain(user.parent_id, db, REFERRAL_RATES)
    for user_id, level, rate in chain:
        commission = round(amount * rate, 2)
        if commission <= 0:
            continue
        u = db.query(m.User).filter(m.User.id == user_id).first()
        if u:
            u.wallet_balance += commission
            u.referral_commission += commission
        db.add(m.CommissionRecord(
            order_no=order.order_no, user_id=user_id,
            level=level, amount=commission, rate=rate,
        ))
    order.commission_distributed = True


def create_freeze_pending(order: m.Order, db: Session):
    """定制订单交付时创建冻结记录"""
    if order.commission_distributed:
        return
    amount = order.amount
    hours = get_auto_accept_hours(db)
    freeze_until = datetime.now() + timedelta(hours=hours)
    pending_records = []

    if not order.creator_id:
        order.commission_distributed = True
        return

    creator_amt = round(amount * 0.30, 2)
    pending_records.append(m.CommissionPending(
        order_no=order.order_no, user_id=order.creator_id,
        role_type="creator", amount=creator_amt, rate=0.30,
        freeze_until=freeze_until,
    ))

    creator = db.query(m.User).filter(m.User.id == order.creator_id).first()
    if creator and creator.parent_id:
        parent_amt = round(amount * 0.10, 2)
        pending_records.append(m.CommissionPending(
            order_no=order.order_no, user_id=creator.parent_id,
            role_type="referral", amount=parent_amt, rate=0.10,
            freeze_until=freeze_until,
        ))

    if pending_records:
        db.add_all(pending_records)
    order.commission_distributed = True


def settle_custom_commission(order: m.Order, db: Session):
    """验收通过 — 释放冻结佣金"""
    pending = db.query(m.CommissionPending).filter(
        m.CommissionPending.order_no == order.order_no,
        m.CommissionPending.status == "pending"
    ).all()
    now = datetime.now()
    for p in pending:
        user = db.query(m.User).filter(m.User.id == p.user_id).first()
        if user:
            if p.role_type == "creator":
                user.making_commission += p.amount
            else:
                user.referral_commission += p.amount
            user.wallet_balance += p.amount
        p.status = "settled"
        p.settled_at = now
        db.add(m.CommissionRecord(
            order_no=order.order_no, user_id=p.user_id,
            level=0 if p.role_type == "creator" else 1,
            amount=p.amount, rate=p.rate,
        ))


def refund_commission(order: m.Order, db: Session):
    """退款 — 收回冻结佣金"""
    pending = db.query(m.CommissionPending).filter(
        m.CommissionPending.order_no == order.order_no,
        m.CommissionPending.status == "pending"
    ).all()
    for p in pending:
        user = db.query(m.User).filter(m.User.id == p.user_id).first()
        if user:
            user.wallet_balance = max(0, user.wallet_balance - p.amount)
        p.status = "cancelled"
        db.add(m.CommissionRecord(
            order_no=order.order_no, user_id=p.user_id,
            level=0 if p.role_type == "creator" else 1,
            amount=-p.amount, rate=0,
        ))


# ---------------------------------------------------------------------------
# PayJS
# ---------------------------------------------------------------------------
PAYJS_MCHID = os.getenv("PAYJS_MCHID", "")
PAYJS_KEY = os.getenv("PAYJS_KEY", "")

import requests as req_lib


def create_native_qrcode(out_trade_no: str, total_fee: int, body: str = "简历模板下载", attach: str = ""):
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
# OAuth helpers
# ---------------------------------------------------------------------------
def oauth_redirect(provider: str, state: str) -> str:
    if provider == "wechat":
        app_id = os.getenv("WECHAT_APP_ID")
        redirect_uri = os.getenv("WECHAT_REDIRECT_URI")
        if not app_id or not redirect_uri:
            raise ValueError("微信 OAuth 未配置")
        base = "https://open.weixin.qq.com/connect/qrconnect"
        params = {
            "appid": app_id, "redirect_uri": redirect_uri,
            "response_type": "code", "scope": "snsapi_login", "state": state,
        }
        return f"{base}?{urllib.parse.urlencode(params)}#wechat_redirect"
    elif provider == "alipay":
        app_id = os.getenv("ALIPAY_APP_ID")
        redirect_uri = os.getenv("ALIPAY_REDIRECT_URI")
        if not app_id or not redirect_uri:
            raise ValueError("支付宝 OAuth 未配置")
        base = "https://openauth.alipay.com/oauth2/publicAppAuthorize.htm"
        params = {
            "app_id": app_id, "redirect_uri": redirect_uri,
            "scope": "auth_user", "state": state,
        }
        return f"{base}?{urllib.parse.urlencode(params)}"
    else:
        raise ValueError(f"不支持的提供商: {provider}")


def wechat_get_userinfo(code: str) -> dict:
    app_id = os.getenv("WECHAT_APP_ID")
    app_secret = os.getenv("WECHAT_APP_SECRET")
    redirect_uri = os.getenv("WECHAT_REDIRECT_URI")
    if not app_id or not app_secret or not redirect_uri:
        raise ValueError("微信 OAuth 配置不完整")

    token_url = "https://api.weixin.qq.com/sns/oauth2/access_token"
    params = {
        "appid": app_id, "secret": app_secret, "code": code,
        "grant_type": "authorization_code", "redirect_uri": redirect_uri,
    }
    url = f"{token_url}?{urllib.parse.urlencode(params)}"
    resp = urllib.request.urlopen(url, timeout=10).read().decode()
    data = _json.loads(resp)
    if "errcode" in data:
        raise ValueError(f"微信授权错误: {data.get('errmsg', '未知错误')}")

    access_token = data["access_token"]
    openid = data["openid"]
    unionid = data.get("unionid")

    info_url = f"https://api.weixin.qq.com/sns/userinfo?access_token={access_token}&openid={openid}&lang=zh_CN"
    resp = urllib.request.urlopen(info_url, timeout=10).read().decode()
    userinfo = _json.loads(resp)
    if "errcode" in userinfo:
        raise ValueError(f"获取用户信息错误: {userinfo.get('errmsg', '未知错误')}")

    return {
        "openid": openid, "unionid": unionid,
        "nickname": userinfo.get("nickname", ""),
        "headimgurl": userinfo.get("headimgurl", ""),
        "access_token": access_token,
    }


def alipay_get_userinfo(auth_code: str) -> dict:
    raise NotImplementedError("支付宝 OAuth 暂需安装 alipay-sdk-python，当前为框架占位")


# ---------------------------------------------------------------------------
# 文件校验
# ---------------------------------------------------------------------------
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_DOC_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}
ALLOWED_TYPES = ALLOWED_IMAGE_TYPES | ALLOWED_DOC_TYPES
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

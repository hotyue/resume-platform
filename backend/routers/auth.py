"""认证路由 — login / register / OAuth / 第三方绑定"""
import os
import json
import urllib.parse
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
import models as m
from auth import create_token, hash_password, verify_password, get_current_user

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


# ================= Schemas =================

class LoginReq(BaseModel):
    username: str
    password: str


class RegisterReq(BaseModel):
    username: str
    password: str
    ref_user_id: Optional[int] = None
    invite_code: Optional[str] = None


class BindThirdPartyReq(BaseModel):
    provider: str
    code: str
    state: str = ""


# ================= Helpers =================

def _update_team_size(parent_id: int, db: Session):
    user = db.query(m.User).filter(m.User.id == parent_id).first()
    if not user:
        return
    user.team_size = (user.team_size or 0) + 1
    if user.parent_id:
        _update_team_size(user.parent_id, db)


def _build_roles(user: m.User, db: Session) -> list:
    roles = [user.role]
    if db.query(m.CreatorApplication).filter(
        m.CreatorApplication.user_id == user.id,
        m.CreatorApplication.status == "approved"
    ).first():
        roles.append("creator")
    if (user.team_size or 0) > 0:
        roles.append("promoter")
    return roles


def _oauth_redirect(provider: str, state: str):
    """构建 OAuth 授权跳转 URL"""
    if provider == "wechat":
        app_id = os.getenv("WECHAT_APP_ID")
        redirect_uri = os.getenv("WECHAT_REDIRECT_URI")
        if not app_id or not redirect_uri:
            raise HTTPException(400, "微信 OAuth 未配置")
        base = "https://open.weixin.qq.com/connect/qrconnect"
        params = {
            "appid": app_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "snsapi_login",
            "state": state,
        }
        return f"{base}?{urllib.parse.urlencode(params)}#wechat_redirect"
    elif provider == "alipay":
        app_id = os.getenv("ALIPAY_APP_ID")
        redirect_uri = os.getenv("ALIPAY_REDIRECT_URI")
        if not app_id or not redirect_uri:
            raise HTTPException(400, "支付宝 OAuth 未配置")
        base = "https://openauth.alipay.com/oauth2/publicAppAuthorize.htm"
        params = {
            "app_id": app_id,
            "redirect_uri": redirect_uri,
            "scope": "auth_user",
            "state": state,
        }
        return f"{base}?{urllib.parse.urlencode(params)}"
    else:
        raise HTTPException(400, f"不支持的提供商: {provider}")


def _wechat_get_userinfo(code: str):
    """通过微信 code 获取 access_token 和用户信息"""
    app_id = os.getenv("WECHAT_APP_ID")
    app_secret = os.getenv("WECHAT_APP_SECRET")
    redirect_uri = os.getenv("WECHAT_REDIRECT_URI")
    if not app_id or not app_secret or not redirect_uri:
        raise HTTPException(500, "微信 OAuth 配置不完整")

    # Step 1: 获取 access_token
    token_url = "https://api.weixin.qq.com/sns/oauth2/access_token"
    params = {
        "appid": app_id,
        "secret": app_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }
    url = f"{token_url}?{urllib.parse.urlencode(params)}"
    try:
        resp = urllib.request.urlopen(url, timeout=10).read().decode()
        data = json.loads(resp)
    except Exception as e:
        raise HTTPException(500, f"微信授权失败: {str(e)}")

    if "errcode" in data:
        raise HTTPException(400, f"微信授权错误: {data.get('errmsg', '未知错误')}")

    access_token = data["access_token"]
    openid = data["openid"]
    unionid = data.get("unionid")

    # Step 2: 获取用户信息
    info_url = f"https://api.weixin.qq.com/sns/userinfo?access_token={access_token}&openid={openid}&lang=zh_CN"
    try:
        resp = urllib.request.urlopen(info_url, timeout=10).read().decode()
        userinfo = json.loads(resp)
    except Exception as e:
        raise HTTPException(500, f"获取微信用户信息失败: {str(e)}")

    if "errcode" in userinfo:
        raise HTTPException(400, f"获取用户信息错误: {userinfo.get('errmsg', '未知错误')}")

    return {
        "openid": openid,
        "unionid": unionid,
        "nickname": userinfo.get("nickname", ""),
        "headimgurl": userinfo.get("headimgurl", ""),
        "access_token": access_token,
    }


def _alipay_get_userinfo(auth_code: str):
    """通过支付宝 auth_code 获取用户信息"""
    app_id = os.getenv("ALIPAY_APP_ID")
    app_private_key = os.getenv("ALIPAY_PRIVATE_KEY")
    redirect_uri = os.getenv("ALIPAY_REDIRECT_URI")
    if not app_id or not app_private_key or not redirect_uri:
        raise HTTPException(500, "支付宝 OAuth 配置不完整")

    # 支付宝使用 RSA 签名，这里用简化方案
    import subprocess
    import base64
    import hashlib
    import time

    biz_content = json.dumps({
        "auth_code": auth_code,
        "scope": "auth_user",
    })

    # 简化处理：实际生产需要 alipay-sdk
    raise HTTPException(501, "支付宝 OAuth 暂需安装 alipay-sdk-python，当前为框架占位")


# ================= Login / Register =================

@router.post("/login")
async def login(req: LoginReq, db: Session = Depends(get_db)):
    user = db.query(m.User).filter(m.User.username == req.username).first()
    if not user or not verify_password(req.password, user.password_hash or ""):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_token(user.id, user.username, user.role)
    return {
        "access_token": token, "token_type": "bearer",
        "user": {
            "id": user.id, "username": user.username, "role": user.role,
            "roles": _build_roles(user, db),
            "wallet_balance": round(user.wallet_balance, 2),
            "deposit_frozen": round(user.deposit_frozen, 2),
        },
    }


@router.post("/register")
async def register(req: RegisterReq, db: Session = Depends(get_db)):
    if db.query(m.User).filter(m.User.username == req.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = m.User(username=req.username, password_hash=hash_password(req.password))

    # 解析推广关系：优先 invite_code，兼容 ref_user_id
    parent_id = None
    if req.invite_code:
        code = req.invite_code.strip()
        # 格式 1: 纯数字用户ID
        try:
            parent_id = int(code)
        except ValueError:
            pass
        # 格式 2: INV 推广码
        if not parent_id:
            upper_code = code.upper()
            if upper_code.startswith("INV"):
                try:
                    parent_id = int(upper_code[3:])
                except ValueError:
                    pass
        # 格式 3: 用户名
        if not parent_id:
            parent = db.query(m.User).filter(m.User.username == code).first()
            if parent:
                parent_id = parent.id
        # 最终验证
        parent = db.query(m.User).filter(m.User.id == parent_id).first() if parent_id else None
        if parent:
            user.parent_id = parent.id
            _update_team_size(parent.id, db)
    elif req.ref_user_id:
        parent = db.query(m.User).filter(m.User.id == req.ref_user_id).first()
        if parent:
            user.parent_id = parent.id
            _update_team_size(parent.id, db)

    db.add(user)
    db.commit()
    token = create_token(user.id, user.username, user.role)
    return {
        "access_token": token, "token_type": "bearer",
        "user": {
            "id": user.id, "username": user.username, "role": user.role,
            "wallet_balance": round(user.wallet_balance, 2),
            "deposit_frozen": round(user.deposit_frozen, 2),
        },
    }


# ================= OAuth =================

@router.get("/oauth/{provider}/redirect")
async def oauth_redirect(provider: str, db: Session = Depends(get_db)):
    """OAuth 授权跳转"""
    state = secrets.token_urlsafe(16)
    redirect_url = _oauth_redirect(provider, state)
    return {"redirect_url": redirect_url}


@router.get("/oauth/{provider}/callback")
async def oauth_callback(provider: str, code: str, state: str, db: Session = Depends(get_db)):
    """OAuth 回调处理"""
    try:
        if provider == "wechat":
            userinfo = _wechat_get_userinfo(code)
            openid = userinfo["openid"]
            unionid = userinfo.get("unionid")
            nickname = userinfo["nickname"]
            access_token = userinfo["access_token"]
        elif provider == "alipay":
            userinfo = _alipay_get_userinfo(code)
            openid = userinfo.get("userid", "")
            unionid = None
            nickname = userinfo.get("nickname", "")
            access_token = None
        else:
            raise HTTPException(400, f"不支持的提供商: {provider}")

        # 查找是否已绑定
        existing = db.query(m.ThirdPartyAuth).filter(
            m.ThirdPartyAuth.provider == provider,
            m.ThirdPartyAuth.openid == openid,
        ).first()

        if existing:
            # 已绑定 → 直接登录
            user = db.query(m.User).filter(m.User.id == existing.user_id).first()
            if not user:
                raise HTTPException(404, "用户不存在")
        else:
            # 未绑定 → 查找是否通过 openid 关联
            if provider == "wechat":
                user = db.query(m.User).filter(m.User.wechat_openid == openid).first()
            elif provider == "alipay":
                user = db.query(m.User).filter(m.User.alipay_user_id == openid).first()

            if user:
                # 用户已有 openid 但无 ThirdPartyAuth 记录 → 补建
                existing = m.ThirdPartyAuth(
                    user_id=user.id,
                    provider=provider,
                    openid=openid,
                    union_id=unionid,
                    token=access_token,
                )
                db.add(existing)
            else:
                # 全新用户 → 自动注册
                username = f"{provider}_{nickname[:10]}_{openid[-6:]}"
                counter = 1
                while db.query(m.User).filter(m.User.username == username).first():
                    username = f"{provider}_{nickname[:8]}_{openid[-6:]}_{counter}"
                    counter += 1

                user = m.User(
                    username=username,
                    role="user",
                )
                if provider == "wechat":
                    user.wechat_openid = openid
                elif provider == "alipay":
                    user.alipay_user_id = openid

                db.add(user)
                db.flush()

                existing = m.ThirdPartyAuth(
                    user_id=user.id,
                    provider=provider,
                    openid=openid,
                    union_id=unionid,
                    token=access_token,
                )
                db.add(existing)

        db.commit()

        # 生成 JWT
        token = create_token(user.id, user.username, user.role)
        return {
            "token": token,
            "user": {
                "id": user.id,
                "username": user.username,
                "role": user.role,
                "roles": [user.role],
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"OAuth 回调处理失败: {str(e)}")


# ================= 第三方账号绑定/解绑 =================

@router.post("/bind-thirdparty")
async def bind_thirdparty(req: BindThirdPartyReq, db: Session = Depends(get_db),
                          current_user: dict = Depends(get_current_user)):
    """绑定第三方账号到当前用户"""
    provider = req.provider
    if provider not in ("wechat", "alipay"):
        raise HTTPException(400, f"不支持的提供商: {provider}")

    user = db.query(m.User).filter(m.User.id == current_user["id"]).first()
    if not user:
        raise HTTPException(404, "用户不存在")

    try:
        if provider == "wechat":
            userinfo = _wechat_get_userinfo(req.code)
            openid = userinfo["openid"]
            unionid = userinfo.get("unionid")
            access_token = userinfo["access_token"]
        elif provider == "alipay":
            userinfo = _alipay_get_userinfo(req.code)
            openid = userinfo.get("userid", "")
            unionid = None
            access_token = None
        else:
            raise HTTPException(400, f"不支持的提供商: {provider}")

        # 检查是否已被其他用户绑定
        existing = db.query(m.ThirdPartyAuth).filter(
            m.ThirdPartyAuth.provider == provider,
            m.ThirdPartyAuth.openid == openid,
        ).first()
        if existing:
            if existing.user_id == user.id:
                return {"message": "已绑定"}
            raise HTTPException(400, "该第三方账号已绑定其他用户")

        # 更新用户字段
        if provider == "wechat":
            user.wechat_openid = openid
        elif provider == "alipay":
            user.alipay_user_id = openid

        # 创建绑定记录
        auth_record = m.ThirdPartyAuth(
            user_id=user.id,
            provider=provider,
            openid=openid,
            union_id=unionid,
            token=access_token,
        )
        db.add(auth_record)
        db.commit()

        return {"message": f"已成功绑定{provider}账号"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"绑定失败: {str(e)}")


@router.post("/unbind-thirdparty")
async def unbind_thirdparty(provider: str, db: Session = Depends(get_db),
                            current_user: dict = Depends(get_current_user)):
    """解绑第三方账号"""
    user = db.query(m.User).filter(m.User.id == current_user["id"]).first()
    if not user:
        raise HTTPException(404, "用户不存在")

    auth_record = db.query(m.ThirdPartyAuth).filter(
        m.ThirdPartyAuth.user_id == user.id,
        m.ThirdPartyAuth.provider == provider,
    ).first()

    if not auth_record:
        raise HTTPException(400, "未绑定该第三方账号")

    # 清除用户字段
    if provider == "wechat":
        user.wechat_openid = None
    elif provider == "alipay":
        user.alipay_user_id = None
    else:
        raise HTTPException(400, f"不支持的提供商: {provider}")

    db.delete(auth_record)
    db.commit()

    return {"message": f"已解绑{provider}账号"}


@router.get("/thirdparty-list")
async def get_thirdparty_list(db: Session = Depends(get_db),
                              current_user: dict = Depends(get_current_user)):
    """查询已绑定的第三方账号列表"""
    records = db.query(m.ThirdPartyAuth).filter(
        m.ThirdPartyAuth.user_id == current_user["id"]
    ).all()
    return {
        "bindings": [
            {
                "provider": r.provider,
                "openid": r.openid,
                "union_id": r.union_id,
                "bound_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ]
    }

"""
简历模板市场 — FastAPI 后端（路由拆分版）
"""
import os
import uuid
import asyncio
import logging
import hashlib
import hmac
import urllib.parse
import requests as req_lib
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query, Request, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse
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

# Assets directory — works in both Docker (/app/assets) and local dev (../assets)
_ASSETS_LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
_ASSETS_PARENT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets"))
ASSETS_DIR = _ASSETS_LOCAL if os.path.isdir(_ASSETS_LOCAL) else _ASSETS_PARENT
os.makedirs(ASSETS_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PayJS 配置
# ---------------------------------------------------------------------------
PAYJS_MCHID = os.getenv("PAYJS_MCHID", "")
PAYJS_KEY = os.getenv("PAYJS_KEY", "")


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
# Background tasks
# ---------------------------------------------------------------------------

async def _delivery_check_loop():
    """后台定时任务：每30分钟检查超时订单"""
    while True:
        try:
            db = SessionLocal()
            try:
                from commission import check_delivery_penalties
                results = check_delivery_penalties(db)
                if results:
                    logger.info(f"交付超时检查完成，处理了 {len(results)} 个订单: {results}")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"交付超时检查异常: {e}")
        await asyncio.sleep(1800)  # 30分钟


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时自动创建数据库表
    m.Base.metadata.create_all(bind=engine)
    # 启动后台定时任务
    asyncio.create_task(_delivery_check_loop())
    logger.info("后台定时任务已启动：每30分钟检查超时订单")
    yield


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="Resume Platform API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# 复用 auth 模块
require_admin = auth.require_admin
require_creator = auth.require_creator
get_current_user = auth.get_current_user


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

app.mount("/static", StaticFiles(directory=ASSETS_DIR), name="static")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/api/v1/health")
async def health(db: Session = Depends(get_db)):
    return {"status": "ok", "templates_count": db.query(m.Template).count()}


# ---------------------------------------------------------------------------
# Mount routers
# ---------------------------------------------------------------------------

from routers.auth import router as auth_router
app.include_router(auth_router)

from routers.user import router as user_router
app.include_router(user_router)

from routers.creator import router as creator_router
app.include_router(creator_router)

from routers.admin import router as admin_router
app.include_router(admin_router)

from routers.orders import router as orders_router
app.include_router(orders_router)

from routers.templates import router as templates_router
app.include_router(templates_router)

from routers.ws import router as ws_router
app.include_router(ws_router)

from routers.ws import ws_http as ws_http_router
app.include_router(ws_http_router)

# 公开配置（无需认证 — 前端展示用）
@app.get("/api/v1/config/public")
async def get_public_config(db: Session = Depends(get_db)):
    """返回前端需要展示的公开配置项"""
    from routers.admin.config import load_all_configs
    all_configs = load_all_configs(db)
    return {
        "creator_rate": all_configs.get("creator_rate", 0.30),
        "deposit_amount": all_configs.get("deposit_amount", 20.0),
    }

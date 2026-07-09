"""Pydantic 请求体 / 响应模型"""
from pydantic import BaseModel
from typing import Optional


# ================= 认证 =================

class AuthLoginReq(BaseModel):
    username: str
    password: str


class AuthRegisterReq(BaseModel):
    username: str
    password: str
    ref_code: Optional[str] = None


# ================= 用户 =================

class RegisterReq(BaseModel):
    username: str
    ref_code: Optional[str] = None


class WithdrawReq(BaseModel):
    user_id: int
    amount: float
    payment_info: str


# ================= 订单 =================

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


# ================= 制作者 =================

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
    status: str  # approved / rejected
    remark: Optional[str] = ""


class ReviewWithdrawReq(BaseModel):
    request_id: int
    status: str  # approved / rejected
    remark: Optional[str] = ""


# ================= 管理员 =================

class UpdateUserReq(BaseModel):
    role: Optional[str] = None
    wallet_balance: Optional[float] = None


class UpdateCommissionConfigReq(BaseModel):
    level: int
    rate: float

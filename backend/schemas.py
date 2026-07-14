"""Pydantic request/response schemas"""
from typing import Optional
from pydantic import BaseModel


class LoginReq(BaseModel):
    username: str
    password: str

class RegisterReq(BaseModel):
    username: str
    password: str
    ref_user_id: Optional[int] = None
    invite_code: Optional[str] = None

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
    transfer_proof: str = ""

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

class ResignCreatorReq(BaseModel):
    force: bool = False

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

class BindThirdPartyReq(BaseModel):
    provider: str
    code: str
    state: str = ""

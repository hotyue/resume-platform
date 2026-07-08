"""
PayJS 支付集成模块
文档: https://payjs.cn/docs

使用前需在环境变量中配置:
  PAYJS_MCHID : 商户号
  PAYJS_KEY   : 通信密钥
  PAYJS_NOTIFY_URL : 支付回调地址（生产环境需为公网可访问 URL）
"""

import os
import hashlib
import logging
from urllib.parse import urlencode

import requests

logger = logging.getLogger(__name__)

# PayJS 配置（从环境变量读取）
PAYJS_MCHID = os.getenv("PAYJS_MCHID", "")
PAYJS_KEY = os.getenv("PAYJS_KEY", "")
PAYJS_NOTIFY_URL = os.getenv("PAYJS_NOTIFY_URL", "")

# API 地址
PAYJS_API_NATIVE = "https://payjs.cn/api/native"


def sign(params: dict, key: str) -> str:
    """
    PayJS 签名算法
    1. 按参数名 ASCII 码从小到大排序
    2. key1=value1&key2=value2… 拼接
    3. 末尾追加 &key=密钥
    4. MD5 后转大写
    """
    # 过滤空值参数，排除 sign 字段
    sorted_params = sorted(
        {k: v for k, v in params.items() if v != "" and k != "sign"}.items()
    )
    sign_str = "&".join(f"{k}={v}" for k, v in sorted_params)
    sign_str += f"&key={key}"
    return hashlib.md5(sign_str.encode("utf-8")).hexdigest().upper()


def verify_sign(params: dict, key: str) -> bool:
    """验证回调签名是否合法"""
    received_sign = params.get("sign", "")
    if not received_sign:
        return False
    expected_sign = sign(params, key)
    return expected_sign == received_sign


def create_native_qrcode(
    out_trade_no: str,
    total_fee: int,
    body: str = "简历模板",
    attach: str = "",
    notify_url: str = "",
) -> dict:
    """
    调用 PayJS Native 扫码支付接口
    
    Args:
        out_trade_no: 商户订单号
        total_fee: 金额，单位：分
        body: 订单标题
        attach: 附加数据，回调时原样返回
        notify_url: 回调地址，为空则使用环境变量配置
    
    Returns:
        {
            "success": bool,
            "message": str,
            "data": {
                "payjs_order_id": str,
                "qrcode": str,        # base64 图片 data URI
                "code_url": str,       # 二维码内容 URL
                "out_trade_no": str,
                "total_fee": int
            } | None
        }
    """
    mchid = PAYJS_MCHID
    key = PAYJS_KEY
    callback_url = notify_url or PAYJS_NOTIFY_URL

    if not mchid or not key:
        return {"success": False, "message": "PayJS 未配置（缺少 PAYJS_MCHID 或 PAYJS_KEY）", "data": None}

    params = {
        "mchid": mchid,
        "total_fee": str(total_fee),
        "out_trade_no": out_trade_no,
        "body": body,
        "notify_url": callback_url,
    }
    if attach:
        params["attach"] = attach

    # 计算签名
    params["sign"] = sign(params, key)

    try:
        resp = requests.post(
            PAYJS_API_NATIVE,
            data=params,
            timeout=10,
        )
        result = resp.json()
    except Exception as e:
        logger.error(f"PayJS 请求失败: {e}")
        return {"success": False, "message": f"请求 PayJS 失败: {str(e)}", "data": None}

    if result.get("return_code") == 1:
        return {
            "success": True,
            "message": "success",
            "data": {
                "payjs_order_id": result.get("payjs_order_id"),
                "qrcode": result.get("qrcode"),      # data:image/...;base64,...
                "code_url": result.get("code_url"),  # weixin://...
                "out_trade_no": result.get("out_trade_no"),
                "total_fee": int(result.get("total_fee", 0)),
            },
        }
    else:
        return {
            "success": False,
            "message": result.get("return_msg", "PayJS 返回异常"),
            "data": None,
        }
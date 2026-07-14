"""WebSocket 路由 — heartbeat / chat / messages / unread / mark-read"""
import os
import json as json_mod
import uuid as uuid_mod
import asyncio
import logging
from collections import defaultdict
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, Form, UploadFile, File
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
import models as m
import auth
from auth import get_current_user
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])

# 全局状态
active_chat_connections: dict[int, list] = defaultdict(list)
online_users: dict[int, WebSocket] = {}
HEARTBEAT_INTERVAL = 30
HEARTBEAT_TIMEOUT = 60
ASSETS_DIR = settings.ASSETS_DIR


def is_chat_participant(order: m.Order, user_id: int) -> bool:
    return order.user_id == user_id or order.creator_id == user_id


def _push_notification(user_id: int, payload: dict):
    ws = online_users.get(user_id)
    if ws is not None:
        asyncio.create_task(_send_ws_safe(ws, payload))


async def _send_ws_safe(ws: WebSocket, data: dict):
    try:
        await ws.send_json(data)
    except Exception:
        uid = None
        for uid_w, ws_v in list(online_users.items()):
            if ws_v is ws:
                uid = uid_w
                break
        if uid is not None:
            online_users.pop(uid, None)


def _message_to_dict(msg: m.OrderMessage) -> dict:
    return {
        "id": msg.id, "order_id": msg.order_id, "sender_id": msg.sender_id,
        "content": msg.content, "attachment_url": msg.attachment_url,
        "msg_type": msg.msg_type, "is_read": msg.is_read,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }


# ================= WebSocket 端点 =================

@router.websocket("/user/heartbeat")
async def heartbeat_websocket(websocket: WebSocket, token: str = Query(None)):
    """用户在线心跳 WebSocket"""
    if not token:
        await websocket.close(code=4001, reason="No token")
        return
    try:
        payload = auth.decode_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Authentication failed")
        return
    user_id = int(payload.get("sub")) if payload.get("sub") else None
    if user_id is None:
        await websocket.close(code=4001, reason="Invalid token")
        return

    await websocket.accept()
    online_users[user_id] = websocket
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        online_users.pop(user_id, None)


@router.websocket("/orders/{order_id}/chat")
async def chat_websocket(websocket: WebSocket, order_id: int, token: str = Query(None)):
    """订单聊天 WebSocket"""
    if not token:
        await websocket.close(code=4001, reason="No token")
        return
    try:
        payload = auth.decode_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Authentication failed")
        return
    user_id = int(payload.get("sub")) if payload.get("sub") else None
    if user_id is None:
        await websocket.close(code=4001, reason="Invalid token")
        return
    user = {
        "id": user_id,
        "username": payload.get("username"),
        "role": payload.get("role", "user"),
    }

    db = SessionLocal()
    try:
        order = db.query(m.Order).filter(m.Order.id == order_id).first()
        if not order:
            await websocket.close(code=4004, reason="Order not found")
            return
        if not is_chat_participant(order, user["id"]):
            await websocket.close(code=4003, reason="Not a participant")
            return
    finally:
        db.close()

    await websocket.accept()
    active_chat_connections[order_id].append(websocket)

    # 连接时推送最近 50 条消息
    db = SessionLocal()
    try:
        msgs = (
            db.query(m.OrderMessage)
            .filter(m.OrderMessage.order_id == order_id)
            .order_by(m.OrderMessage.created_at.desc())
            .limit(50)
            .all()
        )
        history = []
        for msg in reversed(msgs):
            history.append({
                "type": "message", "id": msg.id, "order_id": msg.order_id,
                "sender_id": msg.sender_id, "content": msg.content,
                "attachment_url": msg.attachment_url, "msg_type": msg.msg_type,
                "is_read": msg.is_read,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            })
        if history:
            await websocket.send_json({"type": "history", "messages": history})
    finally:
        db.close()

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg_data = json_mod.loads(data)
            except Exception:
                continue

            if msg_data.get("type") == "message":
                content = msg_data.get("content", "").strip()
                if not content:
                    continue
                attachment_url = msg_data.get("attachment_url")
                msg_type = msg_data.get("msg_type", "text")

                db = SessionLocal()
                try:
                    new_msg = m.OrderMessage(
                        order_id=order_id, sender_id=user["id"],
                        content=content, attachment_url=attachment_url, msg_type=msg_type,
                    )
                    db.add(new_msg)
                    db.commit()
                    msg_payload = {
                        "type": "message", "id": new_msg.id, "order_id": new_msg.order_id,
                        "sender_id": new_msg.sender_id, "content": new_msg.content,
                        "attachment_url": new_msg.attachment_url, "msg_type": new_msg.msg_type,
                        "is_read": False,
                        "created_at": new_msg.created_at.isoformat() if new_msg.created_at else None,
                    }
                finally:
                    db.close()

                for conn in list(active_chat_connections[order_id]):
                    try:
                        await conn.send_json(msg_payload)
                    except Exception:
                        pass

                # 推送通知给订单另一方
                db2 = SessionLocal()
                try:
                    order = db2.query(m.Order).filter(m.Order.id == order_id).first()
                    if order:
                        other_id = None
                        if order.user_id == user["id"]:
                            other_id = order.creator_id
                        elif order.creator_id and order.creator_id == user["id"]:
                            other_id = order.user_id
                        if other_id and other_id != user["id"]:
                            other_user = db2.query(m.User).filter(m.User.id == other_id).first()
                            _push_notification(other_id, {
                                "type": "chat_notification", "order_id": order_id,
                                "sender_id": user["id"],
                                "sender_name": user.get("username", ""),
                                "content": content[:50] if len(content) > 50 else content,
                                "created_at": msg_payload["created_at"],
                            })
                finally:
                    db2.close()

    except WebSocketDisconnect:
        active_chat_connections[order_id].remove(websocket)
        if not active_chat_connections[order_id]:
            del active_chat_connections[order_id]


# ================= HTTP 消息端点（放在 ws.py 以便共享状态）====================

# 这些端点挂载在 /api/v1 前缀下，通过 app.include_router(ws_router, prefix="") 导入
ws_http = APIRouter(prefix="/api/v1", tags=["chat"])


@ws_http.get("/orders/{order_id}/messages")
async def get_order_messages(
    order_id: int, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db), current_user: dict = Depends(get_current_user),
):
    order = db.query(m.Order).filter(m.Order.id == order_id).first()
    if not order:
        raise HTTPException(404, "订单不存在")
    if not is_chat_participant(order, current_user["id"]):
        raise HTTPException(403, "无权查看此订单消息")
    msgs = (
        db.query(m.OrderMessage)
        .filter(m.OrderMessage.order_id == order_id)
        .order_by(m.OrderMessage.created_at.asc())
        .offset(offset).limit(limit).all()
    )
    return {"messages": [_message_to_dict(msg) for msg in msgs]}


@ws_http.post("/orders/{order_id}/messages")
async def send_order_message(
    order_id: int, content: str = Form(...), msg_type: str = Form("text"),
    attachment: UploadFile = File(None),
    db: Session = Depends(get_db), current_user: dict = Depends(get_current_user),
):
    order = db.query(m.Order).filter(m.Order.id == order_id).first()
    if not order:
        raise HTTPException(404, "订单不存在")
    if not is_chat_participant(order, current_user["id"]):
        raise HTTPException(403, "无权发送消息")

    attachment_url = None
    if attachment and attachment.filename:
        upload_dir = os.path.join(ASSETS_DIR, "chat_attachments")
        os.makedirs(upload_dir, exist_ok=True)
        ext = os.path.splitext(attachment.filename)[1]
        save_name = f"{uuid_mod.uuid4().hex}{ext}"
        save_path = os.path.join(upload_dir, save_name)
        with open(save_path, "wb") as f:
            f.write(attachment.file.read())
        attachment_url = f"/assets/chat_attachments/{save_name}"
        content_type = attachment.content_type or ""
        if content_type.startswith("image/"):
            msg_type = "image"
        else:
            msg_type = "file"

    if not content.strip() and not attachment_url:
        raise HTTPException(400, "消息内容不能为空")

    new_msg = m.OrderMessage(
        order_id=order_id, sender_id=current_user["id"],
        content=content.strip() or "(文件)", attachment_url=attachment_url, msg_type=msg_type,
    )
    db.add(new_msg)
    db.commit()
    db.refresh(new_msg)

    msg_payload = _message_to_dict(new_msg)
    msg_payload["type"] = "message"

    for conn in list(active_chat_connections.get(order_id, [])):
        try:
            await conn.send_json(msg_payload)
        except Exception:
            pass

    other_id = None
    if order.user_id == current_user["id"]:
        other_id = order.creator_id
    elif order.creator_id and order.creator_id == current_user["id"]:
        other_id = order.user_id
    if other_id and other_id != current_user["id"]:
        _push_notification(other_id, {
            "type": "chat_notification", "order_id": order_id,
            "sender_id": current_user["id"],
            "sender_name": current_user.get("username", ""),
            "content": (content[:50] if len(content) > 50 else content) or "(文件)",
            "created_at": new_msg.created_at.isoformat() if new_msg.created_at else None,
        })

    return msg_payload


@ws_http.get("/chat/unread-count")
async def get_unread_count(
    db: Session = Depends(get_db), current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]
    user_orders = db.query(m.Order.id).filter(
        (m.Order.user_id == user_id) | (m.Order.creator_id == user_id)
    ).subquery()
    count = (
        db.query(func.count(m.OrderMessage.id))
        .filter(
            m.OrderMessage.order_id.in_(user_orders),
            m.OrderMessage.sender_id != user_id,
            m.OrderMessage.is_read == False,
        )
        .scalar() or 0
    )
    unread_orders = (
        db.query(m.OrderMessage.order_id, func.count(m.OrderMessage.id).label("unread"))
        .filter(
            m.OrderMessage.order_id.in_(user_orders),
            m.OrderMessage.sender_id != user_id,
            m.OrderMessage.is_read == False,
        )
        .group_by(m.OrderMessage.order_id)
        .all()
    )
    unread_list = [{"order_id": row.order_id, "unread": row.unread} for row in unread_orders]
    return {"unread_count": count, "unread_orders": unread_list}


@ws_http.patch("/orders/{order_id}/messages/read")
async def mark_messages_read(
    order_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user),
):
    order = db.query(m.Order).filter(m.Order.id == order_id).first()
    if not order:
        raise HTTPException(404, "订单不存在")
    if not is_chat_participant(order, current_user["id"]):
        raise HTTPException(403, "无权操作")
    db.query(m.OrderMessage).filter(
        m.OrderMessage.order_id == order_id,
        m.OrderMessage.sender_id != current_user["id"],
        m.OrderMessage.is_read == False,
    ).update({"is_read": True})
    db.commit()
    return {"message": "已标记为已读"}

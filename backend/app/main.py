from __future__ import annotations
import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import models, schemas
from .database import Base, engine, get_db
from .connection_manager import manager, AGENTS_ROOM
from .schemas import _as_utc_isoformat

Base.metadata.create_all(bind=engine)

app = FastAPI(title="LiveDesk API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your frontend origin in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- REST: conversation history & bootstrap ----------

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/conversations", response_model=list[schemas.ConversationOut])
def list_conversations(db: Session = Depends(get_db)):
    convos = db.query(models.Conversation).order_by(models.Conversation.created_at.desc()).all()
    return convos


@app.post("/api/conversations", response_model=schemas.ConversationOut)
def create_conversation(payload: schemas.ConversationCreate, db: Session = Depends(get_db)):
    convo = models.Conversation(client_name=payload.client_name)
    db.add(convo)
    db.commit()
    db.refresh(convo)
    return convo


@app.get("/api/conversations/{conversation_id}/messages", response_model=list[schemas.MessageOut])
def get_messages(conversation_id: str, db: Session = Depends(get_db)):
    convo = db.query(models.Conversation).filter_by(id=conversation_id).first()
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return convo.messages


# ---------- WebSocket: the live layer ----------
#
# Two kinds of sockets:
#  1. /ws/agents            -> agents' global feed (new conversations, presence)
#  2. /ws/conversations/:id -> the actual chat room (messages, typing)
#
# Ephemeral events (typing, presence) are broadcast only.
# Message events are persisted first, then broadcast — so history
# is never inconsistent with what was shown live.

@app.websocket("/ws/agents")
async def agents_feed(websocket: WebSocket, name: str = "Agent"):
    await manager.connect(websocket, AGENTS_ROOM, role="agent", name=name)
    try:
        while True:
            await websocket.receive_text()  # agents feed is read-only from client side
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.websocket("/ws/conversations/{conversation_id}")
async def conversation_room(websocket: WebSocket, conversation_id: str, role: str = "client", name: str = "Visitor"):
    db = next(get_db())
    convo = db.query(models.Conversation).filter_by(id=conversation_id).first()
    if not convo:
        await websocket.close(code=4404)
        return

    await manager.connect(websocket, conversation_id, role=role, name=name)

    # Tell the agents feed a new conversation/client showed up (for the sidebar).
    if role == "client":
        await manager.broadcast(AGENTS_ROOM, {
            "type": "new_activity",
            "conversation_id": conversation_id,
            "client_name": name,
        })

    try:
        while True:
            raw = await websocket.receive_text()

            # Client input is untrusted: malformed JSON or a missing/non-string
            # "body" used to raise an uncaught JSONDecodeError/KeyError here,
            # which killed the whole connection instead of just that one bad
            # frame. Validate first and skip the frame instead of crashing.
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"type": "error", "detail": "invalid JSON"}))
                continue

            if not isinstance(event, dict):
                await websocket.send_text(json.dumps({"type": "error", "detail": "expected a JSON object"}))
                continue

            event_type = event.get("type")

            if event_type == "message":
                body = event.get("body")
                if not isinstance(body, str) or not body.strip():
                    await websocket.send_text(json.dumps({"type": "error", "detail": "message body is required"}))
                    continue

                msg = models.Message(
                    conversation_id=conversation_id,
                    sender_role=role,
                    sender_name=name,
                    body=body[:4000],
                )
                db.add(msg)
                db.commit()
                db.refresh(msg)

                payload = {
                    "type": "message",
                    "id": msg.id,
                    "conversation_id": conversation_id,
                    "sender_role": role,
                    "sender_name": name,
                    "body": msg.body,
                    "created_at": _as_utc_isoformat(msg.created_at),
                }
                await manager.broadcast(conversation_id, payload)
                await manager.broadcast(AGENTS_ROOM, {
                    "type": "new_message",
                    "conversation_id": conversation_id,
                    "preview": msg.body[:80],
                    "sender_role": role,
                })

            elif event_type == "typing":
                # Never persisted — pure live signal.
                await manager.broadcast(conversation_id, {
                    "type": "typing",
                    "conversation_id": conversation_id,
                    "sender_role": role,
                    "sender_name": name,
                    "is_typing": bool(event.get("is_typing")),
                }, exclude=websocket)

    except WebSocketDisconnect:
        info = manager.disconnect(websocket)
        if info and info["role"] == "client":
            await manager.broadcast(AGENTS_ROOM, {
                "type": "presence",
                "conversation_id": conversation_id,
                "status": "offline",
                "name": name,
            })
    finally:
        db.close()

from __future__ import annotations
import json
import logging
import secrets

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import models, schemas
from .config import settings
from .database import Base, SessionLocal, engine, get_db
from .connection_manager import manager, AGENTS_ROOM
from .schemas import _as_utc_isoformat

logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("livedesk")

Base.metadata.create_all(bind=engine)

app = FastAPI(title="LiveDesk API")

# Shared secret for role=agent. Not real auth (no per-agent identity), but it
# keeps strangers out of the agent socket and the agent-only endpoints.
AGENT_TOKEN = settings.agent_token
if settings.uses_default_token:
    logger.warning("using the default AGENT_TOKEN — set your own for anything beyond local dev")
logger.info("starting in %s mode, CORS origins: %s", settings.app_env, settings.cors_origins)


def tokens_match(given: str, expected: str) -> bool:
    return secrets.compare_digest(given.encode(), expected.encode())


VALID_ROLES = ("client", "agent")


def require_agent_token(x_agent_token: str = Header(default="")) -> None:
    if not tokens_match(x_agent_token, AGENT_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid or missing agent token")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- REST: conversation history & bootstrap ----------

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/agents/online-count")
def online_agent_count():
    # Public and unauthenticated on purpose — it's just a headcount, no
    # conversation data, and the client widget needs it before a visitor
    # has any conversation (or agent token) at all. Used to be a fixed
    # "3 agents online now" in the widget regardless of whether anyone
    # was actually connected.
    return {"count": manager.online_agent_count()}


@app.get(
    "/api/conversations",
    response_model=list[schemas.ConversationOut],
    dependencies=[Depends(require_agent_token)],
)
def list_conversations(db: Session = Depends(get_db)):
    convos = db.query(models.Conversation).order_by(models.Conversation.created_at.desc()).all()
    return convos


@app.post("/api/conversations", response_model=schemas.ConversationCreated)
def create_conversation(payload: schemas.ConversationCreate, db: Session = Depends(get_db)):
    convo = models.Conversation(client_name=payload.client_name)
    db.add(convo)
    db.commit()
    db.refresh(convo)
    return convo


@app.get("/api/conversations/{conversation_id}/messages", response_model=list[schemas.MessageOut])
def get_messages(
    conversation_id: str,
    x_agent_token: str = Header(default=""),
    x_client_token: str = Header(default=""),
    db: Session = Depends(get_db),
):
    convo = db.query(models.Conversation).filter_by(id=conversation_id).first()
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    is_agent = tokens_match(x_agent_token, AGENT_TOKEN)
    is_owner = tokens_match(x_client_token, convo.client_token)
    if not (is_agent or is_owner):
        raise HTTPException(status_code=401, detail="Invalid or missing token")
    return convo.messages


@app.patch("/api/conversations/{conversation_id}", response_model=schemas.ConversationOut, dependencies=[Depends(require_agent_token)])
async def update_conversation(
    conversation_id: str, payload: schemas.ConversationUpdate, db: Session = Depends(get_db)
):
    convo = db.query(models.Conversation).filter_by(id=conversation_id).first()
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    updates = payload.model_dump(exclude_unset=True)

    if "status" in updates and updates["status"] is not None:
        try:
            convo.status = models.ConversationStatus(updates["status"])
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid status")

    if "priority" in updates and updates["priority"] is not None:
        try:
            convo.priority = models.ConversationPriority(updates["priority"])
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid priority")

    if "assigned_to" in updates:
        convo.assigned_to = updates["assigned_to"]

    db.commit()
    db.refresh(convo)

    # So a second agent looking at the same ticket sees the change live,
    # instead of only finding out on their next full page load.
    await manager.broadcast(AGENTS_ROOM, {
        "type": "ticket_updated",
        "conversation_id": convo.id,
        "status": convo.status.value,
        "priority": convo.priority.value,
        "assigned_to": convo.assigned_to,
    })

    return convo


async def reject(websocket: WebSocket, code: int) -> None:
    # Closing before accept() makes the server answer the upgrade with a plain
    # HTTP 403, and browsers never see the close code. Accept first so the
    # client actually receives 4400/4401/4404.
    logger.info("rejected websocket %s with %s", websocket.url.path, code)
    await websocket.accept()
    await websocket.close(code=code)


def find_client_token(conversation_id: str) -> str | None:
    with SessionLocal() as db:
        convo = db.query(models.Conversation).filter_by(id=conversation_id).first()
        return convo.client_token if convo else None


def save_message(conversation_id: str, role: str, name: str, body: str) -> dict:
    with SessionLocal() as db:
        msg = models.Message(
            conversation_id=conversation_id,
            sender_role=role,
            sender_name=name,
            body=body[:4000],
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)
        return {
            "type": "message",
            "id": msg.id,
            "conversation_id": conversation_id,
            "sender_role": role,
            "sender_name": name,
            "body": msg.body,
            "created_at": _as_utc_isoformat(msg.created_at),
        }


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
async def agents_feed(websocket: WebSocket, name: str = "Agent", token: str = ""):
    if not tokens_match(token, AGENT_TOKEN):
        await reject(websocket, 4401)
        return

    await manager.connect(websocket, AGENTS_ROOM, role="agent", name=name)
    try:
        while True:
            await websocket.receive_text()  # agents feed is read-only from client side
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.websocket("/ws/conversations/{conversation_id}")
async def conversation_room(
    websocket: WebSocket,
    conversation_id: str,
    role: str = "client",
    name: str = "Visitor",
    token: str = "",
):
    if role not in VALID_ROLES:
        await reject(websocket, 4400)
        return

    if role == "agent" and not tokens_match(token, AGENT_TOKEN):
        await reject(websocket, 4401)
        return

    client_token = find_client_token(conversation_id)
    if client_token is None:
        await reject(websocket, 4404)
        return

    if role == "client" and not tokens_match(token, client_token):
        await reject(websocket, 4401)
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

                payload = save_message(conversation_id, role, name, body)
                await manager.broadcast(conversation_id, payload)
                await manager.broadcast(AGENTS_ROOM, {
                    "type": "new_message",
                    "conversation_id": conversation_id,
                    "preview": payload["body"][:80],
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

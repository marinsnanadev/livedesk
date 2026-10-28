"""
Tracks every live WebSocket connection and broadcasts events to the
right audience. This is the piece that turns "send a message, save it,
done" into an actual real-time system:

- Connections are grouped by conversation ("room"), so a client only
  hears about their own conversation.
- Agents additionally join a global "agents" room, so they see
  presence/new-conversation events across all conversations at once.
- Typing events are NOT persisted — they're pure live state, gone the
  moment nobody is listening. That split (durable messages in Postgres/
  SQLite vs. ephemeral presence in memory) is the core architectural
  idea of the whole project.
"""
from __future__ import annotations
import json
from typing import Dict, Set
from fastapi import WebSocket


AGENTS_ROOM = "__agents__"


class ConnectionManager:
    def __init__(self) -> None:
        # room_id -> set of live sockets in that room
        self.rooms: Dict[str, Set[WebSocket]] = {}
        # socket -> metadata (role, name, conversation_id) for cleanup on disconnect
        self.meta: Dict[WebSocket, dict] = {}

    async def connect(self, websocket: WebSocket, room_id: str, role: str, name: str) -> None:
        await websocket.accept()
        self.rooms.setdefault(room_id, set()).add(websocket)
        self.meta[websocket] = {"room_id": room_id, "role": role, "name": name, "typing": False}

        if role == "agent":
            self.rooms.setdefault(AGENTS_ROOM, set()).add(websocket)

        if role == "client":
            # Let every connected agent know a client is present/back online.
            await self.broadcast(AGENTS_ROOM, {
                "type": "presence",
                "conversation_id": room_id,
                "status": "online",
                "name": name,
            })

    async def disconnect(self, websocket: WebSocket) -> None:
        # Whoever notices a socket is gone first (its own handler, or a
        # broadcast that failed to reach it) lands here, so the "left"
        # announcements live here too. Otherwise a socket dropped by a failed
        # broadcast would never tell the agents the client went offline.
        info = self.meta.pop(websocket, None)
        if not info:
            return

        room = self.rooms.get(info["room_id"])
        if room:
            room.discard(websocket)
            if not room:
                self.rooms.pop(info["room_id"], None)

        agents_room = self.rooms.get(AGENTS_ROOM)
        if agents_room:
            agents_room.discard(websocket)

        if info["typing"]:
            await self.broadcast(info["room_id"], {
                "type": "typing",
                "conversation_id": info["room_id"],
                "sender_role": info["role"],
                "sender_name": info["name"],
                "is_typing": False,
            })

        # A visitor can have several tabs open: only the last one leaving
        # makes them offline.
        if info["role"] == "client" and not self.client_online(info["room_id"]):
            await self.broadcast(AGENTS_ROOM, {
                "type": "presence",
                "conversation_id": info["room_id"],
                "status": "offline",
                "name": info["name"],
            })

    def set_typing(self, websocket: WebSocket, is_typing: bool) -> None:
        if websocket in self.meta:
            self.meta[websocket]["typing"] = is_typing

    def client_online(self, room_id: str) -> bool:
        return any(self.meta[ws]["role"] == "client" for ws in self.rooms.get(room_id, ()))

    def online_conversations(self) -> list[str]:
        return [room_id for room_id in self.rooms if room_id != AGENTS_ROOM and self.client_online(room_id)]

    async def broadcast(self, room_id: str, payload: dict, exclude: WebSocket | None = None) -> None:
        sockets = list(self.rooms.get(room_id, set()))
        dead = []
        for ws in sockets:
            if ws is exclude:
                continue
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)

    def online_agent_count(self) -> int:
        # Count distinct agent *names*, not sockets: one agent has two
        # sockets open at once whenever they have a ticket selected — the
        # global /ws/agents feed (always open) plus a role=agent socket on
        # that specific conversation (opened by the chat panel). Counting
        # sockets reported "2 agents online" for one agent working a ticket.
        names = {self.meta[ws]["name"] for ws in self.rooms.get(AGENTS_ROOM, set())}
        return len(names)


manager = ConnectionManager()

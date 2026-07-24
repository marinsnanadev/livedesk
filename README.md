# LiveDesk

Live support chat with real-time presence, a "typing…" indicator, and persisted history — a mini Intercom/Zendesk built to show how to actually solve real-time state, not just "send a message and have it show up on screen."

**[Add the deploy link here once published]**

## Why this project

A chat with API fetches is a commodity. What sets this project apart is the clear separation between two layers of state:

- **Durable state** (messages, conversations) — lives in the database (SQLite by default, swap to Postgres just by changing `DATABASE_URL`, no code changes needed).
- **Live state** (who's online, who's typing) — lives only in memory in the backend's `ConnectionManager`, is never persisted, and disappears the moment nobody is listening.

This separation is the architectural core of the project — and it's exactly the question that tends to come up in technical interviews: *"how do you handle N clients connected at the same time, and what happens when one of them drops?"*

## Architecture

```
Client (widget)   ──┐
                     ├──WebSocket──► FastAPI (ConnectionManager) ──► SQLite/Postgres
Agent (dashboard) ──┘
```

- Each conversation is a "room" — sockets only receive events from their own room.
- Agents also join a global room (`agents`), so they can see new conversations and presence in real time in the sidebar, even without an open conversation.
- Messages are persisted **before** being broadcast — history is never inconsistent with what was shown live.
- "Typing" events never touch the database.
- The frontend automatically reconnects with exponential backoff if the socket drops.

## Running locally

### Backend

```
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload OR python -m uvicorn app.main:app --reload
```

The API comes up at `http://localhost:8000`. Tests: `pytest -v`.

### Frontend

```
cd frontend
npm install
cp .env.example .env
npm run dev
```

- **Agent dashboard:** `http://localhost:5173/`
- **Client widget (visitor view):** `http://localhost:5173/widget`

Open both routes in separate tabs to simulate a real conversation between client and agent.

## Stack

- **Backend:** FastAPI, native WebSockets, SQLAlchemy, SQLite (easy swap to Postgres in production)
- **Frontend:** React, Vite, React Router — no UI framework, custom CSS with a token system
- **Tests:** pytest + FastAPI's `TestClient`, covering the full connection and message-exchange flow
- **CI:** GitHub Actions running the backend tests and the frontend build on every push

## Possible next steps

- Real authentication for agents (the name is currently hardcoded, just a demo)
- Close/reopen conversations from the UI
- Push notification when the agent is offline

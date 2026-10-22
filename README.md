# LiveDesk

Live support chat with real-time presence, a "typing…" indicator, and persisted history — a mini Intercom/Zendesk built to show how to actually solve real-time state, not just "send a message and have it show up on screen."

**[Live demo link goes here once deployed — see [Deploying](#deploying) below]**

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
- Ticket status, priority, and assignment are persisted too — updating one broadcasts a `ticket_updated` event to every connected agent, so two dashboards never disagree about who owns a ticket.
- The frontend automatically reconnects with exponential backoff if the socket drops.
- `role=agent` is gated by a shared `AGENT_TOKEN`, checked on the websocket handshake and on every agent REST endpoint (listing and updating tickets) — without it, anyone who knows the URL shape could open a socket as an "agent" and read every conversation. Visitors get a per-conversation `client_token` when their chat is created, and that is what lets them read, join, and post in that conversation.

## Running locally

### Backend

```
cd backend
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload OR python -m uvicorn app.main:app --reload
```

The API comes up at `http://localhost:8000`. Tests: `pytest -v`.

The schema lives in Alembic migrations (`backend/alembic/versions`), so run
`alembic upgrade head` once before the first start and again after pulling a
change that adds a migration. After changing a model, generate the migration
with `alembic revision --autogenerate -m "what changed"` and read it before
committing — a test fails if the models and the migrations drift apart.

Everything the backend reads from the environment is listed in
`backend/.env.example`:

| Variable | What it does |
| --- | --- |
| `AGENT_TOKEN` | Shared secret for `role=agent` (websocket and agent-only endpoints). Unset or blank falls back to a well-known dev default and logs a warning. |
| `APP_ENV` | Set to `production` and the app refuses to start on the default token. |
| `DATABASE_URL` | SQLite by default. Both `postgres://` and `postgresql://` URLs work (the psycopg 3 driver is used). |
| `CORS_ORIGINS` | Comma-separated frontend origins allowed to call the API (defaults to the local Vite dev server). |

### Frontend

```
cd frontend
npm install
cp .env.example .env
npm run dev
```

- **Agent dashboard:** `http://localhost:5173/` — asks for the `AGENT_TOKEN` from the backend's `.env` on first load.
- **Client widget (visitor view):** `http://localhost:5173/widget`

Open both routes in separate tabs to simulate a real conversation between client and agent.

## Stack

- **Backend:** FastAPI, native WebSockets, SQLAlchemy, SQLite (easy swap to Postgres in production)
- **Frontend:** React, Vite, React Router — no UI framework, custom CSS with a token system
- **Tests:** pytest + FastAPI's `TestClient`, covering the full connection and message-exchange flow
- **CI:** GitHub Actions running the backend tests and the frontend build on every push

## Possible next steps

- Per-agent identity (today it's one shared token for every agent, not individual accounts/logins)
- Rate limiting on message sends, to prevent a single connection from flooding a room
- Close/reopen conversations from the UI
- Push notification when the agent is offline

## Deploying

The backend is a standard FastAPI app and WebSockets work fine on Render. The
frontend is a static Vite build (Vercel or Netlify).

1. **Backend (Render):** create a new Blueprint from this repo. `render.yaml`
   provisions the Postgres database and the web service, and its start command
   runs `alembic upgrade head` before the server. Render generates
   `AGENT_TOKEN` for you (read it from the service's Environment tab — it's the
   token you log into the dashboard with). Check Render's current free-tier
   limits for the database before relying on it long term.
2. **Frontend:** deploy the `frontend/` folder to Vercel or Netlify and set
   `VITE_API_BASE` to the backend's URL. `vercel.json` and `public/_redirects`
   make `/widget` and other routes survive a page refresh.
3. **CORS:** back on Render, set `CORS_ORIGINS` to the frontend's URL, since
   the API only accepts the origins listed there.
4. Drop the live link at the top of this README once it's up.

Any other host works too: set the four variables from the table above and run
`alembic upgrade head` before starting `uvicorn`.

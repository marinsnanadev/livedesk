"""
Covers the core flow: create a conversation, connect client + agent
over WebSocket, exchange a message, and confirm it was persisted.
Run with: pytest
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from app.main import app, AGENT_TOKEN

client = TestClient(app)
AGENT_HEADERS = {"X-Agent-Token": AGENT_TOKEN}


def _create_conversation(name="Test Visitor"):
    resp = client.post("/api/conversations", json={"client_name": name})
    assert resp.status_code == 200
    return resp.json()["id"]


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_online_agent_count_reflects_real_connections():
    # Regression test: the client widget used to show a hardcoded
    # "3 agents online now" regardless of whether anyone was actually
    # connected. This confirms the count is real and unauthenticated
    # (the widget has no agent token to send).
    resp = client.get("/api/agents/online-count")
    assert resp.status_code == 200
    baseline = resp.json()["count"]

    with client.websocket_connect(f"/ws/agents?name=Counted&token={AGENT_TOKEN}"):
        resp = client.get("/api/agents/online-count")
        assert resp.json()["count"] == baseline + 1

    # Back down once the connection closes.
    resp = client.get("/api/agents/online-count")
    assert resp.json()["count"] == baseline


def test_online_agent_count_does_not_double_count_the_same_agent():
    # Regression test: an agent with a ticket open has TWO sockets in the
    # agents room at once — the global /ws/agents feed, plus a role=agent
    # socket on that specific conversation (opened by the chat panel).
    # Both used to count as separate "online agents" (1 real agent -> 2),
    # since online_agent_count() counted sockets instead of distinct names.
    convo_id = _create_conversation("Double Count Target")
    baseline = client.get("/api/agents/online-count").json()["count"]

    with client.websocket_connect(f"/ws/agents?name=Amy&token={AGENT_TOKEN}"):
        with client.websocket_connect(
            f"/ws/conversations/{convo_id}?role=agent&name=Amy&token={AGENT_TOKEN}"
        ):
            resp = client.get("/api/agents/online-count")
            assert resp.json()["count"] == baseline + 1  # one agent, not two


def test_create_and_list_conversation():
    convo_id = _create_conversation()
    resp = client.get("/api/conversations")
    assert resp.status_code == 200
    assert any(c["id"] == convo_id for c in resp.json())


def test_message_round_trip_over_websocket():
    convo_id = _create_conversation("Maria")

    with client.websocket_connect(f"/ws/conversations/{convo_id}?role=client&name=Maria") as client_ws, \
         client.websocket_connect(f"/ws/conversations/{convo_id}?role=agent&name=Amy&token={AGENT_TOKEN}") as agent_ws:

        client_ws.send_json({"type": "message", "body": "Hi, I need help"})

        # Both sockets in the room receive the broadcast, including the sender.
        client_event = client_ws.receive_json()
        agent_event = agent_ws.receive_json()

        assert client_event["type"] == "message"
        assert client_event["body"] == "Hi, I need help"
        assert agent_event["body"] == "Hi, I need help"

    # Persisted, so it survives after the sockets close.
    history = client.get(f"/api/conversations/{convo_id}/messages").json()
    assert len(history) == 1
    assert history[0]["sender_name"] == "Maria"


def test_typing_event_is_not_persisted():
    convo_id = _create_conversation("Joao")

    with client.websocket_connect(f"/ws/conversations/{convo_id}?role=client&name=Joao") as client_ws, \
         client.websocket_connect(f"/ws/conversations/{convo_id}?role=agent&name=Amy&token={AGENT_TOKEN}") as agent_ws:

        client_ws.send_json({"type": "typing", "is_typing": True})
        event = agent_ws.receive_json()
        assert event["type"] == "typing"
        assert event["is_typing"] is True

    history = client.get(f"/api/conversations/{convo_id}/messages").json()
    assert history == []


def test_new_conversation_has_ticket_defaults():
    convo_id = _create_conversation("Default Ticket")
    convo = next(c for c in client.get("/api/conversations").json() if c["id"] == convo_id)
    assert convo["status"] == "open"
    assert convo["priority"] == "medium"
    assert convo["assigned_to"] is None


def test_update_ticket_persists_across_requests():
    convo_id = _create_conversation("Persisted Ticket")

    resp = client.patch(
        f"/api/conversations/{convo_id}",
        json={"status": "in_progress", "priority": "urgent", "assigned_to": "Amy"},
        headers=AGENT_HEADERS,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "in_progress"
    assert body["priority"] == "urgent"
    assert body["assigned_to"] == "Amy"

    # Bug this guards against: if the endpoint updated its own in-memory
    # object but never called db.commit(), this second, independent
    # request would still read back the old defaults.
    convo = next(c for c in client.get("/api/conversations").json() if c["id"] == convo_id)
    assert convo["status"] == "in_progress"
    assert convo["priority"] == "urgent"
    assert convo["assigned_to"] == "Amy"


def test_update_ticket_rejects_invalid_status():
    convo_id = _create_conversation("Bad Status")
    resp = client.patch(f"/api/conversations/{convo_id}", json={"status": "not_a_real_status"}, headers=AGENT_HEADERS)
    assert resp.status_code == 422

    # Confirms the rejected update didn't slip through before validation failed.
    convo = next(c for c in client.get("/api/conversations").json() if c["id"] == convo_id)
    assert convo["status"] == "open"


def test_update_ticket_broadcasts_to_agents_feed():
    convo_id = _create_conversation("Broadcast Ticket")

    with client.websocket_connect(f"/ws/agents?name=Watcher&token={AGENT_TOKEN}") as agents_ws:
        client.patch(f"/api/conversations/{convo_id}", json={"priority": "high"}, headers=AGENT_HEADERS)
        event = agents_ws.receive_json()

        assert event["type"] == "ticket_updated"
        assert event["conversation_id"] == convo_id
        assert event["priority"] == "high"


def test_update_conversation_404_for_unknown_id():
    resp = client.patch("/api/conversations/does-not-exist", json={"priority": "high"}, headers=AGENT_HEADERS)
    assert resp.status_code == 404


def test_update_conversation_rejects_missing_agent_token():
    convo_id = _create_conversation("Unauthorized Patch")
    resp = client.patch(f"/api/conversations/{convo_id}", json={"priority": "urgent"})
    assert resp.status_code == 401

    # Confirms the rejected request never touched the row.
    convo = next(c for c in client.get("/api/conversations").json() if c["id"] == convo_id)
    assert convo["priority"] == "medium"


def test_agents_feed_rejects_missing_or_wrong_token():
    from starlette.websockets import WebSocketDisconnect

    try:
        with client.websocket_connect("/ws/agents?name=Intruder"):
            assert False, "should have been rejected without a token"
    except WebSocketDisconnect as exc:
        assert exc.code == 4401

    try:
        with client.websocket_connect("/ws/agents?name=Intruder&token=totally-wrong"):
            assert False, "should have been rejected with a wrong token"
    except WebSocketDisconnect as exc:
        assert exc.code == 4401


def test_conversation_room_rejects_agent_role_without_token():
    from starlette.websockets import WebSocketDisconnect

    convo_id = _create_conversation("Guarded Room")
    try:
        with client.websocket_connect(f"/ws/conversations/{convo_id}?role=agent&name=Intruder"):
            assert False, "should have been rejected without a token"
    except WebSocketDisconnect as exc:
        assert exc.code == 4401


def test_conversation_room_still_allows_client_role_without_token():
    convo_id = _create_conversation("Open To Clients")
    with client.websocket_connect(f"/ws/conversations/{convo_id}?role=client&name=Visitor"):
        pass  # connecting without raising is the assertion — clients never needed a token


def test_suite_never_writes_to_the_real_dev_database():
    # Regression test: this suite used to hit whatever DATABASE_URL
    # defaults to (backend/livedesk.db) — the same file the dashboard
    # reads from — so running `pytest` a few times quietly filled the
    # real ticket queue with test conversations. conftest.py points tests
    # at their own file; this just confirms that redirect is in effect.
    from app.database import DATABASE_URL
    assert "test_livedesk" in DATABASE_URL
    assert DATABASE_URL != "sqlite:///./livedesk.db"


def test_timestamps_are_serialized_as_explicit_utc():
    # Regression test: SQLite silently drops tzinfo on write, so a naive
    # datetime.isoformat() (e.g. "2026-09-04T21:09:38") gets misread by
    # `new Date(...)` in the browser as *local* time instead of UTC,
    # throwing off every "Xmin ago" label by the viewer's UTC offset.
    # A correctly UTC-tagged value always ends in "+00:00" or "Z".
    convo_id = _create_conversation("Timezone Tester")

    convo = next(c for c in client.get("/api/conversations").json() if c["id"] == convo_id)
    assert convo["created_at"].endswith("+00:00") or convo["created_at"].endswith("Z")

    with client.websocket_connect(f"/ws/conversations/{convo_id}?role=client&name=Timezone Tester") as ws:
        ws.send_json({"type": "message", "body": "checking timestamps"})
        event = ws.receive_json()
        assert event["created_at"].endswith("+00:00") or event["created_at"].endswith("Z")

    history = client.get(f"/api/conversations/{convo_id}/messages").json()
    assert history[0]["created_at"].endswith("+00:00") or history[0]["created_at"].endswith("Z")


def test_invalid_json_does_not_crash_the_connection():
    # Regression test: `json.loads` used to raise JSONDecodeError straight
    # out of the receive loop, killing the whole connection on one bad frame
    # instead of just rejecting it.
    convo_id = _create_conversation("Bad JSON Sender")

    with client.websocket_connect(f"/ws/conversations/{convo_id}?role=client&name=Tester") as ws:
        ws.send_text("not valid json{{{")
        error = ws.receive_json()
        assert error["type"] == "error"

        # Connection is still alive and usable after the bad frame.
        ws.send_json({"type": "message", "body": "still works"})
        event = ws.receive_json()
        assert event["type"] == "message"
        assert event["body"] == "still works"


def test_message_without_body_is_rejected_not_crashed():
    # Regression test: `event["body"]` used to raise a KeyError straight out
    # of the receive loop when a client sent {"type": "message"} with no
    # "body" field.
    convo_id = _create_conversation("Missing Body Sender")

    with client.websocket_connect(f"/ws/conversations/{convo_id}?role=client&name=Tester") as ws:
        ws.send_json({"type": "message"})
        error = ws.receive_json()
        assert error["type"] == "error"

    history = client.get(f"/api/conversations/{convo_id}/messages").json()
    assert history == []

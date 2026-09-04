"""
Covers the core flow: create a conversation, connect client + agent
over WebSocket, exchange a message, and confirm it was persisted.
Run with: pytest
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _create_conversation(name="Test Visitor"):
    resp = client.post("/api/conversations", json={"client_name": name})
    assert resp.status_code == 200
    return resp.json()["id"]


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_create_and_list_conversation():
    convo_id = _create_conversation()
    resp = client.get("/api/conversations")
    assert resp.status_code == 200
    assert any(c["id"] == convo_id for c in resp.json())


def test_message_round_trip_over_websocket():
    convo_id = _create_conversation("Maria")

    with client.websocket_connect(f"/ws/conversations/{convo_id}?role=client&name=Maria") as client_ws, \
         client.websocket_connect(f"/ws/conversations/{convo_id}?role=agent&name=Nana") as agent_ws:

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


def test_typing_event_is_not_persisted():
    convo_id = _create_conversation("Joao")

    with client.websocket_connect(f"/ws/conversations/{convo_id}?role=client&name=Joao") as client_ws, \
         client.websocket_connect(f"/ws/conversations/{convo_id}?role=agent&name=Nana") as agent_ws:

        client_ws.send_json({"type": "typing", "is_typing": True})
        event = agent_ws.receive_json()
        assert event["type"] == "typing"
        assert event["is_typing"] is True

    history = client.get(f"/api/conversations/{convo_id}/messages").json()
    assert history == []

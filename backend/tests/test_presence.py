import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from app.connection_manager import AGENTS_ROOM, ConnectionManager
from app.main import app, AGENT_TOKEN


@pytest.fixture
def client():
    # Entering the TestClient runs every connection on one event loop, like
    # uvicorn does. Without it each websocket gets its own loop and thread,
    # and tests that wait on events crossing between sockets hang at random.
    with TestClient(app) as test_client:
        yield test_client


def _new_conversation(client, name="Visitor"):
    return client.post("/api/conversations", json={"client_name": name}).json()


def _client_url(convo, name="Visitor"):
    return f"/ws/conversations/{convo['id']}?role=client&name={name}&token={convo['client_token']}"


def _agent_url(convo):
    return f"/ws/conversations/{convo['id']}?role=agent&name=Amy&token={AGENT_TOKEN}"


def _feed(client):
    return client.websocket_connect(f"/ws/agents?name=Watcher&token={AGENT_TOKEN}")


def _ready(ws):
    # The handshake can complete before the server has put the socket in its
    # room, so anything broadcast right after connecting may miss it. The
    # error reply proves the server's handler loop is already running.
    ws.send_text("ping")
    assert ws.receive_json()["type"] == "error"


def _events_until(ws, event_type):
    # An agent socket on a conversation also sits in the agents room, so
    # presence events arrive between the ones a test is waiting for.
    events = [ws.receive_json()]
    while events[-1]["type"] != event_type:
        events.append(ws.receive_json())
    return events


def test_agents_feed_starts_with_a_snapshot_of_who_is_online(client):
    # Regression test: presence events only describe changes, so a dashboard
    # that logged in after a visitor connected saw them as offline until they
    # reconnected.
    here = _new_conversation(client, "Here")
    gone = _new_conversation(client, "Gone")
    with client.websocket_connect(_client_url(gone)) as gone_ws:
        _ready(gone_ws)

    with client.websocket_connect(_client_url(here)) as here_ws:
        _ready(here_ws)
        with _feed(client) as feed:
            snapshot = feed.receive_json()

    assert snapshot["type"] == "presence_snapshot"
    assert here["id"] in snapshot["online"]
    assert gone["id"] not in snapshot["online"]


def test_a_conversation_with_only_an_agent_is_not_online(client):
    convo = _new_conversation(client, "Agent Only")
    with client.websocket_connect(_agent_url(convo)) as agent_ws:
        _ready(agent_ws)
        with _feed(client) as feed:
            assert convo["id"] not in feed.receive_json()["online"]


def test_visitor_with_two_tabs_stays_online_until_the_last_one_closes(client):
    # Regression test: closing either tab announced the visitor as offline.
    convo = _new_conversation(client, "Two Tabs")

    with _feed(client) as feed:
        feed.receive_json()  # snapshot
        with client.websocket_connect(_client_url(convo)) as tab_a:
            _ready(tab_a)
            with client.websocket_connect(_client_url(convo)) as tab_b:
                _ready(tab_b)
            tab_a.send_json({"type": "message", "body": "still here"})
            tab_a.receive_json()
        # Each connect sends presence + new_activity (4), then the message,
        # then the final offline. An early offline would push the message
        # out of the sixth slot.
        events = [feed.receive_json() for _ in range(6)]

    assert [e["type"] for e in events[4:]] == ["new_message", "presence"]
    assert events[5]["status"] == "offline"


def test_peer_is_told_when_someone_leaves_mid_typing(client):
    # Regression test: if the other side dropped while typing, "typing…"
    # stayed on screen forever.
    convo = _new_conversation(client, "Typist")

    with client.websocket_connect(_agent_url(convo)) as agent_ws:
        _ready(agent_ws)
        with client.websocket_connect(_client_url(convo)) as client_ws:
            _ready(client_ws)
            client_ws.send_json({"type": "typing", "is_typing": True})
            assert _events_until(agent_ws, "typing")[-1]["is_typing"] is True
        left = _events_until(agent_ws, "typing")[-1]

    assert left["is_typing"] is False


def test_leaving_without_typing_sends_no_typing_event(client):
    convo = _new_conversation(client, "Quiet")

    with client.websocket_connect(_agent_url(convo)) as agent_ws:
        _ready(agent_ws)
        with client.websocket_connect(_client_url(convo)) as client_ws:
            _ready(client_ws)
        agent_ws.send_json({"type": "message", "body": "anyone there?"})
        events = _events_until(agent_ws, "message")

    assert not any(e["type"] == "typing" for e in events)


class FakeSocket:
    def __init__(self):
        self.gone = False
        self.received = []

    async def accept(self):
        pass

    async def send_text(self, text):
        if self.gone:
            raise RuntimeError("connection is gone")
        self.received.append(json.loads(text))


def test_socket_dropped_by_a_failed_broadcast_still_announces_offline():
    # Regression test: a broadcast that hit a dead socket removed it quietly,
    # and the handler's own disconnect then found nothing left to announce,
    # so the visitor stayed "online" on every dashboard forever.
    async def scenario():
        manager = ConnectionManager()
        agent, visitor = FakeSocket(), FakeSocket()
        await manager.connect(agent, AGENTS_ROOM, role="agent", name="Amy")
        await manager.connect(visitor, "c1", role="client", name="Alice")

        visitor.gone = True  # network dropped, no close frame
        await manager.broadcast("c1", {"type": "typing"})
        await manager.disconnect(visitor)  # the handler noticing, later

        return [e["status"] for e in agent.received if e["type"] == "presence"]

    assert asyncio.run(scenario()) == ["online", "offline"]

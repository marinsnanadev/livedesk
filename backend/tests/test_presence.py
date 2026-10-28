import asyncio
import json

from app.connection_manager import AGENTS_ROOM, ConnectionManager
from helpers import agent_url, agents_feed, client_url, events_until, new_conversation, ready


def test_agents_feed_starts_with_a_snapshot_of_who_is_online(client):
    # Regression test: presence events only describe changes, so a dashboard
    # that logged in after a visitor connected saw them as offline until they
    # reconnected.
    here = new_conversation(client, "Here")
    gone = new_conversation(client, "Gone")
    with client.websocket_connect(client_url(gone)) as gone_ws:
        ready(gone_ws)

    with client.websocket_connect(client_url(here)) as here_ws:
        ready(here_ws)
        with agents_feed(client) as feed:
            snapshot = feed.receive_json()

    assert snapshot["type"] == "presence_snapshot"
    assert here["id"] in snapshot["online"]
    assert gone["id"] not in snapshot["online"]


def test_a_conversation_with_only_an_agent_is_not_online(client):
    convo = new_conversation(client, "Agent Only")
    with client.websocket_connect(agent_url(convo)) as agent_ws:
        ready(agent_ws)
        with agents_feed(client) as feed:
            assert convo["id"] not in feed.receive_json()["online"]


def test_visitor_with_two_tabs_stays_online_until_the_last_one_closes(client):
    # Regression test: closing either tab announced the visitor as offline.
    convo = new_conversation(client, "Two Tabs")

    with agents_feed(client) as feed:
        feed.receive_json()  # snapshot
        with client.websocket_connect(client_url(convo)) as tab_a:
            ready(tab_a)
            with client.websocket_connect(client_url(convo)) as tab_b:
                ready(tab_b)
            tab_a.send_json({"type": "message", "body": "still here"})
            tab_a.receive_json()
        # Each connect sends a presence event (2), the message sends
        # new_activity + new_message (2 more), then the final offline. An early
        # offline would push the message out of the fifth slot.
        events = [feed.receive_json() for _ in range(5)]

    assert [e["type"] for e in events[3:]] == ["new_message", "presence"]
    assert events[4]["status"] == "offline"


def test_peer_is_told_when_someone_leaves_mid_typing(client):
    # Regression test: if the other side dropped while typing, "typing…"
    # stayed on screen forever.
    convo = new_conversation(client, "Typist")

    with client.websocket_connect(agent_url(convo)) as agent_ws:
        ready(agent_ws)
        with client.websocket_connect(client_url(convo)) as client_ws:
            ready(client_ws)
            client_ws.send_json({"type": "typing", "is_typing": True})
            assert events_until(agent_ws, "typing")[-1]["is_typing"] is True
        left = events_until(agent_ws, "typing")[-1]

    assert left["is_typing"] is False


def test_leaving_without_typing_sends_no_typing_event(client):
    convo = new_conversation(client, "Quiet")

    with client.websocket_connect(agent_url(convo)) as agent_ws:
        ready(agent_ws)
        with client.websocket_connect(client_url(convo)) as client_ws:
            ready(client_ws)
        agent_ws.send_json({"type": "message", "body": "anyone there?"})
        events = events_until(agent_ws, "message")

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

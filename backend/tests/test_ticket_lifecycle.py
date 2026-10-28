from app.main import AGENT_TOKEN
from helpers import agent_url, agents_feed, client_url, events_until, new_conversation, ready, send_message

AGENT_HEADERS = {"X-Agent-Token": AGENT_TOKEN}


def _tickets(client):
    return client.get("/api/conversations", headers=AGENT_HEADERS).json()


def _open_ticket(client, name, body="hello"):
    convo = new_conversation(client, name)
    with client.websocket_connect(client_url(convo, name)) as ws:
        ready(ws)
        send_message(ws, body)
    return convo


def _set_status(client, convo, status):
    resp = client.patch(f"/api/conversations/{convo['id']}", json={"status": status}, headers=AGENT_HEADERS)
    assert resp.status_code == 200


def test_a_conversation_is_not_a_ticket_until_the_visitor_writes(client):
    # Regression test: opening the widget created a conversation that showed
    # up in every agent's queue, empty, even if the visitor never typed.
    empty = new_conversation(client, "Walked Away")
    assert empty["id"] not in [t["id"] for t in _tickets(client)]

    with client.websocket_connect(client_url(empty)) as ws:
        ready(ws)
        send_message(ws, "actually, one question")
    assert empty["id"] in [t["id"] for t in _tickets(client)]


def test_tickets_are_ordered_by_latest_message_and_carry_a_preview(client):
    # Regression test: the list was sorted by creation time, so a ticket that
    # just got a reply sat below ones nobody had touched in hours.
    older = new_conversation(client, "Older")
    newer = new_conversation(client, "Newer")
    long_body = "x" * 120

    with client.websocket_connect(client_url(older)) as older_ws, client.websocket_connect(client_url(newer)) as newer_ws:
        ready(older_ws)
        ready(newer_ws)
        send_message(older_ws, "first words")
        send_message(newer_ws, "second words")
        send_message(older_ws, long_body)

    ours = [t for t in _tickets(client) if t["id"] in (older["id"], newer["id"])]
    assert [t["id"] for t in ours] == [older["id"], newer["id"]]
    assert ours[0]["last_message_preview"] == "x" * 80
    assert ours[0]["last_sender_role"] == "client"
    assert ours[1]["last_message_preview"] == "second words"


def test_the_first_message_announces_the_ticket_and_connecting_does_not(client):
    # Regression test: new_activity used to fire on every connect, so the
    # dashboard added a ticket for a visitor who hadn't said anything.
    convo = new_conversation(client, "Anna")

    with agents_feed(client) as feed:
        feed.receive_json()  # snapshot
        with client.websocket_connect(client_url(convo, "Anna")) as ws:
            ready(ws)
            send_message(ws, "first")
            send_message(ws, "second")
        events = [feed.receive_json() for _ in range(4)]

    assert [e["type"] for e in events] == ["presence", "new_activity", "new_message", "new_message"]
    assert events[1]["client_name"] == "Anna"
    assert events[2]["preview"] == "first"
    assert events[2]["created_at"].endswith("+00:00")


def test_a_client_message_reopens_a_resolved_ticket(client):
    # Regression test: a customer writing back to a resolved ticket got no
    # answer, because it stayed resolved and nobody was watching it.
    convo = _open_ticket(client, "Came Back")
    _set_status(client, convo, "resolved")

    with agents_feed(client) as feed:
        feed.receive_json()  # snapshot
        with client.websocket_connect(client_url(convo, "Came Back")) as ws:
            ready(ws)
            send_message(ws, "it broke again")
            reopened = events_until(feed, "ticket_updated")[-1]

    assert reopened["conversation_id"] == convo["id"]
    assert reopened["status"] == "open"
    assert next(t for t in _tickets(client) if t["id"] == convo["id"])["status"] == "open"


def test_an_agent_reply_does_not_reopen_a_resolved_ticket(client):
    convo = _open_ticket(client, "Stays Closed")
    _set_status(client, convo, "resolved")

    with client.websocket_connect(agent_url(convo)) as ws:
        ready(ws)
        send_message(ws, "glad it's sorted")

    assert next(t for t in _tickets(client) if t["id"] == convo["id"])["status"] == "resolved"


def test_a_client_message_on_an_open_ticket_sends_no_ticket_update(client):
    convo = _open_ticket(client, "Still Open")

    with agents_feed(client) as feed:
        feed.receive_json()  # snapshot
        with client.websocket_connect(client_url(convo, "Still Open")) as ws:
            ready(ws)
            send_message(ws, "one more thing")
        # presence (connect), new_message, then presence (left). A stray
        # ticket_updated would take the middle or last slot.
        events = [feed.receive_json() for _ in range(3)]

    assert [e["type"] for e in events] == ["presence", "new_message", "presence"]

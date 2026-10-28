from app.main import AGENT_TOKEN


def new_conversation(client, name="Visitor"):
    return client.post("/api/conversations", json={"client_name": name}).json()


def client_url(convo, name="Visitor"):
    return f"/ws/conversations/{convo['id']}?role=client&name={name}&token={convo['client_token']}"


def agent_url(convo):
    return f"/ws/conversations/{convo['id']}?role=agent&name=Amy&token={AGENT_TOKEN}"


def agents_feed(client):
    return client.websocket_connect(f"/ws/agents?name=Watcher&token={AGENT_TOKEN}")


def ready(ws):
    # The handshake can complete before the server has put the socket in its
    # room, so anything broadcast right after connecting may miss it. The
    # error reply proves the server's handler loop is already running.
    ws.send_text("ping")
    assert ws.receive_json()["type"] == "error"


def events_until(ws, event_type):
    # An agent socket on a conversation also sits in the agents room, so
    # presence events arrive between the ones a test is waiting for.
    events = [ws.receive_json()]
    while events[-1]["type"] != event_type:
        events.append(ws.receive_json())
    return events


def send_message(ws, body):
    ws.send_json({"type": "message", "body": body})
    return ws.receive_json()

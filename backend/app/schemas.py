from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, field_serializer


# SQLite (unlike Postgres) silently drops tzinfo on write, so a value
# saved as UTC comes back "naive" — datetime.isoformat() then omits the
# offset, and JS's `new Date(...)` misreads it as *local* time instead
# of UTC. Every value stored here is UTC by convention (see models.py),
# so treat a naive value as UTC before serializing rather than trusting
# whatever tzinfo (or lack of it) the DB driver handed back.
def _as_utc_isoformat(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    sender_role: str
    sender_name: str
    body: str
    created_at: datetime

    @field_serializer("created_at")
    def _serialize_created_at(self, value: datetime) -> str:
        return _as_utc_isoformat(value)


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    client_name: str
    status: str
    created_at: datetime

    @field_serializer("created_at")
    def _serialize_created_at(self, value: datetime) -> str:
        return _as_utc_isoformat(value)


class ConversationCreate(BaseModel):
    client_name: str = "Visitor"

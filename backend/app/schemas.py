from datetime import datetime
from pydantic import BaseModel, ConfigDict


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    sender_role: str
    sender_name: str
    body: str
    created_at: datetime


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    client_name: str
    status: str
    created_at: datetime


class ConversationCreate(BaseModel):
    client_name: str = "Visitor"

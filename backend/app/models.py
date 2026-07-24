"""
Persisted data. WebSockets carry the "live" layer (presence, typing),
but every message and conversation lives here — so a page refresh,
or an agent joining mid-conversation, never loses history.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
import enum

from .database import Base


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class ConversationStatus(str, enum.Enum):
    open = "open"
    closed = "closed"


class SenderRole(str, enum.Enum):
    client = "client"
    agent = "agent"


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=new_id)
    client_name = Column(String, nullable=False, default="Visitor")
    status = Column(SAEnum(ConversationStatus), default=ConversationStatus.open, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    messages = relationship("Message", back_populates="conversation", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=new_id)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    sender_role = Column(SAEnum(SenderRole), nullable=False)
    sender_name = Column(String, nullable=False)
    body = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    conversation = relationship("Conversation", back_populates="messages")

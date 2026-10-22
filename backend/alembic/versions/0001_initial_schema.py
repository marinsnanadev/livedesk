"""initial schema

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

ENUM_NAMES = ("senderrole", "conversationpriority", "conversationstatus")


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("client_name", sa.String(), nullable=False),
        sa.Column("status", sa.Enum("open", "in_progress", "resolved", name="conversationstatus"), nullable=False),
        sa.Column("priority", sa.Enum("low", "medium", "high", "urgent", name="conversationpriority"), nullable=False),
        sa.Column("assigned_to", sa.String(), nullable=True),
        sa.Column("client_token", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("conversation_id", sa.String(), nullable=False),
        sa.Column("sender_role", sa.Enum("client", "agent", name="senderrole"), nullable=False),
        sa.Column("sender_name", sa.String(), nullable=False),
        sa.Column("body", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_messages_conversation_id"), "messages", ["conversation_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_messages_conversation_id"), table_name="messages")
    op.drop_table("messages")
    op.drop_table("conversations")
    # Postgres keeps enum types around after their tables are gone.
    for name in ENUM_NAMES:
        sa.Enum(name=name).drop(op.get_bind(), checkfirst=True)

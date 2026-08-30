"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-08-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

scope_type = postgresql.ENUM("personal", "group", name="scope_type", create_type=False)
list_type = postgresql.ENUM("shopping", "tasks", name="list_type", create_type=False)
item_status = postgresql.ENUM("active", "completed", "cancelled", name="item_status", create_type=False)


def upgrade() -> None:
    scope_type.create(op.get_bind(), checkfirst=True)
    list_type.create(op.get_bind(), checkfirst=True)
    item_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "scopes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scope_type", scope_type, nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_scopes_telegram_chat_id", "scopes", ["telegram_chat_id"], unique=True)

    op.create_table(
        "telegram_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("ha_user_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_telegram_users_telegram_user_id", "telegram_users", ["telegram_user_id"], unique=True
    )

    op.create_table(
        "link_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("ha_user_id", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_link_codes_code", "link_codes", ["code"], unique=True)

    op.create_table(
        "lists",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scopes.id", ondelete="CASCADE")),
        sa.Column("list_type", list_type, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_lists_scope_id", "lists", ["scope_id"])

    op.create_table(
        "items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("list_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("lists.id", ondelete="CASCADE")),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", item_status, nullable=False, server_default="active"),
        sa.Column(
            "created_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("telegram_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_recurring", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("rrule", sa.String(length=255), nullable=True),
        sa.Column(
            "notifications_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("last_notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_notify_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_items_list_id", "items", ["list_id"])
    op.create_index("ix_items_next_notify", "items", ["next_notify_at"])


def downgrade() -> None:
    op.drop_index("ix_items_next_notify", table_name="items")
    op.drop_index("ix_items_list_id", table_name="items")
    op.drop_table("items")
    op.drop_index("ix_lists_scope_id", table_name="lists")
    op.drop_table("lists")
    op.drop_index("ix_link_codes_code", table_name="link_codes")
    op.drop_table("link_codes")
    op.drop_index("ix_telegram_users_telegram_user_id", table_name="telegram_users")
    op.drop_table("telegram_users")
    op.drop_index("ix_scopes_telegram_chat_id", table_name="scopes")
    op.drop_table("scopes")
    item_status.drop(op.get_bind(), checkfirst=True)
    list_type.drop(op.get_bind(), checkfirst=True)
    scope_type.drop(op.get_bind(), checkfirst=True)

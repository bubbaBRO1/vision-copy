"""Add projects table, project_id FKs, incognito flag on chat_sessions

Revision ID: 0003
Revises: 0002_google_guest
Create Date: 2026-05-07
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0003"
down_revision: Union[str, None] = "0002_google_guest"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_projects_user_id", "projects", ["user_id"])

    # searches
    op.add_column("searches", sa.Column("project_id", UUID(as_uuid=True), nullable=True))
    op.create_index("ix_searches_project_id", "searches", ["project_id"])

    # collections
    op.add_column("collections", sa.Column("project_id", UUID(as_uuid=True), nullable=True))
    op.create_index("ix_collections_project_id", "collections", ["project_id"])

    # chat_sessions
    op.add_column("chat_sessions", sa.Column("project_id", UUID(as_uuid=True), nullable=True))
    op.add_column("chat_sessions", sa.Column("is_incognito", sa.Boolean, nullable=False, server_default="false"))
    op.create_index("ix_chat_sessions_project_id", "chat_sessions", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_chat_sessions_project_id", table_name="chat_sessions")
    op.drop_column("chat_sessions", "is_incognito")
    op.drop_column("chat_sessions", "project_id")

    op.drop_index("ix_collections_project_id", table_name="collections")
    op.drop_column("collections", "project_id")

    op.drop_index("ix_searches_project_id", table_name="searches")
    op.drop_column("searches", "project_id")

    op.drop_index("ix_projects_user_id", table_name="projects")
    op.drop_table("projects")

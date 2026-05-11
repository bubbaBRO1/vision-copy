"""Add case workspace tables

Revision ID: 0005_case_workspace
Revises: 0004_memory
Create Date: 2026-05-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision: str = "0005_case_workspace"
down_revision: Union[str, tuple[str, str], None] = "0004_memory"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "case_evidence",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", UUID(as_uuid=True), nullable=False),
        sa.Column("search_id", UUID(as_uuid=True), nullable=True),
        sa.Column("result_key", sa.String(512), nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("evidence_type", sa.String(50), nullable=False, server_default="note"),
        sa.Column("status", sa.String(40), nullable=False, server_default="needs_review"),
        sa.Column("confidence", sa.Integer(), nullable=True),
        sa.Column("source_url", sa.String(1024), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("tags", JSONB, nullable=True),
        sa.Column("provenance", JSONB, nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("include_in_report", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    for col in ["user_id", "project_id", "search_id", "result_key", "evidence_type", "status"]:
        op.create_index(f"ix_case_evidence_{col}", "case_evidence", [col])

    op.create_table(
        "case_entities",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False, server_default="unknown"),
        sa.Column("confidence", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    for col in ["user_id", "project_id", "entity_type"]:
        op.create_index(f"ix_case_entities_{col}", "case_entities", [col])

    op.create_table(
        "case_timeline_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False, server_default="note"),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata_json", JSONB, nullable=True),
    )
    for col in ["user_id", "project_id", "event_type", "occurred_at"]:
        op.create_index(f"ix_case_timeline_events_{col}", "case_timeline_events", [col])

    op.create_table(
        "case_report_drafts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("format", sa.String(20), nullable=False, server_default="markdown"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    for col in ["user_id", "project_id"]:
        op.create_index(f"ix_case_report_drafts_{col}", "case_report_drafts", [col])

    op.create_table(
        "case_ai_insights",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("disclaimer", sa.Text(), nullable=False),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    for col in ["user_id", "project_id", "action"]:
        op.create_index(f"ix_case_ai_insights_{col}", "case_ai_insights", [col])


def downgrade() -> None:
    for table, cols in [
        ("case_ai_insights", ["action", "project_id", "user_id"]),
        ("case_report_drafts", ["project_id", "user_id"]),
        ("case_timeline_events", ["occurred_at", "event_type", "project_id", "user_id"]),
        ("case_entities", ["entity_type", "project_id", "user_id"]),
        ("case_evidence", ["status", "evidence_type", "result_key", "search_id", "project_id", "user_id"]),
    ]:
        for col in cols:
            op.drop_index(f"ix_{table}_{col}", table_name=table)
        op.drop_table(table)

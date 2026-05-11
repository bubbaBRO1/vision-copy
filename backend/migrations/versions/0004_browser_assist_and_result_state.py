"""Add browser assist and search result state tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "search_result_states",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("search_id", UUID(as_uuid=True), nullable=False),
        sa.Column("result_key", sa.String(512), nullable=False),
        sa.Column("saved", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("hidden", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_search_result_states_user_id", "search_result_states", ["user_id"])
    op.create_index("ix_search_result_states_search_id", "search_result_states", ["search_id"])
    op.create_index("ix_search_result_states_result_key", "search_result_states", ["result_key"])

    op.create_table(
        "browser_assist_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("search_id", UUID(as_uuid=True), nullable=True),
        sa.Column("project_id", UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("mode", sa.String(32), nullable=False, server_default="isolated"),
        sa.Column("approved_urls", JSONB, nullable=False, server_default="[]"),
        sa.Column("visited_urls", JSONB, nullable=False, server_default="[]"),
        sa.Column("run_log", JSONB, nullable=False, server_default="[]"),
        sa.Column("is_incognito", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("persist_artifacts", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_browser_assist_runs_user_id", "browser_assist_runs", ["user_id"])
    op.create_index("ix_browser_assist_runs_search_id", "browser_assist_runs", ["search_id"])
    op.create_index("ix_browser_assist_runs_project_id", "browser_assist_runs", ["project_id"])

    op.create_table(
        "browser_assist_artifacts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("source_url", sa.String(1024), nullable=False),
        sa.Column("final_url", sa.String(1024), nullable=True),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("screenshot_path", sa.String(1024), nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_browser_assist_artifacts_run_id", "browser_assist_artifacts", ["run_id"])
    op.create_index("ix_browser_assist_artifacts_user_id", "browser_assist_artifacts", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_browser_assist_artifacts_user_id", table_name="browser_assist_artifacts")
    op.drop_index("ix_browser_assist_artifacts_run_id", table_name="browser_assist_artifacts")
    op.drop_table("browser_assist_artifacts")

    op.drop_index("ix_browser_assist_runs_project_id", table_name="browser_assist_runs")
    op.drop_index("ix_browser_assist_runs_search_id", table_name="browser_assist_runs")
    op.drop_index("ix_browser_assist_runs_user_id", table_name="browser_assist_runs")
    op.drop_table("browser_assist_runs")

    op.drop_index("ix_search_result_states_result_key", table_name="search_result_states")
    op.drop_index("ix_search_result_states_search_id", table_name="search_result_states")
    op.drop_index("ix_search_result_states_user_id", table_name="search_result_states")
    op.drop_table("search_result_states")

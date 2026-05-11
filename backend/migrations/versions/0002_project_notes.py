"""Add notes column to projects

Revision ID: 0002_project_notes
Revises: 0003
Create Date: 2026-05-07
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0002_project_notes"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("notes", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "notes")

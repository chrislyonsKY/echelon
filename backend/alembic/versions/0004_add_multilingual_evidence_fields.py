"""Add multilingual original/translated fields to evidence.

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-28

Signals keep multilingual text inside raw_payload for compatibility.
Evidence gets first-class original/translated fields because it is
already rendered directly in analyst-facing UI.
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("evidence", sa.Column("title_original", sa.Text()))
    op.add_column("evidence", sa.Column("description_original", sa.Text()))
    op.add_column("evidence", sa.Column("title_translated", sa.Text()))
    op.add_column("evidence", sa.Column("description_translated", sa.Text()))
    op.add_column("evidence", sa.Column("text_direction", sa.Text()))
    op.add_column("evidence", sa.Column("translation_status", sa.Text()))


def downgrade() -> None:
    op.drop_column("evidence", "translation_status")
    op.drop_column("evidence", "text_direction")
    op.drop_column("evidence", "description_translated")
    op.drop_column("evidence", "title_translated")
    op.drop_column("evidence", "description_original")
    op.drop_column("evidence", "title_original")

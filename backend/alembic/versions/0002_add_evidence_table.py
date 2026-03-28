"""Add evidence table for video/media attached to signal events.

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-28

Evidence is attached to events — provenance determines trust,
graphic classification determines presentation. Evidence never
affects convergence scoring.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

TIMESTAMPTZ = sa.DateTime(timezone=True)

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evidence",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("signal_id", UUID(as_uuid=True), sa.ForeignKey("signals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.Text, nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("platform", sa.Text),
        sa.Column("thumbnail_url", sa.Text),
        sa.Column("title", sa.Text),
        sa.Column("description", sa.Text),
        sa.Column("author", sa.Text),
        sa.Column("language", sa.Text),
        sa.Column("published_at", TIMESTAMPTZ),
        sa.Column("attached_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("NOW()")),
        sa.Column("provenance_family", sa.Text),
        sa.Column("confirmation_policy", sa.Text),
        sa.Column("geolocation_status", sa.Text, server_default="unverified"),
        sa.Column("time_verification_status", sa.Text, server_default="unverified"),
        sa.Column("graphic_flag", sa.Boolean, server_default="false"),
        sa.Column("graphic_confidence", sa.Float),
        sa.Column("graphic_reason", sa.Text),
        sa.Column("review_status", sa.Text, nullable=False, server_default="unreviewed"),
        sa.Column("restricted", sa.Boolean, server_default="false"),
        sa.Column("restricted_reason", sa.Text),
        sa.Column("content_hash", sa.Text),
        sa.Column("moderation_payload", JSONB),
    )

    op.create_index("ix_evidence_signal_id", "evidence", ["signal_id"])
    op.create_index("ix_evidence_type", "evidence", ["type"])
    op.create_index("ix_evidence_review_status", "evidence", ["review_status"])


def downgrade() -> None:
    op.drop_table("evidence")

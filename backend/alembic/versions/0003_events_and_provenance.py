"""Add events table, event_signals junction, and provenance columns on signals.

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-28

Events cluster related signals into analyst-facing incidents.
Provenance columns normalize source trust metadata across all ingestors.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

TIMESTAMPTZ = sa.DateTime(timezone=True)

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Events table ──────────────────────────────────────────────────────
    op.create_table(
        "events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column("location", sa.Text, nullable=False),  # Geography handled via raw SQL below
        sa.Column("h3_index_7", sa.Text, nullable=False),
        sa.Column("first_seen", TIMESTAMPTZ, nullable=False),
        sa.Column("last_seen", TIMESTAMPTZ, nullable=False),
        sa.Column("source_families", JSONB, nullable=False, server_default="[]"),
        sa.Column("corroboration_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("confirmation_status", sa.Text, nullable=False, server_default="unconfirmed"),
        sa.Column("signal_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("summary", sa.Text),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("NOW()")),
    )

    # Replace the TEXT location column with proper Geography
    op.execute("ALTER TABLE events DROP COLUMN location")
    op.execute("SELECT AddGeographyColumn('events', 'location', 4326, 'POINT', 2)")
    op.execute("ALTER TABLE events ALTER COLUMN location SET NOT NULL")

    op.create_index("ix_events_event_type", "events", ["event_type"])
    op.create_index("ix_events_h3_index_7", "events", ["h3_index_7"])
    op.create_index("ix_events_first_seen", "events", ["first_seen"])
    op.create_index("ix_events_confirmation_status", "events", ["confirmation_status"])

    # ── Event–Signal junction ─────────────────────────────────────────────
    op.create_table(
        "event_signals",
        sa.Column("event_id", UUID(as_uuid=True), sa.ForeignKey("events.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("signal_id", UUID(as_uuid=True), sa.ForeignKey("signals.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_index("ix_event_signals_signal_id", "event_signals", ["signal_id"])

    # ── Provenance columns on signals ─────────────────────────────────────
    op.add_column("signals", sa.Column("provenance_family", sa.Text))
    op.add_column("signals", sa.Column("confirmation_policy", sa.Text))


def downgrade() -> None:
    op.drop_column("signals", "confirmation_policy")
    op.drop_column("signals", "provenance_family")
    op.drop_table("event_signals")
    op.drop_table("events")

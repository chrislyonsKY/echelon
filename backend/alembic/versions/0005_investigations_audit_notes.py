"""Add investigations, audit log, analyst notes, false positive feedback, confidence breakdown

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Investigations — saved analytical views
    op.create_table(
        "investigations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("viewport", postgresql.JSONB, nullable=False),
        sa.Column("date_range", postgresql.JSONB, nullable=False),
        sa.Column("active_layers", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("filters", postgresql.JSONB, server_default="{}"),
        sa.Column("aoi_geojson", postgresql.JSONB),
        sa.Column("selected_events", postgresql.JSONB, server_default="[]"),
        sa.Column("imagery_selections", postgresql.JSONB, server_default="[]"),
        sa.Column("notes", sa.Text),
        sa.Column("tags", postgresql.JSONB, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_investigations_user_id", "investigations", ["user_id"])

    # Event audit log — immutable trail
    op.create_table(
        "event_audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("actor_type", sa.Text, nullable=False, server_default="system"),
        sa.Column("actor_id", sa.Text),
        sa.Column("detail", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_event_audit_log_event_id", "event_audit_log", ["event_id"])

    # Analyst notes
    op.create_table(
        "analyst_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("events.id", ondelete="CASCADE")),
        sa.Column("h3_index", sa.Text),
        sa.Column("note_type", sa.Text, nullable=False, server_default="observation"),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("confidence", sa.Text),
        sa.Column("reviewed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_analyst_notes_user_id", "analyst_notes", ["user_id"])
    op.create_index("ix_analyst_notes_event_id", "analyst_notes", ["event_id"])
    op.create_index("ix_analyst_notes_h3_index", "analyst_notes", ["h3_index"])

    # False positive feedback
    op.create_table(
        "false_positive_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("events.id", ondelete="CASCADE")),
        sa.Column("h3_index", sa.Text),
        sa.Column("signal_ids", postgresql.JSONB, server_default="[]"),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("detail", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_false_positive_feedback_event_id", "false_positive_feedback", ["event_id"])

    # Confidence breakdown columns on h3_convergence_scores
    op.add_column("h3_convergence_scores", sa.Column("confidence_statistical", sa.Float))
    op.add_column("h3_convergence_scores", sa.Column("confidence_diversity", sa.Float))
    op.add_column("h3_convergence_scores", sa.Column("confidence_sensor", sa.Float))
    op.add_column("h3_convergence_scores", sa.Column("confidence_media", sa.Float))
    op.add_column("h3_convergence_scores", sa.Column("confidence_reviewed", sa.Float))

    # Spatial uncertainty on signals
    op.add_column("signals", sa.Column("geo_precision", sa.Text))
    op.add_column("signals", sa.Column("geo_radius_km", sa.Float))

    # Debunking workflow on events
    op.add_column("events", sa.Column("debunk_status", sa.Text))
    op.add_column("events", sa.Column("debunk_reason", sa.Text))
    op.add_column("events", sa.Column("debunked_by", postgresql.UUID(as_uuid=True)))
    op.add_column("events", sa.Column("debunked_at", sa.DateTime(timezone=True)))
    op.add_column("events", sa.Column("trust_stage", sa.Text, server_default="raw"))
    op.add_column("events", sa.Column("scoring_version", sa.Text))

    # Alert outcome tracking for calibration
    op.add_column("alerts", sa.Column("outcome", sa.Text))
    op.add_column("alerts", sa.Column("outcome_by", postgresql.UUID(as_uuid=True)))
    op.add_column("alerts", sa.Column("outcome_at", sa.DateTime(timezone=True)))
    op.add_column("alerts", sa.Column("outcome_notes", sa.Text))


def downgrade() -> None:
    op.drop_column("alerts", "outcome_notes")
    op.drop_column("alerts", "outcome_at")
    op.drop_column("alerts", "outcome_by")
    op.drop_column("alerts", "outcome")
    op.drop_column("events", "scoring_version")
    op.drop_column("events", "trust_stage")
    op.drop_column("events", "debunked_at")
    op.drop_column("events", "debunked_by")
    op.drop_column("events", "debunk_reason")
    op.drop_column("events", "debunk_status")
    op.drop_column("signals", "geo_radius_km")
    op.drop_column("signals", "geo_precision")
    op.drop_column("h3_convergence_scores", "confidence_reviewed")
    op.drop_column("h3_convergence_scores", "confidence_media")
    op.drop_column("h3_convergence_scores", "confidence_sensor")
    op.drop_column("h3_convergence_scores", "confidence_diversity")
    op.drop_column("h3_convergence_scores", "confidence_statistical")
    op.drop_table("false_positive_feedback")
    op.drop_table("analyst_notes")
    op.drop_table("event_audit_log")
    op.drop_table("investigations")

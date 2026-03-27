"""Initial schema — all tables, PostGIS extension, H3 indexes.

Revision ID: 0001
Revises:
Create Date: 2025-03-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

TIMESTAMPTZ = sa.DateTime(timezone=True)
import geoalchemy2

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable PostGIS and pgcrypto extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # signals
    op.create_table(
        "signals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("signal_type", sa.Text, nullable=False),
        sa.Column("h3_index_5", sa.Text, nullable=False),
        sa.Column("h3_index_7", sa.Text, nullable=False),
        sa.Column("h3_index_9", sa.Text, nullable=False),
        sa.Column("location", geoalchemy2.Geography("POINT", srid=4326), nullable=False),
        sa.Column("occurred_at", TIMESTAMPTZ, nullable=False),
        sa.Column("ingested_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("NOW()")),
        sa.Column("weight", sa.Float, nullable=False),
        sa.Column("raw_payload", JSONB),
        sa.Column("source_id", sa.Text),
        sa.Column("dedup_hash", sa.Text, nullable=False, unique=True),
    )
    op.create_index("ix_signals_source", "signals", ["source"])
    op.create_index("ix_signals_signal_type", "signals", ["signal_type"])
    op.create_index("ix_signals_h3_index_5", "signals", ["h3_index_5"])
    op.create_index("ix_signals_h3_index_7", "signals", ["h3_index_7"])
    op.create_index("ix_signals_h3_index_9", "signals", ["h3_index_9"])
    op.create_index("ix_signals_occurred_at", "signals", ["occurred_at"])

    # h3_cell_baseline
    op.create_table(
        "h3_cell_baseline",
        sa.Column("h3_index", sa.Text, nullable=False),
        sa.Column("resolution", sa.Integer, nullable=False),
        sa.Column("signal_source", sa.Text, nullable=False),
        sa.Column("window_days", sa.Integer, nullable=False, server_default="365"),
        sa.Column("mu", sa.Float, nullable=False),
        sa.Column("sigma", sa.Float, nullable=False),
        sa.Column("observation_count", sa.Integer, nullable=False),
        sa.Column("last_computed", TIMESTAMPTZ, nullable=False),
        sa.Column("low_confidence", sa.Boolean, nullable=False, server_default="false"),
        sa.PrimaryKeyConstraint("h3_index", "resolution", "signal_source"),
    )

    # h3_convergence_scores
    op.create_table(
        "h3_convergence_scores",
        sa.Column("h3_index", sa.Text, nullable=False),
        sa.Column("resolution", sa.Integer, nullable=False),
        sa.Column("z_score", sa.Float, nullable=False),
        sa.Column("raw_score", sa.Float, nullable=False),
        sa.Column("signal_breakdown", JSONB),
        sa.Column("low_confidence", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("computed_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("h3_index", "resolution"),
    )
    op.create_index("ix_convergence_z_score", "h3_convergence_scores", ["z_score"])

    # users
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("github_id", sa.BigInteger, unique=True, nullable=False),
        sa.Column("github_username", sa.Text, nullable=False),
        sa.Column("email", sa.Text),
        sa.Column("byok_key_enc", sa.Text),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("NOW()")),
        sa.Column("last_seen_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("NOW()")),
    )

    # aois
    op.create_table(
        "aois",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("geometry", geoalchemy2.Geography("POLYGON", srid=4326), nullable=False),
        sa.Column("alert_threshold", sa.Float, nullable=False, server_default="2.0"),
        sa.Column("alert_email", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_aois_user_id", "aois", ["user_id"])

    # alerts
    op.create_table(
        "alerts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("aoi_id", UUID(as_uuid=True), sa.ForeignKey("aois.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trigger_type", sa.Text, nullable=False),
        sa.Column("trigger_detail", JSONB, nullable=False),
        sa.Column("h3_index", sa.Text, nullable=False),
        sa.Column("z_score", sa.Float),
        sa.Column("fired_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("NOW()")),
        sa.Column("email_sent", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("read_at", TIMESTAMPTZ),
    )
    op.create_index("ix_alerts_aoi_id", "alerts", ["aoi_id"])
    op.create_index("ix_alerts_fired_at", "alerts", ["fired_at"])


def downgrade() -> None:
    op.drop_table("alerts")
    op.drop_table("aois")
    op.drop_table("users")
    op.drop_table("h3_convergence_scores")
    op.drop_table("h3_cell_baseline")
    op.drop_table("signals")

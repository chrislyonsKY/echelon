"""
Echelon ORM Models

All PostGIS geometry columns use Geography(Point/Polygon, 4326) for
correct spherical distance calculations at global scale.
H3 indexes are stored as TEXT (hex string) — never as integers.

Do NOT call Base.metadata.create_all() — use Alembic migrations.
"""
import uuid
from datetime import datetime

from geoalchemy2 import Geography
from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Float, ForeignKey,
    Integer, Text, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Signal(Base):
    """Unified table for all ingested events across all signal sources."""

    __tablename__ = "signals"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source       = Column(Text, nullable=False, index=True)
    signal_type  = Column(Text, nullable=False, index=True)
    h3_index_5   = Column(Text, nullable=False, index=True)
    h3_index_7   = Column(Text, nullable=False, index=True)
    h3_index_9   = Column(Text, nullable=False, index=True)
    location     = Column(Geography("POINT", srid=4326), nullable=False)
    occurred_at  = Column(DateTime(timezone=True), nullable=False, index=True)
    ingested_at  = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    weight       = Column(Float, nullable=False)
    raw_payload  = Column(JSONB)
    source_id    = Column(Text)
    dedup_hash   = Column(Text, unique=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("dedup_hash", name="uq_signals_dedup_hash"),
    )


class H3CellBaseline(Base):
    """Rolling 365-day statistics per H3 cell per signal source for Z-score normalization."""

    __tablename__ = "h3_cell_baseline"

    h3_index          = Column(Text, nullable=False, primary_key=True)
    resolution        = Column(Integer, nullable=False, primary_key=True)
    signal_source     = Column(Text, nullable=False, primary_key=True)
    window_days       = Column(Integer, nullable=False, default=365)
    mu                = Column(Float, nullable=False)
    sigma             = Column(Float, nullable=False)
    observation_count = Column(Integer, nullable=False)
    last_computed     = Column(DateTime(timezone=True), nullable=False)
    low_confidence    = Column(Boolean, nullable=False, default=False)


class H3ConvergenceScore(Base):
    """Pre-computed convergence Z-scores per H3 cell. Refreshed every 15 minutes."""

    __tablename__ = "h3_convergence_scores"

    h3_index         = Column(Text, nullable=False, primary_key=True)
    resolution       = Column(Integer, nullable=False, primary_key=True)
    z_score          = Column(Float, nullable=False, index=True)
    raw_score        = Column(Float, nullable=False)
    signal_breakdown = Column(JSONB)
    low_confidence   = Column(Boolean, nullable=False, default=False)
    computed_at      = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class User(Base):
    """Authenticated users — GitHub OAuth only, no passwords stored."""

    __tablename__ = "users"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    github_id       = Column(BigInteger, unique=True, nullable=False)
    github_username = Column(Text, nullable=False)
    email           = Column(Text)
    byok_key_enc    = Column(Text)   # AES-256 encrypted Anthropic key, opt-in only
    created_at      = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    last_seen_at    = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    aois   = relationship("AOI", back_populates="user", cascade="all, delete-orphan")


class AOI(Base):
    """User-saved areas of interest with alert configuration."""

    __tablename__ = "aois"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id         = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name            = Column(Text, nullable=False)
    geometry        = Column(Geography("POLYGON", srid=4326), nullable=False)
    alert_threshold = Column(Float, nullable=False, default=2.0)
    alert_email     = Column(Boolean, nullable=False, default=False)
    created_at      = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    user   = relationship("User", back_populates="aois")
    alerts = relationship("Alert", back_populates="aoi", cascade="all, delete-orphan")


class Alert(Base):
    """Fired alert events — stored for in-app notification and email delivery."""

    __tablename__ = "alerts"

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    aoi_id         = Column(UUID(as_uuid=True), ForeignKey("aois.id", ondelete="CASCADE"), nullable=False)
    trigger_type   = Column(Text, nullable=False)
    trigger_detail = Column(JSONB, nullable=False)
    h3_index       = Column(Text, nullable=False)
    z_score        = Column(Float)
    fired_at       = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    email_sent     = Column(Boolean, nullable=False, default=False)
    read_at        = Column(DateTime(timezone=True))

    aoi = relationship("AOI", back_populates="alerts")

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

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source              = Column(Text, nullable=False, index=True)
    signal_type         = Column(Text, nullable=False, index=True)
    h3_index_5          = Column(Text, nullable=False, index=True)
    h3_index_7          = Column(Text, nullable=False, index=True)
    h3_index_9          = Column(Text, nullable=False, index=True)
    location            = Column(Geography("POINT", srid=4326), nullable=False)
    occurred_at         = Column(DateTime(timezone=True), nullable=False, index=True)
    ingested_at         = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    weight              = Column(Float, nullable=False)
    raw_payload         = Column(JSONB)
    source_id           = Column(Text)
    dedup_hash          = Column(Text, unique=True, nullable=False)
    provenance_family   = Column(Text)   # official_sensor, curated_dataset, news_media, open_source, crowd_sourced
    confirmation_policy = Column(Text)   # verified, corroborated, unverified, context_only
    # Spatial uncertainty — geocoding precision class
    geo_precision       = Column(Text)   # exact | address | city | admin1 | country | estimated
    geo_radius_km       = Column(Float)  # confidence radius in km (null = exact/unknown)

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
    # Confidence breakdown — decomposed trust dimensions
    confidence_statistical = Column(Float)  # Z-score magnitude (statistical anomaly strength)
    confidence_diversity   = Column(Float)  # Number of distinct source families contributing
    confidence_sensor      = Column(Float)  # Fraction of score from sensor sources (GFW, OpenSky, FIRMS, Sentinel)
    confidence_media       = Column(Float)  # Fraction of score from media sources (GDELT, news, OSINT)
    confidence_reviewed    = Column(Float)  # Fraction of contributing signals that have been human-reviewed


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


class Event(Base):
    """Clustered incident — groups related signals into a single analytical event.

    Events are the analyst-facing unit of work. A signal is raw data;
    an event is an assessed incident with corroboration from multiple
    independent source families.
    """

    __tablename__ = "events"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title               = Column(Text, nullable=False)
    event_type          = Column(Text, nullable=False, index=True)
    location            = Column(Geography("POINT", srid=4326), nullable=False)
    h3_index_7          = Column(Text, nullable=False, index=True)
    first_seen          = Column(DateTime(timezone=True), nullable=False, index=True)
    last_seen           = Column(DateTime(timezone=True), nullable=False)
    source_families     = Column(JSONB, nullable=False, default=list)
    corroboration_count = Column(Integer, nullable=False, default=1)
    confirmation_status = Column(Text, nullable=False, default="unconfirmed")
    # unconfirmed | single_source | multi_source | corroborated
    debunk_status       = Column(Text)
    # null (not assessed) | false | duplicate | spoofed | mislocated | satire |
    # propaganda | old_imagery | stale_repost | debunked
    debunk_reason       = Column(Text)
    debunked_by         = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    debunked_at         = Column(DateTime(timezone=True))
    signal_count        = Column(Integer, nullable=False, default=0)
    summary             = Column(Text)
    # Trust workflow stage
    trust_stage         = Column(Text, nullable=False, default="raw")
    # raw | corroborated | human_reviewed | geolocated | time_verified | export_ready
    scoring_version     = Column(Text)  # version tag of scoring logic that produced this event
    created_at          = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at          = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    signals = relationship("EventSignal", back_populates="event", cascade="all, delete-orphan")


class EventSignal(Base):
    """Junction table linking events to their supporting signals."""

    __tablename__ = "event_signals"

    event_id  = Column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), primary_key=True)
    signal_id = Column(UUID(as_uuid=True), ForeignKey("signals.id", ondelete="CASCADE"), primary_key=True)

    event = relationship("Event", back_populates="signals")


class Evidence(Base):
    """Evidence items attached to signal events.

    Video is evidence — provenance determines trust,
    graphic classification determines presentation.
    Evidence never affects convergence scoring.
    """

    __tablename__ = "evidence"

    id                        = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    signal_id                 = Column(UUID(as_uuid=True), ForeignKey("signals.id", ondelete="CASCADE"), nullable=False, index=True)
    type                      = Column(Text, nullable=False)  # "video", "image", "document"
    url                       = Column(Text, nullable=False)
    platform                  = Column(Text)  # "youtube", "telegram", "twitter", "tiktok", etc.
    thumbnail_url             = Column(Text)
    title                     = Column(Text)
    description               = Column(Text)
    title_original            = Column(Text)
    description_original      = Column(Text)
    title_translated          = Column(Text)
    description_translated    = Column(Text)
    author                    = Column(Text)
    language                  = Column(Text)
    text_direction            = Column(Text)
    translation_status        = Column(Text)
    published_at              = Column(DateTime(timezone=True))
    attached_at               = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Provenance — determines trust
    provenance_family         = Column(Text)  # "official", "ugc", "aggregator", "context_only"
    confirmation_policy       = Column(Text)  # "wire_confirmed", "context_only", "unverified"

    # Verification status
    geolocation_status        = Column(Text, default="unverified")  # "geolocated", "unverified", "disputed"
    time_verification_status  = Column(Text, default="unverified")  # "verified", "unverified", "disputed"

    # Graphic content — controls presentation only, never scoring
    graphic_flag              = Column(Boolean, default=False)
    graphic_confidence        = Column(Float)  # 0.0-1.0 from moderation model
    graphic_reason            = Column(Text)   # "violence", "gore", "disturbing", etc.

    # Review workflow
    review_status             = Column(Text, nullable=False, default="unreviewed")
    # "unreviewed" | "auto_flagged" | "human_approved" | "human_rejected" | "restricted"

    # Perpetrator/terrorist content — never publicly amplified
    restricted                = Column(Boolean, default=False)
    restricted_reason         = Column(Text)  # "perpetrator_produced", "terrorist_promoted", etc.
    content_hash              = Column(Text)  # SHA-256 for cross-referencing (e.g., GIFCT)

    # Raw metadata from moderation/extraction pipeline
    moderation_payload        = Column(JSONB)


class Investigation(Base):
    """Saved investigation state — replayable view with AOI, layers, filters, and notes.

    Lets analysts save and reopen the exact same analytical context later.
    """

    __tablename__ = "investigations"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id      = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title        = Column(Text, nullable=False)
    description  = Column(Text)
    # Full state snapshot
    viewport     = Column(JSONB, nullable=False)  # {center, zoom, bearing, pitch}
    date_range   = Column(JSONB, nullable=False)  # {from, to}
    active_layers = Column(JSONB, nullable=False, default=list)  # ["gdelt","gfw","opensky",...]
    filters      = Column(JSONB, default=dict)    # source filters, min z-score, etc.
    aoi_geojson  = Column(JSONB)                  # optional AOI polygon
    selected_events = Column(JSONB, default=list) # event IDs the analyst was examining
    imagery_selections = Column(JSONB, default=list) # scene IDs and provider
    notes        = Column(Text)                   # analyst narrative
    tags         = Column(JSONB, default=list)     # freeform tags for organization
    created_at   = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at   = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    user = relationship("User")


class EventAuditLog(Base):
    """Immutable audit trail for event lifecycle changes.

    Records when an event was created, merged, reclassified, annotated,
    exported, or reviewed. Trusted tools show their own history.
    """

    __tablename__ = "event_audit_log"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id   = Column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    action     = Column(Text, nullable=False)
    # created | signal_added | merged | reclassified | annotated | exported |
    # reviewed | verification_changed | false_positive_marked
    actor_type = Column(Text, nullable=False, default="system")  # system | user | celery
    actor_id   = Column(Text)  # user UUID or task name
    detail     = Column(JSONB)  # action-specific context
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class AnalystNote(Base):
    """Analyst notes and peer review on events or H3 cells.

    Supports signed assessments — trust grows when conclusions are attributable.
    """

    __tablename__ = "analyst_notes"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # Polymorphic target — either an event or an H3 cell
    event_id   = Column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), index=True)
    h3_index   = Column(Text, index=True)  # alternative to event_id for cell-level notes
    note_type  = Column(Text, nullable=False, default="observation")
    # observation | assessment | review | correction | question
    content    = Column(Text, nullable=False)
    confidence = Column(Text)  # high | medium | low | uncertain
    reviewed   = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    user = relationship("User")


class FalsePositiveFeedback(Base):
    """Analyst feedback marking events or alert clusters as noise.

    Used to tune weights, deduplication, clustering, and UI warnings over time.
    """

    __tablename__ = "false_positive_feedback"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id     = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    event_id    = Column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), index=True)
    h3_index    = Column(Text, index=True)
    signal_ids  = Column(JSONB, default=list)  # specific signals marked as noise
    reason      = Column(Text, nullable=False)
    # duplicate | natural_hazard | false_geocode | stale_data | data_artifact | other
    detail      = Column(Text)
    created_at  = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    user = relationship("User")


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
    # Calibration — track alert outcomes for hit-rate reporting
    outcome        = Column(Text)  # null (pending) | confirmed | downgraded | dismissed | false_positive
    outcome_by     = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    outcome_at     = Column(DateTime(timezone=True))
    outcome_notes  = Column(Text)

    aoi = relationship("AOI", back_populates="alerts")

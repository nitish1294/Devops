from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import Stage
from app.models.base import Base, TimestampMixin


class Application(Base, TimestampMixin):
    """Candidate x Job. This is the row the pipeline board moves around."""

    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("job_id", "candidate_id", name="uq_job_candidate"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    stage: Mapped[str] = mapped_column(String(20), default=Stage.SOURCED, nullable=False, index=True)
    board_position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    match_score: Mapped[int | None] = mapped_column(Integer)
    rejection_reason: Mapped[str | None] = mapped_column(String(255))
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    job = relationship("Job", back_populates="applications", lazy="joined")
    candidate = relationship("Candidate", back_populates="applications", lazy="joined")
    owner = relationship("User", lazy="joined")
    stage_events = relationship(
        "StageEvent",
        back_populates="application",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="StageEvent.id",
    )
    interviews = relationship(
        "Interview", back_populates="application", lazy="selectin", cascade="all, delete-orphan"
    )
    offers = relationship(
        "Offer", back_populates="application", lazy="selectin", cascade="all, delete-orphan"
    )


class StageEvent(Base):
    """Append-only stage transitions. Powers time-in-stage and time-to-hire."""

    __tablename__ = "stage_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    from_stage: Mapped[str | None] = mapped_column(String(20))
    to_stage: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    moved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    application = relationship("Application", back_populates="stage_events")
    moved_by = relationship("User", lazy="joined")

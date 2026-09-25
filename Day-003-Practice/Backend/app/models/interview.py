from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import InterviewMode, InterviewStatus
from app.models.base import Base, TimestampMixin


class Interview(Base, TimestampMixin):
    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    round_name: Mapped[str] = mapped_column(String(120), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=45, nullable=False)
    mode: Mapped[str] = mapped_column(String(20), default=InterviewMode.VIDEO, nullable=False)
    location_or_link: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(
        String(20), default=InterviewStatus.SCHEDULED, nullable=False, index=True
    )
    feedback_summary: Mapped[str | None] = mapped_column(Text)
    overall_rating: Mapped[int | None] = mapped_column(Integer)  # 1-5
    recommendation: Mapped[str | None] = mapped_column(String(20))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    application = relationship("Application", back_populates="interviews", lazy="joined")
    panelists = relationship(
        "InterviewPanelist",
        back_populates="interview",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    @property
    def panelist_users(self) -> list:
        """The panel as User rows - what the API actually returns."""
        return [p.user for p in (self.panelists or []) if p.user]


class InterviewPanelist(Base):
    __tablename__ = "interview_panelists"

    id: Mapped[int] = mapped_column(primary_key=True)
    interview_id: Mapped[int] = mapped_column(
        ForeignKey("interviews.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    interview = relationship("Interview", back_populates="panelists")
    user = relationship("User", lazy="joined")

from sqlalchemy import Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Candidate(Base, TimestampMixin):
    """Person-level record. One candidate can apply to many jobs."""

    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30))
    location: Mapped[str | None] = mapped_column(String(120))
    current_company: Mapped[str | None] = mapped_column(String(150))
    current_title: Mapped[str | None] = mapped_column(String(150))
    total_experience: Mapped[float | None] = mapped_column(Numeric(4, 1))
    current_ctc: Mapped[float | None] = mapped_column(Numeric(12, 2))
    expected_ctc: Mapped[float | None] = mapped_column(Numeric(12, 2))
    notice_period_days: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str | None] = mapped_column(String(60))  # referral, naukri, linkedin, careers_site
    referred_by: Mapped[str | None] = mapped_column(String(150))
    skills: Mapped[str | None] = mapped_column(Text)
    linkedin_url: Mapped[str | None] = mapped_column(String(255))
    resume_doc_id: Mapped[str | None] = mapped_column(String(64))  # -> MongoDB resumes._id

    applications = relationship(
        "Application", back_populates="candidate", lazy="selectin", cascade="all, delete-orphan"
    )

    @property
    def skill_list(self) -> list[str]:
        return [s.strip() for s in (self.skills or "").split(",") if s.strip()]

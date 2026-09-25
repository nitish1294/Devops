from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import EmploymentType, JobStatus
from app.models.base import Base, TimestampMixin


class Job(Base, TimestampMixin):
    """A job requisition: the thing candidates are matched against."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(120))
    employment_type: Mapped[str] = mapped_column(
        String(20), default=EmploymentType.FULL_TIME, nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default=JobStatus.DRAFT, nullable=False, index=True)
    openings: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    experience_min: Mapped[int | None] = mapped_column(Integer)
    experience_max: Mapped[int | None] = mapped_column(Integer)
    salary_min: Mapped[float | None] = mapped_column(Numeric(12, 2))
    salary_max: Mapped[float | None] = mapped_column(Numeric(12, 2))
    skills: Mapped[str | None] = mapped_column(Text)  # comma separated, kept simple on purpose
    target_close_date: Mapped[date | None] = mapped_column(Date)

    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"))
    hiring_manager_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    recruiter_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    department = relationship("Department", back_populates="jobs", lazy="joined")
    hiring_manager = relationship("User", foreign_keys=[hiring_manager_id], lazy="joined")
    recruiter = relationship("User", foreign_keys=[recruiter_id], lazy="joined")
    applications = relationship(
        "Application", back_populates="job", lazy="selectin", cascade="all, delete-orphan"
    )

    @property
    def skill_list(self) -> list[str]:
        return [s.strip() for s in (self.skills or "").split(",") if s.strip()]

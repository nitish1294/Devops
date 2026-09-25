from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Department(Base, TimestampMixin):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    location: Mapped[str | None] = mapped_column(String(120))

    members = relationship("User", back_populates="department", lazy="selectin")
    jobs = relationship("Job", back_populates="department", lazy="selectin")

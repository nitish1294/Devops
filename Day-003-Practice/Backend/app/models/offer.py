from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import OfferStatus
from app.models.base import Base, TimestampMixin


class Offer(Base, TimestampMixin):
    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    designation: Mapped[str] = mapped_column(String(150), nullable=False)
    annual_ctc: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    fixed_component: Mapped[float | None] = mapped_column(Numeric(12, 2))
    variable_component: Mapped[float | None] = mapped_column(Numeric(12, 2))
    joining_bonus: Mapped[float | None] = mapped_column(Numeric(12, 2))
    joining_date: Mapped[date | None] = mapped_column(Date)
    valid_till: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default=OfferStatus.DRAFT, nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    application = relationship("Application", back_populates="offers", lazy="joined")
    approved_by = relationship("User", lazy="joined")

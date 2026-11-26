import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)

    reservations: Mapped[list["Reservation"]] = relationship(back_populates="user")


class Credential(Base):
    __tablename__ = "credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)


class Book(Base):
    __tablename__ = "books"
    __table_args__ = (
        CheckConstraint("total_copies >= 0", name="ck_books_total_copies_nonnegative"),
        CheckConstraint("reserved_copies >= 0", name="ck_books_reserved_copies_nonnegative"),
        CheckConstraint("borrowed_copies >= 0", name="ck_books_borrowed_copies_nonnegative"),
        CheckConstraint(
            "reserved_copies + borrowed_copies <= total_copies",
            name="ck_books_allocated_copies_within_stock",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    author: Mapped[str] = mapped_column(String(200), nullable=False)
    legacy_isbn: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    total_copies: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved_copies: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    borrowed_copies: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    reservations: Mapped[list["Reservation"]] = relationship(back_populates="book")

    @property
    def available_copies(self) -> int:
        return self.total_copies - self.reserved_copies - self.borrowed_copies


class ReservationStatus(str, enum.Enum):
    PENDING = "Pending"
    RESERVED = "Reserved"
    REJECTED = "Rejected"
    BORROWED = "Borrowed"
    RETURNED = "Returned"


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), nullable=False, index=True)
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus, native_enum=False, length=20),
        nullable=False,
        default=ReservationStatus.PENDING,
        index=True,
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    user: Mapped[User] = relationship(back_populates="reservations")
    book: Mapped[Book] = relationship(back_populates="reservations")

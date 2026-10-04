"""
Модели базы данных: пользователь, автомобиль, запись на диагностику.

Используется SQLAlchemy 2.0 (Mapped / mapped_column).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""


class User(Base):
    """Клиент бота (привязан к Telegram ID)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    cars: Mapped[list["Car"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    appointments: Mapped[list["Appointment"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Car(Base):
    """Автомобиль клиента + последний расчёт стоимости ТО."""

    __tablename__ = "cars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    brand: Mapped[str] = mapped_column(String(64))
    mileage: Mapped[int] = mapped_column(Integer, default=0)
    regimen: Mapped[str | None] = mapped_column(String(16), nullable=True)
    work_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user: Mapped["User"] = relationship(back_populates="cars")


class Appointment(Base):
    """Заявка на диагностику."""

    __tablename__ = "appointments"

    NEW = "new"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    DONE = "done"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)  # ← новое
    brand: Mapped[str | None] = mapped_column(String(64), nullable=True)
    regimen: Mapped[str | None] = mapped_column(String(16), nullable=True)
    date_label: Mapped[str] = mapped_column(String(32))
    date_iso: Mapped[str] = mapped_column(String(10), index=True)
    time: Mapped[str] = mapped_column(String(8))
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="new")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User | None"] = relationship(back_populates="appointments")

"""
Подключение к SQLite и функции-помощники для работы с данными.

Все функции асинхронные, используют async_sessionmaker.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import DB_URL
from database.models import Appointment, Base, Car, User

engine = create_async_engine(DB_URL, echo=False, future=True)

# expire_on_commit=False — объекты остаются пригодными для чтения после commit
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    """Создаёт таблицы при старте бота."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_or_create_user(tg_id: int, username: str | None, first_name: str | None) -> User:
    """Возвращает пользователя, создавая его при первом обращении."""
    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.tg_id == tg_id))
        user = result.scalar_one_or_none()

        if user is None:
            user = User(tg_id=tg_id, username=username, first_name=first_name)
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

        # Обновляем актуальные данные профиля
        changed = False
        if username and user.username != username:
            user.username = username
            changed = True
        if first_name and user.first_name != first_name:
            user.first_name = first_name
            changed = True
        if changed:
            await session.commit()
            await session.refresh(user)
        return user


async def save_car(
    user_id: int,
    brand: str,
    mileage: int,
    regimen: str | None = None,
    work_price: float | None = None,
) -> Car:
    """Сохраняет/обновляет автомобиль пользователя (уникален по марке)."""
    async with SessionLocal() as session:
        result = await session.execute(
            select(Car).where(Car.user_id == user_id, func.lower(Car.brand) == brand.lower())
        )
        car = result.scalar_one_or_none()

        if car is None:
            car = Car(
                user_id=user_id,
                brand=brand,
                mileage=mileage,
                regimen=regimen,
                work_price=work_price,
            )
            session.add(car)
        else:
            car.mileage = mileage
            if regimen:
                car.regimen = regimen
            car.work_price = work_price

        await session.commit()
        await session.refresh(car)
        return car


async def get_last_car(user_id: int) -> Car | None:
    """Последний рассчитанный автомобиль пользователя (для записи)."""
    async with SessionLocal() as session:
        result = await session.execute(
            select(Car).where(Car.user_id == user_id).order_by(Car.updated_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()


async def is_slot_taken(tg_id: int, date_iso: str, time: str) -> bool:
    """Есть ли у этого пользователя активная заявка на выбранное время."""
    async with SessionLocal() as session:
        result = await session.execute(
            select(func.count())
            .select_from(Appointment)
            .where(
                Appointment.tg_id == tg_id,
                Appointment.date_iso == date_iso,
                Appointment.time == time,
                Appointment.status.in_([Appointment.NEW, Appointment.CONFIRMED]),
            )
        )
        return (result.scalar_one() or 0) > 0


async def create_appointment(
    *,
    user_id: int | None,
    tg_id: int,
    username: str | None,
    brand: str | None,
    regimen: str | None,
    date_label: str,
    date_iso: str,
    time: str,
) -> Appointment:
    """Создаёт запись на диагностику."""
    async with SessionLocal() as session:
        appointment = Appointment(
            user_id=user_id,
            tg_id=tg_id,
            username=username,
            brand=brand,
            regimen=regimen,
            date_label=date_label,
            date_iso=date_iso,
            time=time,
        )
        session.add(appointment)
        await session.commit()
        await session.refresh(appointment)
        return appointment


async def get_user_profile(tg_id: int) -> dict:
    """Данные для экрана «Мой профиль»."""
    async with SessionLocal() as session:
        user = (
            await session.execute(select(User).where(User.tg_id == tg_id))
        ).scalar_one_or_none()

        if user is None:
            return {"exists": False}

        cars = (
            await session.execute(
                select(Car).where(Car.user_id == user.id).order_by(Car.updated_at.desc())
            )
        ).scalars().all()

        bookings = (
            await session.execute(
                select(Appointment)
                .where(Appointment.user_id == user.id)
                .order_by(Appointment.created_at.desc())
            )
        ).scalars().all()

        return {
            "exists": True,
            "user": user,
            "cars": list(cars),
            "bookings": list(bookings),
            "active_bookings": [
                b for b in bookings if b.status in (Appointment.NEW, Appointment.CONFIRMED)
            ],
        }

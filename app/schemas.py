from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import ReservationStatus


class UserCreate(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr


class UserRead(UserCreate):
    model_config = ConfigDict(from_attributes=True)


class RegisterCreate(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class LoginCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class BookCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    author: str = Field(min_length=1, max_length=200)
    phone_number: str = Field(
        min_length=8,
        max_length=20,
        pattern=r"^\+?[0-9][0-9\s().-]{6,18}[0-9]$",
    )
    total_copies: int = Field(ge=0)


class BookUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    author: str | None = Field(default=None, min_length=1, max_length=200)
    phone_number: str | None = Field(
        default=None,
        min_length=8,
        max_length=20,
        pattern=r"^\+?[0-9][0-9\s().-]{6,18}[0-9]$",
    )
    total_copies: int | None = Field(default=None, ge=0)


class BookRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    author: str
    phone_number: str | None
    total_copies: int
    reserved_copies: int
    borrowed_copies: int
    available_copies: int


class ReservationCreate(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    book_id: int = Field(gt=0)


class ReservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    book_id: int
    status: ReservationStatus
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Callable

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import SessionLocal, create_tables
from app.auth import hash_password, verify_password
from app.models import Book, Credential, Reservation, ReservationStatus, User, utc_now
from app.queue import QueueUnavailable, publish_reservation
from app.schemas import (
    BookCreate,
    BookRead,
    BookUpdate,
    LoginCreate,
    RegisterCreate,
    ReservationCreate,
    ReservationRead,
    UserCreate,
    UserRead,
)


def get_db():
    with SessionLocal() as db:
        yield db


def create_app(
    reservation_publisher: Callable[[str], None] = publish_reservation,
    initialize_database: bool = True,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if initialize_database:
            create_tables()
        yield

    app = FastAPI(
        title="Library Reservation API",
        description="Tra cứu sách và gửi yêu cầu đặt mượn được xử lý qua RabbitMQ.",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.state.reservation_publisher = reservation_publisher
    DbSession = Annotated[Session, Depends(get_db)]

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/auth/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
    def register(payload: RegisterCreate, db: DbSession):
        existing = db.scalar(select(User).where(User.email == str(payload.email)))
        if existing is not None or db.get(User, payload.id) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email hoặc mã người dùng đã tồn tại",
            )
        user = User(id=payload.id, name=payload.name, email=str(payload.email))
        db.add(user)
        db.flush()
        db.add(
            Credential(
                user_id=user.id,
                password_hash=hash_password(payload.password),
            )
        )
        db.commit()
        db.refresh(user)
        return user

    @app.post("/auth/login", response_model=UserRead)
    def login(payload: LoginCreate, db: DbSession):
        user = db.scalar(select(User).where(User.email == str(payload.email)))
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email hoặc mật khẩu không đúng")
        credential = db.scalar(select(Credential).where(Credential.user_id == user.id))
        if credential is None or not verify_password(payload.password, credential.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email hoặc mật khẩu không đúng")
        return user

    @app.get("/dashboard")
    def dashboard(db: DbSession):
        books = db.scalars(select(Book)).all()
        reservations = db.scalars(select(Reservation)).all()
        total_copies = sum(book.total_copies for book in books)
        available_copies = sum(book.available_copies for book in books)
        status_counts = {
            status_name.value: sum(
                reservation.status == status_name for reservation in reservations
            )
            for status_name in ReservationStatus
        }
        return {
            "title_count": len(books),
            "total_copies": total_copies,
            "available_copies": available_copies,
            "reservation_count": len(reservations),
            "status_counts": status_counts,
        }

    @app.get("/users/{user_id}", response_model=UserRead)
    def get_user(user_id: str, db: DbSession):
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user

    @app.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
    def create_user(payload: UserCreate, db: DbSession):
        user = User(id=payload.id, name=payload.name, email=str(payload.email))
        db.add(user)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User ID or email already exists",
            ) from exc
        db.refresh(user)
        return user

    @app.post("/books", response_model=BookRead, status_code=status.HTTP_201_CREATED)
    def create_book(payload: BookCreate, db: DbSession):
        book = Book(**payload.model_dump())
        db.add(book)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Book data conflicts with an existing record") from exc
        db.refresh(book)
        return book

    @app.patch("/books/{book_id}", response_model=BookRead)
    def update_book(book_id: int, payload: BookUpdate, db: DbSession):
        book = db.get(Book, book_id)
        if book is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
        changes = payload.model_dump(exclude_unset=True)
        if any(value is None for value in changes.values()):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Book fields cannot be null")
        allocated_copies = book.reserved_copies + book.borrowed_copies
        if "total_copies" in changes and changes["total_copies"] < allocated_copies:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Total copies cannot be lower than {allocated_copies} copies currently in use",
            )
        for field, value in changes.items():
            setattr(book, field, value)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Book data conflicts with an existing record") from exc
        db.refresh(book)
        return book

    @app.delete("/books/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_book(book_id: int, db: DbSession):
        book = db.get(Book, book_id)
        if book is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
        has_reservations = db.scalar(
            select(Reservation.id).where(Reservation.book_id == book_id).limit(1)
        )
        if has_reservations is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Books with reservation history cannot be deleted",
            )
        db.delete(book)
        db.commit()

    @app.get("/books", response_model=list[BookRead])
    def list_books(
        db: DbSession,
        q: str | None = Query(default=None, min_length=1, max_length=200),
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ):
        query = select(Book).order_by(Book.id).offset(offset).limit(limit)
        if q:
            pattern = f"%{q}%"
            query = query.where(
                Book.title.ilike(pattern)
                | Book.author.ilike(pattern)
                | Book.phone_number.ilike(pattern)
            )
        return db.scalars(query).all()

    @app.get("/books/{book_id}", response_model=BookRead)
    def get_book(book_id: int, db: DbSession):
        book = db.get(Book, book_id)
        if book is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
        return book

    @app.post(
        "/reservations",
        response_model=ReservationRead,
        status_code=status.HTTP_202_ACCEPTED,
    )
    def create_reservation(payload: ReservationCreate, db: DbSession):
        if db.get(User, payload.user_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        if db.get(Book, payload.book_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

        reservation = Reservation(
            user_id=payload.user_id,
            book_id=payload.book_id,
            status=ReservationStatus.PENDING,
        )
        db.add(reservation)
        db.commit()
        db.refresh(reservation)
        try:
            app.state.reservation_publisher(reservation.id)
        except QueueUnavailable as exc:
            reservation.status = ReservationStatus.REJECTED
            reservation.rejection_reason = "Reservation queue is unavailable"
            reservation.updated_at = utc_now()
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"message": str(exc), "reservation_id": reservation.id},
            ) from exc
        return reservation

    @app.get("/reservations/{reservation_id}", response_model=ReservationRead)
    def get_reservation(reservation_id: str, db: DbSession):
        reservation = db.get(Reservation, reservation_id)
        if reservation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found"
            )
        return reservation

    @app.get(
        "/users/{user_id}/reservations", response_model=list[ReservationRead]
    )
    def list_user_reservations(
        user_id: str,
        db: DbSession,
        reservation_status: ReservationStatus | None = Query(default=None, alias="status"),
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ):
        if db.get(User, user_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        query = (
            select(Reservation)
            .where(Reservation.user_id == user_id)
            .order_by(Reservation.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        if reservation_status is not None:
            query = query.where(Reservation.status == reservation_status)
        return db.scalars(query).all()

    @app.post("/reservations/{reservation_id}/borrow", response_model=ReservationRead)
    def borrow_reservation(reservation_id: str, db: DbSession):
        reservation = db.scalar(
            select(Reservation)
            .where(Reservation.id == reservation_id)
            .with_for_update()
        )
        if reservation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found"
            )
        if reservation.status != ReservationStatus.RESERVED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only reserved books can be borrowed",
            )
        book = db.scalar(select(Book).where(Book.id == reservation.book_id).with_for_update())
        book.reserved_copies -= 1
        book.borrowed_copies += 1
        reservation.status = ReservationStatus.BORROWED
        reservation.updated_at = utc_now()
        db.commit()
        db.refresh(reservation)
        return reservation

    @app.post("/reservations/{reservation_id}/return", response_model=ReservationRead)
    def return_reservation(reservation_id: str, db: DbSession):
        reservation = db.scalar(
            select(Reservation)
            .where(Reservation.id == reservation_id)
            .with_for_update()
        )
        if reservation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found"
            )
        if reservation.status != ReservationStatus.BORROWED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only borrowed books can be returned",
            )
        book = db.scalar(select(Book).where(Book.id == reservation.book_id).with_for_update())
        book.borrowed_copies -= 1
        reservation.status = ReservationStatus.RETURNED
        reservation.updated_at = utc_now()
        db.commit()
        db.refresh(reservation)
        return reservation

    static_dir = Path(__file__).resolve().parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

        @app.get("/", include_in_schema=False)
        def frontend():
            return FileResponse(static_dir / "index.html")

    return app


app = create_app()

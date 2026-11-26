from sqlalchemy import select

from app.database import SessionLocal, create_tables
from app.auth import hash_password
from app.models import Book, Credential, User


def seed() -> None:
    create_tables()
    with SessionLocal.begin() as db:
        if db.get(User, "user-001") is None:
            db.add(
                User(
                    id="user-001",
                    name="Nguyen Van An",
                    email="an@example.com",
                )
            )
        if db.get(Credential, 1) is None:
            existing = db.scalar(select(Credential).where(Credential.user_id == "user-001"))
            if existing is None:
                db.flush()
                db.add(
                    Credential(
                        user_id="user-001",
                        password_hash=hash_password("123456"),
                    )
                )
        if db.scalar(select(Book).where(Book.legacy_isbn == "9780132350884")) is None:
            db.add(
                Book(
                    title="Clean Code",
                    author="Robert C. Martin",
                    legacy_isbn="9780132350884",
                    phone_number=None,
                    total_copies=3,
                    reserved_copies=0,
                    borrowed_copies=0,
                )
            )


if __name__ == "__main__":
    seed()

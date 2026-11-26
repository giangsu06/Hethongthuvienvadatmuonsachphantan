from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import DATABASE_URL


class Base(DeclarativeBase):
    pass


engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)
    migrate_book_phone_fields(engine)


def migrate_book_phone_fields(bind) -> None:
    with bind.begin() as connection:
        inspector = inspect(connection)
        if "books" not in inspector.get_table_names():
            return
        columns = {column["name"] for column in inspector.get_columns("books")}
        if "isbn" in columns and "legacy_isbn" not in columns:
            connection.execute(text("ALTER TABLE books RENAME COLUMN isbn TO legacy_isbn"))
            columns.remove("isbn")
            columns.add("legacy_isbn")
            if bind.dialect.name == "postgresql":
                connection.execute(text("ALTER TABLE books ALTER COLUMN legacy_isbn DROP NOT NULL"))
        if "phone_number" not in columns:
            connection.execute(text("ALTER TABLE books ADD COLUMN phone_number VARCHAR(20)"))

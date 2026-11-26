from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, migrate_book_phone_fields
from app.main import create_app, get_db


def make_client(publisher=lambda _: None):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    app = create_app(
        reservation_publisher=publisher,
        initialize_database=False,
    )

    def override_get_db():
        with TestingSession() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), engine


def test_reservation_lifecycle_updates_available_copies():
    client, engine = make_client()
    try:
        user = client.post(
            "/users",
            json={"id": "u1", "name": "Reader", "email": "reader@example.com"},
        )
        book = client.post(
            "/books",
            json={
                "title": "Distributed Systems",
                "author": "A. Author",
                "phone_number": "09012345670",
                "total_copies": 1,
            },
        )
        assert user.status_code == 201
        assert book.status_code == 201

        response = client.post(
            "/reservations", json={"user_id": "u1", "book_id": book.json()["id"]}
        )
        assert response.status_code == 202
        reservation_id = response.json()["id"]
        assert response.json()["status"] == "Pending"

        from app.models import Reservation, ReservationStatus
        from app.worker import process_reservation

        process_reservation(
            reservation_id,
            sessionmaker(bind=engine, autoflush=False, expire_on_commit=False),
        )
        reserved = client.get(f"/reservations/{reservation_id}")
        assert reserved.json()["status"] == "Reserved"
        assert client.get(f"/books/{book.json()['id']}").json()["available_copies"] == 0

        borrowed = client.post(f"/reservations/{reservation_id}/borrow")
        assert borrowed.json()["status"] == "Borrowed"
        assert client.get(f"/books/{book.json()['id']}").json()["available_copies"] == 0

        returned = client.post(f"/reservations/{reservation_id}/return")
        assert returned.json()["status"] == "Returned"
        assert client.get(f"/books/{book.json()['id']}").json()["available_copies"] == 1

        db = sessionmaker(bind=engine)()
        assert db.get(Reservation, reservation_id).status == ReservationStatus.RETURNED
        db.close()
    finally:
        engine.dispose()


def test_legacy_isbn_is_preserved_when_migrating_to_phone_number():
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE books (id INTEGER PRIMARY KEY, isbn VARCHAR(20) NOT NULL UNIQUE)"
            )
            connection.exec_driver_sql(
                "INSERT INTO books (id, isbn) VALUES (1, '9780132350884')"
            )

        migrate_book_phone_fields(engine)

        with engine.connect() as connection:
            columns = {column[1] for column in connection.exec_driver_sql("PRAGMA table_info(books)")}
            row = connection.exec_driver_sql(
                "SELECT legacy_isbn, phone_number FROM books WHERE id = 1"
            ).one()
        assert "isbn" not in columns
        assert {"legacy_isbn", "phone_number"} <= columns
        assert row == ("9780132350884", None)
    finally:
        engine.dispose()


def test_book_phone_number_must_look_like_a_phone_number():
    client, engine = make_client()
    try:
        response = client.post(
            "/books",
            json={
                "title": "Bad phone",
                "author": "A. Author",
                "phone_number": "call me",
                "total_copies": 1,
            },
        )
        assert response.status_code == 422
    finally:
        engine.dispose()


def test_worker_rejects_reservation_when_no_copies_are_available():
    client, engine = make_client()
    try:
        client.post("/users", json={"id": "u1", "name": "One", "email": "one@example.com"})
        book = client.post(
            "/books",
            json={
                "title": "Limited",
                "author": "A. Author",
                "phone_number": "09012345671",
                "total_copies": 0,
            },
        ).json()
        reservation = client.post(
            "/reservations", json={"user_id": "u1", "book_id": book["id"]}
        ).json()

        from app.worker import process_reservation

        process_reservation(
            reservation["id"],
            sessionmaker(bind=engine, autoflush=False, expire_on_commit=False),
        )
        result = client.get(f"/reservations/{reservation['id']}").json()
        assert result["status"] == "Rejected"
        assert result["rejection_reason"] == "No copies are currently available"
    finally:
        engine.dispose()


def test_queue_failure_returns_503_and_does_not_leave_pending_reservation():
    from app.queue import QueueUnavailable

    def fail_to_publish(_):
        raise QueueUnavailable("RabbitMQ unavailable")

    client, engine = make_client(publisher=fail_to_publish)
    try:
        client.post("/users", json={"id": "u1", "name": "One", "email": "one@example.com"})
        book = client.post(
            "/books",
            json={
                "title": "Queued",
                "author": "A. Author",
                "phone_number": "09012345672",
                "total_copies": 1,
            },
        ).json()

        response = client.post(
            "/reservations", json={"user_id": "u1", "book_id": book["id"]}
        )
        assert response.status_code == 503
        reservation_id = response.json()["detail"]["reservation_id"]
        assert client.get(f"/reservations/{reservation_id}").json()["status"] == "Rejected"
    finally:
        engine.dispose()


def test_register_and_login():
    client, engine = make_client()
    try:
        registered = client.post(
            "/auth/register",
            json={
                "id": "u-auth",
                "name": "Auth Reader",
                "email": "auth@example.com",
                "password": "secret123",
            },
        )
        assert registered.status_code == 201

        wrong_password = client.post(
            "/auth/login",
            json={"email": "auth@example.com", "password": "wrong123"},
        )
        assert wrong_password.status_code == 401

        logged_in = client.post(
            "/auth/login",
            json={"email": "auth@example.com", "password": "secret123"},
        )
        assert logged_in.status_code == 200
        assert logged_in.json()["id"] == "u-auth"
    finally:
        engine.dispose()


def test_book_management_preserves_inventory_and_history():
    client, engine = make_client()
    try:
        book = client.post(
            "/books",
            json={
                "title": "Original title",
                "author": "A. Author",
                "phone_number": "09012345673",
                "total_copies": 2,
            },
        ).json()

        updated = client.patch(
            f"/books/{book['id']}",
            json={"title": "Updated title", "total_copies": 1},
        )
        assert updated.status_code == 200
        assert updated.json()["title"] == "Updated title"
        assert updated.json()["total_copies"] == 1

        deleted = client.delete(f"/books/{book['id']}")
        assert deleted.status_code == 204
        assert client.get(f"/books/{book['id']}").status_code == 404
    finally:
        engine.dispose()


def test_book_stock_cannot_be_reduced_below_allocated_copies():
    client, engine = make_client()
    try:
        client.post("/users", json={"id": "u-stock", "name": "Reader", "email": "stock@example.com"})
        book = client.post(
            "/books",
            json={
                "title": "Stock control",
                "author": "A. Author",
                "phone_number": "09012345674",
                "total_copies": 1,
            },
        ).json()
        reservation = client.post(
            "/reservations", json={"user_id": "u-stock", "book_id": book["id"]}
        ).json()

        from app.worker import process_reservation

        process_reservation(
            reservation["id"],
            sessionmaker(bind=engine, autoflush=False, expire_on_commit=False),
        )
        response = client.patch(f"/books/{book['id']}", json={"total_copies": 0})
        assert response.status_code == 409
        assert client.delete(f"/books/{book['id']}").status_code == 409
    finally:
        engine.dispose()

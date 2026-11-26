import json
import logging
import time
import uuid

import pika
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import AMQP_URL, RESERVATION_QUEUE
from app.database import SessionLocal, create_tables
from app.models import Book, Reservation, ReservationStatus, utc_now


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("reservation-worker")


def process_reservation(
    reservation_id: str,
    session_factory: sessionmaker[Session] = SessionLocal,
) -> None:
    with session_factory.begin() as db:
        reservation = db.scalar(
            select(Reservation)
            .where(Reservation.id == reservation_id)
            .with_for_update()
        )
        if reservation is None:
            logger.warning("Reservation %s no longer exists", reservation_id)
            return
        if reservation.status != ReservationStatus.PENDING:
            logger.info(
                "Skipping reservation %s with status %s",
                reservation_id,
                reservation.status.value,
            )
            return

        book = db.scalar(select(Book).where(Book.id == reservation.book_id).with_for_update())
        if book is None:
            reservation.status = ReservationStatus.REJECTED
            reservation.rejection_reason = "Book no longer exists"
        elif book.available_copies <= 0:
            reservation.status = ReservationStatus.REJECTED
            reservation.rejection_reason = "No copies are currently available"
        else:
            book.reserved_copies += 1
            reservation.status = ReservationStatus.RESERVED
            reservation.rejection_reason = None
        reservation.updated_at = utc_now()

    logger.info("Processed reservation %s", reservation_id)


def _handle_message(channel, method, properties, body: bytes) -> None:
    try:
        message = json.loads(body)
        reservation_id = str(uuid.UUID(message["reservation_id"]))
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        logger.exception("Discarding malformed reservation message")
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        return

    try:
        process_reservation(reservation_id)
    except Exception:
        logger.exception("Failed to process reservation %s; requeuing", reservation_id)
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        return
    channel.basic_ack(delivery_tag=method.delivery_tag)


def run_worker() -> None:
    create_tables()
    while True:
        connection = None
        try:
            connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
            channel = connection.channel()
            channel.queue_declare(queue=RESERVATION_QUEUE, durable=True)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=RESERVATION_QUEUE, on_message_callback=_handle_message)
            logger.info("Listening on queue %s", RESERVATION_QUEUE)
            channel.start_consuming()
        except (pika.exceptions.AMQPError, OSError):
            logger.exception("RabbitMQ connection failed; retrying in 5 seconds")
            time.sleep(5)
        finally:
            if connection is not None and connection.is_open:
                connection.close()


if __name__ == "__main__":
    run_worker()

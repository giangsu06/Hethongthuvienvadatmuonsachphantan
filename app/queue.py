import json

import pika

from app.config import AMQP_URL, RESERVATION_QUEUE


class QueueUnavailable(Exception):
    pass


def publish_reservation(reservation_id: str) -> None:
    try:
        connection = pika.BlockingConnection(
            pika.URLParameters(AMQP_URL)
        )
        channel = connection.channel()
        channel.queue_declare(queue=RESERVATION_QUEUE, durable=True)
        channel.confirm_delivery()
        channel.basic_publish(
            exchange="",
            routing_key=RESERVATION_QUEUE,
            body=json.dumps({"reservation_id": reservation_id}),
            properties=pika.BasicProperties(
                delivery_mode=pika.DeliveryMode.Persistent,
                content_type="application/json",
            ),
            mandatory=True,
        )
        connection.close()
    except pika.exceptions.AMQPError as exc:
        raise QueueUnavailable("RabbitMQ could not accept the reservation request") from exc

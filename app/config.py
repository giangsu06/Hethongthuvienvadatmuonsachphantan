import os


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://library:library@localhost:5432/library",
)
AMQP_URL = os.getenv("AMQP_URL", "amqp://guest:guest@localhost:5672/%2F")
RESERVATION_QUEUE = os.getenv("RESERVATION_QUEUE", "reservation_requests")

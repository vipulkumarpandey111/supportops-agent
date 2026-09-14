import os

import pika

QUEUE_NAME = "tickets"


def get_connection_and_channel():
    credentials = pika.PlainCredentials(
        os.environ["RABBITMQ_USER"], os.environ["RABBITMQ_PASSWORD"]
    )
    params = pika.ConnectionParameters(
        host=os.environ["RABBITMQ_HOST"],
        port=int(os.environ["RABBITMQ_PORT"]),
        credentials=credentials,
    )
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    # durable=True: the queue survives a RabbitMQ restart.
    channel.queue_declare(queue=QUEUE_NAME, durable=True)
    return connection, channel


def publish_ticket(ticket_id: str) -> None:
    """Publish just the ticket_id — the worker fetches full ticket data from
    MongoDB. Keeps Mongo as the single source of truth and the queue message
    tiny."""
    connection, channel = get_connection_and_channel()
    channel.basic_publish(
        exchange="",
        routing_key=QUEUE_NAME,
        body=ticket_id,
        properties=pika.BasicProperties(delivery_mode=2),  # persistent message
    )
    connection.close()

import dataclasses

from app.orchestration.graph import resolve_ticket
from app.queue import QUEUE_NAME, get_connection_and_channel
from app.storage import get_ticket, update_ticket


def process_message(channel, method, properties, body):
    ticket_id = body.decode()
    ticket = get_ticket(ticket_id)

    if ticket is None:
        # Message refers to a ticket we have no record of — nothing to do.
        channel.basic_ack(delivery_tag=method.delivery_tag)
        return

    if ticket["status"] in ("processing", "resolved"):
        # Idempotency: RabbitMQ's at-least-once delivery can redeliver a
        # message (e.g. after a worker crash before ack). Skip work already
        # done or already in flight rather than reprocessing.
        channel.basic_ack(delivery_tag=method.delivery_tag)
        return

    update_ticket(ticket_id, status="processing")

    try:
        result = resolve_ticket(ticket["ticket_text"])

        resolver_result = result.get("resolver_result")
        responder_reply = result.get("responder_reply")

        if resolver_result is not None and resolver_result.requires_human_approval:
            status = "pending_human_approval"
        else:
            status = "resolved"

        update_ticket(
            ticket_id,
            status=status,
            classification=result["classification"].model_dump(mode="json"),
            chunks_used=[dataclasses.asdict(c) for c in result["chunks"]],
            answer=result["answer"].model_dump(mode="json"),
            retry_count=result["retry_count"],
            resolver_result=resolver_result.model_dump(mode="json")
            if resolver_result
            else None,
            final_reply=responder_reply.reply_text if responder_reply else None,
        )
        print(f"[worker] {status}: ticket {ticket_id}", flush=True)
    except Exception as exc:
        update_ticket(ticket_id, status="failed", error=str(exc))
        print(f"[worker] ticket {ticket_id} failed: {exc}", flush=True)

    channel.basic_ack(delivery_tag=method.delivery_tag)


def main():
    connection, channel = get_connection_and_channel()
    channel.basic_qos(prefetch_count=1)  # one ticket at a time per worker
    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=process_message)
    print("[worker] waiting for tickets...", flush=True)
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
        connection.close()


if __name__ == "__main__":
    main()

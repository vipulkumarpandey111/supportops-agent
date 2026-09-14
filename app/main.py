import os
import uuid

import pika
import psycopg2
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from app.queue import publish_ticket
from app.storage import get_ticket, save_new_ticket

load_dotenv()

app = FastAPI(title="SupportOps Agent")


def check_postgres() -> bool:
    conn = psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.environ["POSTGRES_PORT"],
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=3,
    )
    conn.close()
    return True


def check_mongo() -> bool:
    client = MongoClient(
        host=os.environ["MONGO_HOST"],
        port=int(os.environ["MONGO_PORT"]),
        username=os.environ["MONGO_USER"],
        password=os.environ["MONGO_PASSWORD"],
        serverSelectionTimeoutMS=3000,
    )
    try:
        client.admin.command("ping")
    except PyMongoError:
        return False
    finally:
        client.close()
    return True


def check_rabbitmq() -> bool:
    credentials = pika.PlainCredentials(
        os.environ["RABBITMQ_USER"], os.environ["RABBITMQ_PASSWORD"]
    )
    params = pika.ConnectionParameters(
        host=os.environ["RABBITMQ_HOST"],
        port=int(os.environ["RABBITMQ_PORT"]),
        credentials=credentials,
        connection_attempts=1,
        socket_timeout=3,
    )
    connection = pika.BlockingConnection(params)
    connection.close()
    return True


@app.get("/health")
def health():
    checks = {}
    for name, check in (
        ("postgres", check_postgres),
        ("mongo", check_mongo),
        ("rabbitmq", check_rabbitmq),
    ):
        try:
            checks[name] = "ok" if check() else "unreachable"
        except Exception as exc:
            checks[name] = f"error: {exc}"
    status = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": status, "checks": checks}


class TicketCreate(BaseModel):
    ticket_text: str


@app.post("/tickets", status_code=202)
def create_ticket(payload: TicketCreate):
    """Accepts a ticket and returns immediately — resolution happens
    asynchronously via the worker consuming from RabbitMQ. Poll
    GET /tickets/{ticket_id} for the result."""
    ticket_id = str(uuid.uuid4())
    save_new_ticket(ticket_id, payload.ticket_text)
    publish_ticket(ticket_id)
    return {"ticket_id": ticket_id, "status": "pending"}


@app.get("/tickets/{ticket_id}")
def read_ticket(ticket_id: str):
    ticket = get_ticket(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    return ticket

import os

import pika
import psycopg2
from dotenv import load_dotenv
from fastapi import FastAPI
from pymongo import MongoClient
from pymongo.errors import PyMongoError

load_dotenv()

app = FastAPI(title="SecDevAgent")


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

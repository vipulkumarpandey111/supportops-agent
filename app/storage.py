import os
from datetime import datetime, timezone

from pymongo import MongoClient

_COLLECTION_NAME = "tickets"


def get_collection():
    client = MongoClient(
        host=os.environ["MONGO_HOST"],
        port=int(os.environ["MONGO_PORT"]),
        username=os.environ["MONGO_USER"],
        password=os.environ["MONGO_PASSWORD"],
    )
    db = client[os.environ["MONGO_DB"]]
    return db[_COLLECTION_NAME]


def save_new_ticket(ticket_id: str, ticket_text: str) -> None:
    now = datetime.now(timezone.utc)
    get_collection().insert_one(
        {
            "_id": ticket_id,
            "ticket_text": ticket_text,
            "status": "pending",
            "created_at": now,
            "updated_at": now,
            "classification": None,
            "chunks_used": None,
            "answer": None,
            "retry_count": None,
            "resolver_result": None,
            "final_reply": None,
            "error": None,
        }
    )


def get_ticket(ticket_id: str) -> dict:
    return get_collection().find_one({"_id": ticket_id})


def update_ticket(ticket_id: str, status: str, **fields) -> None:
    fields["status"] = status
    fields["updated_at"] = datetime.now(timezone.utc)
    get_collection().update_one({"_id": ticket_id}, {"$set": fields})

import glob
import os
import re

import psycopg2
from dotenv import load_dotenv
from pgvector.psycopg2 import register_vector

from app.rag.embeddings import embed

load_dotenv()

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "docs")

EMBEDDING_DIM = 768


def get_connection():
    conn = psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.environ["POSTGRES_PORT"],
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )
    return conn


def ensure_schema(conn):
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    conn.commit()
    register_vector(conn)  # must run after the extension exists

    with conn.cursor() as cur:
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS ticket_docs (
                id SERIAL PRIMARY KEY,
                source_file TEXT NOT NULL,
                category TEXT NOT NULL,
                heading TEXT NOT NULL,
                content TEXT NOT NULL,
                embedding VECTOR({EMBEDDING_DIM}) NOT NULL
            );
        """)
    conn.commit()


def chunk_markdown(text: str) -> list[tuple[str, str]]:
    """Split a markdown doc into (heading, content) chunks on '##' headings.

    A cheap form of semantic chunking: each chunk is one self-contained
    policy point, rather than an arbitrary character count.
    """
    sections = re.split(r"^## ", text, flags=re.MULTILINE)[1:]
    chunks = []
    for section in sections:
        heading, _, body = section.partition("\n")
        chunks.append((heading.strip(), body.strip()))
    return chunks


def ingest():
    conn = get_connection()
    ensure_schema(conn)

    with conn.cursor() as cur:
        cur.execute("DELETE FROM ticket_docs;")  # idempotent re-ingestion

        doc_paths = sorted(glob.glob(os.path.join(DOCS_DIR, "*.md")))
        total_chunks = 0
        for path in doc_paths:
            category = os.path.splitext(os.path.basename(path))[0]
            with open(path) as f:
                text = f.read()

            for heading, content in chunk_markdown(text):
                vector = embed(f"{heading}\n{content}")
                cur.execute(
                    """
                    INSERT INTO ticket_docs (source_file, category, heading, content, embedding)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (os.path.basename(path), category, heading, content, vector),
                )
                total_chunks += 1

    conn.commit()
    conn.close()
    print(f"Ingested {total_chunks} chunks from {len(doc_paths)} docs.")


if __name__ == "__main__":
    ingest()

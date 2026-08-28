from dataclasses import dataclass
from typing import Optional

from app.rag.embeddings import embed
from app.rag.ingest import get_connection

try:
    from pgvector.psycopg2 import register_vector
except ImportError:  # pragma: no cover
    register_vector = None


@dataclass
class RetrievedChunk:
    source_file: str
    category: str
    heading: str
    content: str
    distance: float  # cosine distance: lower = more similar


def retrieve(query: str, top_k: int = 3, category: Optional[str] = None) -> list[RetrievedChunk]:
    """Embed the query and return the top-k closest doc chunks.

    `category` narrows the search to one doc category BEFORE ranking by
    similarity (e.g. the Classifier's output) — this is metadata filtering,
    see RAG.md section 2.5.
    """
    query_vector = embed(query)

    conn = get_connection()
    register_vector(conn)
    with conn.cursor() as cur:
        if category:
            cur.execute(
                """
                SELECT source_file, category, heading, content, embedding <=> %s::vector AS distance
                FROM ticket_docs
                WHERE category = %s
                ORDER BY distance ASC
                LIMIT %s
                """,
                (query_vector, category, top_k),
            )
        else:
            cur.execute(
                """
                SELECT source_file, category, heading, content, embedding <=> %s::vector AS distance
                FROM ticket_docs
                ORDER BY distance ASC
                LIMIT %s
                """,
                (query_vector, top_k),
            )
        rows = cur.fetchall()
    conn.close()

    return [
        RetrievedChunk(source_file=r[0], category=r[1], heading=r[2], content=r[3], distance=r[4])
        for r in rows
    ]

from typing import Optional

from pydantic import BaseModel, Field

from app.llm_client import generate
from app.rag.retriever import retrieve


class GroundedAnswer(BaseModel):
    answer: str
    sufficient_context: bool = Field(
        description="False if the retrieved context did not actually contain "
        "enough information to answer confidently"
    )


ANSWER_PROMPT = """You are a Cloudnest support assistant. Answer the customer's
question using ONLY the policy context below. If the context does not contain
enough information to answer, set sufficient_context to false and say so in
the answer rather than guessing.

Context:
{context}

Customer question:
{question}
"""


def answer_with_context(question: str, category: Optional[str] = None, top_k: int = 3) -> GroundedAnswer:
    chunks = retrieve(question, top_k=top_k, category=category)
    context = "\n\n".join(f"[{c.heading}] {c.content}" for c in chunks)
    prompt = ANSWER_PROMPT.format(context=context, question=question)
    return generate(prompt, GroundedAnswer)

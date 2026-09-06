from typing import List, Optional, TypedDict

from langgraph.graph import END, StateGraph

from app.agents.classifier import TicketClassification, classify_ticket
from app.llm_client import generate
from app.rag.answer import ANSWER_PROMPT, GroundedAnswer
from app.rag.retriever import RetrievedChunk, retrieve

MAX_RETRIES = 1


class TicketState(TypedDict):
    ticket_text: str
    classification: Optional[TicketClassification]
    chunks: Optional[List[RetrievedChunk]]
    answer: Optional[GroundedAnswer]
    retry_count: int


def classify_node(state: TicketState) -> dict:
    classification = classify_ticket(state["ticket_text"])
    return {"classification": classification}


def retrieve_node(state: TicketState) -> dict:
    is_retry = state.get("answer") is not None
    category = None if is_retry else state["classification"].category.value
    top_k = 5 if is_retry else 3

    chunks = retrieve(state["ticket_text"], top_k=top_k, category=category)
    update = {"chunks": chunks}
    if is_retry:
        update["retry_count"] = state["retry_count"] + 1
    return update


def generate_node(state: TicketState) -> dict:
    context = "\n\n".join(f"[{c.heading}] {c.content}" for c in state["chunks"])
    prompt = ANSWER_PROMPT.format(context=context, question=state["ticket_text"])
    answer = generate(prompt, GroundedAnswer)
    return {"answer": answer}


def route_after_generate(state: TicketState) -> str:
    if state["answer"].sufficient_context:
        return "end"
    if state["retry_count"] >= MAX_RETRIES:
        return "end"
    return "retry"


def build_graph():
    graph = StateGraph(TicketState)
    graph.add_node("classify", classify_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("generate", generate_node)

    graph.set_entry_point("classify")
    graph.add_edge("classify", "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_conditional_edges(
        "generate", route_after_generate, {"retry": "retrieve", "end": END}
    )

    return graph.compile()


def resolve_ticket(ticket_text: str) -> TicketState:
    app = build_graph()
    initial_state: TicketState = {
        "ticket_text": ticket_text,
        "classification": None,
        "chunks": None,
        "answer": None,
        "retry_count": 0,
    }
    return app.invoke(initial_state)

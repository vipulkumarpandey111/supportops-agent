from enum import Enum

from pydantic import BaseModel, Field

from app.llm_client import generate


class Category(str, Enum):
    billing = "billing"
    technical_issue = "technical_issue"
    account_access = "account_access"
    feature_request = "feature_request"
    complaint = "complaint"
    other = "other"


class Sentiment(str, Enum):
    positive = "positive"
    neutral = "neutral"
    negative = "negative"


class TicketClassification(BaseModel):
    category: Category
    urgency: int = Field(ge=1, le=5, description="1 = low urgency, 5 = critical")
    sentiment: Sentiment
    intent: str = Field(description="One short sentence: what the customer wants done")


CLASSIFIER_PROMPT = """You are a support ticket triage assistant.
Read the customer ticket below and classify it.

Ticket:
\"\"\"
{ticket_text}
\"\"\"
"""


def classify_ticket(ticket_text: str) -> TicketClassification:
    prompt = CLASSIFIER_PROMPT.format(ticket_text=ticket_text)
    return generate(prompt, TicketClassification)

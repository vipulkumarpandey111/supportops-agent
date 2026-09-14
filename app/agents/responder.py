from pydantic import BaseModel

from app.agents.resolver import ResolverResult
from app.llm_client import generate


class ResponderReply(BaseModel):
    reply_text: str


RESPOND_PROMPT = """You are drafting the final customer-facing reply for a
Cloudnest support ticket. Use a friendly, concise tone.

Original ticket:
\"\"\"
{ticket_text}
\"\"\"

Action outcome:
{outcome}

If requires_human_approval is true, tell the customer their refund is being
reviewed by a specialist rather than confirming it's done. If the order
wasn't found, apologize and ask them to double-check the order ID. If no
action was taken, just answer using the earlier grounded answer context
provided below.

Grounded answer context (fallback if no action was needed):
{fallback_answer}
"""


def draft_reply(ticket_text: str, resolver_result: ResolverResult, fallback_answer: str) -> ResponderReply:
    prompt = RESPOND_PROMPT.format(
        ticket_text=ticket_text,
        outcome=resolver_result.model_dump_json(),
        fallback_answer=fallback_answer,
    )
    return generate(prompt, ResponderReply)

from pydantic import BaseModel, Field

from app.llm_client import generate

JUDGE_MODEL = "qwen2.5:7b"  # same local model as generation — a known limitation,
# see EVALUATION.md section 4 (self-preference bias) and ROADMAP.md Phase 11.


class JudgeVerdict(BaseModel):
    faithful: bool = Field(
        description="True only if every claim in the reply is supported by the "
        "provided context — no invented facts, even plausible-sounding ones."
    )
    correct: bool = Field(
        description="True if the reply appropriately handles the scenario, "
        "judged against the stated expected behavior."
    )
    reasoning: str = Field(description="Brief explanation for both verdicts.")


JUDGE_PROMPT = """You are grading a customer support agent's reply. Be strict —
if the reply contains a claim not supported by the context, faithful must be false,
even if the claim happens to sound reasonable.

Customer ticket:
\"\"\"
{ticket_text}
\"\"\"

Context the agent had available:
\"\"\"
{context}
\"\"\"

Agent's reply:
\"\"\"
{reply}
\"\"\"

Expected behavior for this scenario:
\"\"\"
{expected_behavior}
\"\"\"

Grade the reply for faithfulness (grounded in the context, no fabrication) and
correctness (matches the expected behavior).
"""


def judge_response(
    ticket_text: str, context: str, reply: str, expected_behavior: str
) -> JudgeVerdict:
    prompt = JUDGE_PROMPT.format(
        ticket_text=ticket_text,
        context=context or "(no context was retrieved)",
        reply=reply,
        expected_behavior=expected_behavior,
    )
    return generate(prompt, JudgeVerdict, model=JUDGE_MODEL)

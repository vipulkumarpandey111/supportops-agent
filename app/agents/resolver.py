from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.llm_client import generate
from app.tools.orders import get_order, initiate_refund


class ResolverActionType(str, Enum):
    initiate_refund = "initiate_refund"
    check_order_status = "check_order_status"
    no_action = "no_action"


class ResolverPlan(BaseModel):
    action: ResolverActionType
    order_id: Optional[str] = Field(
        description="The order ID mentioned in the ticket, if any (e.g. 'ORD-1001')"
    )
    refund_amount: Optional[float] = Field(
        description="Amount to refund, if action is initiate_refund. Use the "
        "order's actual charged amount if the customer wants a full refund."
    )
    reasoning: str


PLAN_PROMPT = """You are a support agent's action-planning assistant. Given a
customer ticket and the applicable policy context, decide what action to
take. Extract the order ID from the ticket text if one is mentioned
(format: ORD-####). If no order ID is present, use action "no_action".

Policy context:
{context}

Customer ticket:
\"\"\"
{ticket_text}
\"\"\"
"""


def plan_action(ticket_text: str, context: str) -> ResolverPlan:
    prompt = PLAN_PROMPT.format(context=context, ticket_text=ticket_text)
    return generate(prompt, ResolverPlan)


class ResolverResult(BaseModel):
    action_taken: str
    order_found: bool
    requires_human_approval: bool = False
    details: dict = Field(default_factory=dict)


def execute_plan(plan: ResolverPlan) -> ResolverResult:
    """Deterministic execution — the LLM only proposed the plan; this
    function is what actually touches the database and enforces the
    approval threshold."""
    if plan.action == ResolverActionType.no_action or plan.order_id is None:
        return ResolverResult(action_taken="no_action", order_found=False)

    order = get_order(plan.order_id)
    if order is None:
        return ResolverResult(
            action_taken="order_not_found",
            order_found=False,
            details={"order_id": plan.order_id},
        )

    if plan.action == ResolverActionType.check_order_status:
        return ResolverResult(
            action_taken="check_order_status", order_found=True, details=order
        )

    if plan.action == ResolverActionType.initiate_refund:
        amount = plan.refund_amount or order["amount"]
        result = initiate_refund(plan.order_id, amount)
        return ResolverResult(
            action_taken="initiate_refund",
            order_found=True,
            requires_human_approval=result["requires_human_approval"],
            details={**order, **result},
        )

    return ResolverResult(action_taken="no_action", order_found=False)

import dataclasses
from typing import Optional


@dataclasses.dataclass
class TestCase:
    id: str
    ticket_text: str
    expected_category: Optional[str]
    expected_behavior: str
    expect_no_matching_docs: bool = False


TEST_CASES = [
    TestCase(
        id="billing_small_refund_auto",
        ticket_text="I was double charged for order ORD-1001, please refund the extra 15 dollars.",
        expected_category="billing",
        expected_behavior=(
            "This is a duplicate charge under $50 (ORD-1001, $15). It should be "
            "auto-refunded and the reply should confirm the refund is being processed, "
            "not ask for further review."
        ),
    ),
    TestCase(
        id="billing_large_refund_escalate",
        ticket_text="Please refund my order ORD-1002, I was charged twice.",
        expected_category="billing",
        expected_behavior=(
            "This is a refund of $75, which is at/above the $50 auto-approve threshold. "
            "The reply should tell the customer it's under review by a specialist, "
            "NOT confirm the refund is done."
        ),
    ),
    TestCase(
        id="billing_missing_order",
        ticket_text="Please refund my order ORD-4242, I was charged twice.",
        expected_category="billing",
        expected_behavior=(
            "ORD-4242 does not exist in the system. The reply should apologize and "
            "ask the customer to double-check the order ID, not claim a refund was issued."
        ),
    ),
    TestCase(
        id="account_access_lockout",
        ticket_text="I cannot log into my account, it keeps saying invalid password even "
        "after I reset it three times.",
        expected_category="account_access",
        expected_behavior=(
            "Should explain the likely cause (cached session on another device) and "
            "the fix (wait 15 minutes, log out other devices) based on policy."
        ),
    ),
    TestCase(
        id="technical_upload_stuck",
        ticket_text="My file upload has been stuck at 0% for the last 10 minutes.",
        expected_category="technical_issue",
        expected_behavior=(
            "Should suggest the known cause (firewall/proxy blocking the upload "
            "endpoint) and recommend trying a different network to confirm."
        ),
    ),
    TestCase(
        id="feature_request_dark_mode",
        ticket_text="Can you add dark mode to the mobile app?",
        expected_category="feature_request",
        expected_behavior=(
            "Should acknowledge the request and explain it's logged with the product "
            "team with no committed timeline, without promising a release date."
        ),
    ),
    TestCase(
        id="out_of_corpus_salesforce",
        ticket_text="Does Cloudnest support integration with Salesforce?",
        expected_category="feature_request",
        expected_behavior=(
            "Cloudnest's docs say nothing about Salesforce integration. The reply "
            "should honestly say this isn't something it can confirm, not invent an answer."
        ),
    ),
    TestCase(
        id="complaint_no_matching_docs",
        ticket_text="I'm furious — this is the third time this has happened and nobody "
        "on your team has helped me at all!",
        expected_category="complaint",
        expected_behavior=(
            "This ticket is a vague complaint with no specific actionable detail and no "
            "matching policy doc for its category. The reply should acknowledge the "
            "frustration without fabricating a specific resolution."
        ),
        expect_no_matching_docs=True,
    ),
]

from app.evaluation.judge import judge_response
from app.evaluation.test_cases import TEST_CASES, TestCase
from app.orchestration.graph import TicketState, resolve_ticket


def check_retrieval(tc: TestCase, final_state: TicketState) -> bool:
    """Deterministic — no LLM involved. See EVALUATION.md section 2."""
    chunks = final_state["chunks"] or []
    if tc.expect_no_matching_docs:
        # Confirms the system actually noticed the gap and retried with a
        # broadened search, rather than silently returning nothing useful.
        return final_state["retry_count"] >= 1
    return any(c.category == tc.expected_category for c in chunks)


def get_final_reply(final_state: TicketState) -> str:
    if final_state.get("responder_reply"):
        return final_state["responder_reply"].reply_text
    return final_state["answer"].answer


def run_evaluation():
    results = []
    for tc in TEST_CASES:
        final_state = resolve_ticket(tc.ticket_text)
        retrieval_ok = check_retrieval(tc, final_state)
        reply = get_final_reply(final_state)
        context = "\n\n".join(f"[{c.heading}] {c.content}" for c in final_state["chunks"])

        verdict = judge_response(tc.ticket_text, context, reply, tc.expected_behavior)

        results.append(
            {
                "id": tc.id,
                "actual_category": final_state["classification"].category.value,
                "expected_category": tc.expected_category,
                "retrieval_ok": retrieval_ok,
                "faithful": verdict.faithful,
                "correct": verdict.correct,
                "reasoning": verdict.reasoning,
                "reply": reply,
            }
        )
    return results


def print_report(results):
    total = len(results)
    retrieval_pass = sum(r["retrieval_ok"] for r in results)
    faithful_pass = sum(r["faithful"] for r in results)
    correct_pass = sum(r["correct"] for r in results)

    print(f"\n=== Evaluation report ({total} cases) ===")
    print(f"Retrieval OK: {retrieval_pass}/{total}")
    print(f"Faithful:     {faithful_pass}/{total}")
    print(f"Correct:      {correct_pass}/{total}")
    print()

    for r in results:
        passed = r["retrieval_ok"] and r["faithful"] and r["correct"]
        flag = "PASS" if passed else "FAIL"
        cat_note = (
            "" if r["actual_category"] == r["expected_category"]
            else f" (classified as {r['actual_category']}, expected {r['expected_category']})"
        )
        print(f"[{flag}] {r['id']}{cat_note}")
        print(
            f"       retrieval={r['retrieval_ok']} faithful={r['faithful']} "
            f"correct={r['correct']}"
        )
        if not passed:
            print(f"       judge reasoning: {r['reasoning']}")
            print(f"       reply: {r['reply']}")
        print()


if __name__ == "__main__":
    results = run_evaluation()
    print_report(results)

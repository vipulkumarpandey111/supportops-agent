# Evaluation — Testing a Non-Deterministic System

A from-first-principles reference for Phase 7, in the same style as
[RAG.md](RAG.md) and [LANGGRAPH.md](LANGGRAPH.md).

---

## 1. Why ordinary unit tests don't work here

A normal backend function is deterministic: `add(2, 3)` always returns `5`,
so `assert add(2, 3) == 5` is a valid, permanent test. An LLM call is not
deterministic in the same sense — ask `classify_ticket()` the same question
twice and you may get slightly different wording, and even the structured
fields (`urgency`, `sentiment`) can shift by one point between runs at
nonzero temperature.

This means `assert answer == "exact expected string"` is the wrong tool.
What you actually want to know is closer to: *"is this answer good?"* —
which is a judgment call, not an equality check. That's the entire reason
LLM-as-judge evaluation exists: you use a second LLM call to make that
judgment call programmatically, instead of a human reading every output by
hand forever.

## 2. Two separate things get evaluated, not one

It's a common mistake to only check "did the final answer sound right" and
stop there. A RAG-based agentic pipeline can fail at two independent
stages, and conflating them hides which one actually broke:

- **Retrieval quality**: did we fetch the right supporting context at all?
  This is measurable *without* an LLM — it's a deterministic check ("was a
  chunk from the expected category/doc in the top-k results?").
- **Generation quality**: given whatever context was retrieved (right or
  wrong), did the model produce a faithful, correct response? This needs
  judgment, because "faithful" isn't a string-match property.

A system can have perfect retrieval and still fail at generation (model
ignores good context and hallucinates anyway), or perfect generation logic
undone by bad retrieval (correctly summarizes the *wrong* policy). Scoring
only the end-to-end result can't distinguish these — you need both numbers.

## 3. What "faithfulness" and "correctness" actually mean

- **Faithfulness**: does every claim in the answer trace back to something
  actually present in the retrieved context? An answer can be faithful and
  still wrong (if the retrieved context itself was wrong), and an answer
  can be plausible-sounding and unfaithful (the model added a detail that
  simply isn't in the context — the textbook hallucination).
- **Correctness**: given the full scenario (ticket + what should have
  happened), did the system do/say the right thing? This is the more
  holistic check — for Phase 6 in particular, "correct" includes things
  like *did it actually escalate a $75 refund instead of auto-approving
  it*, not just "does the reply read nicely."

These are different questions. A judge should be asked about each
separately, not folded into one vague "is this good? yes/no."

## 4. LLM-as-judge: the pattern, and its real risks

The mechanism is simple: give a (usually more careful, structured) prompt
to an LLM containing the input, the context used, and the output produced,
and ask it to return a structured verdict — using the exact same
`instructor`-based pattern as every other agent in this project. The judge
call is architecturally no different from the Classifier or Resolver; it's
just pointed at *evaluating* instead of *producing*.

Real risks worth knowing, not just as trivia but because they'll bite you:

- **Self-preference bias**: using the *same* model as both generator and
  judge tends to inflate scores — a model is statistically more likely to
  rate its own style/phrasing favorably. Using a stronger or at least
  *different* model as judge is standard practice at scale (flagged
  properly for Phase 11 — we use the same local model for both here, which
  is a known, accepted limitation at this scale).
- **Judge prompt sensitivity**: a vaguely-worded judge prompt ("is this
  good?") produces inconsistent, low-signal verdicts. A judge prompt needs
  the same rigor as any other agent prompt — explicit criteria, not vibes.
- **Grading the wrong thing**: it's easy to accidentally build a judge that
  rewards confident-sounding answers over correct ones. This is exactly why
  faithfulness and correctness are asked as separate structured fields
  instead of one free-text "review."

## 4.5. A real example from this project, not a hypothetical

The risks in section 4 aren't theoretical — the first real evaluation run
of this pipeline hit one directly. Two billing test cases had replies that,
read manually, were both textbook-correct (one confirmed an auto-refund,
one correctly deferred a large refund for human review). The judge marked
both `correct=False` anyway, and its own stated reasoning for the second
case directly contradicted the reply it was given — it effectively said
"this reply says X, but it should have said X" and called that a failure.

The takeaway: `qwen2.5:7b` is capable enough to *generate* a good reply
here, but not reliably capable enough to *reason about* the correctness of
a reply when the judgment involves a negation ("should defer, not
confirm"). This is precisely why production judge setups usually use a
stronger or different model than the generator — and precisely why a
human still has to read a sample of judged results before trusting the
automated pass/fail numbers, even after the automation exists.

## 5. Why Ragas/DeepEval exist, and why this project builds a minimal judge instead

**Ragas** and **DeepEval** are the market-standard frameworks for this —
they provide pre-built metrics (faithfulness, answer relevancy, context
precision/recall), batch evaluation runners, and reporting. They're the
right choice for a real production eval suite.

Both default to calling a *hosted* model (typically OpenAI) as the judge.
Pointing them at a fully local model requires wrapping your own LLM client
to satisfy their internal interfaces — doable, but it's framework-fighting
for a benefit that doesn't matter yet at this project's scale, and it would
mean adopting a tool without understanding what it does internally.

This project builds a small custom judge instead, using the exact same
`llm_client.generate()` + Pydantic schema pattern used everywhere else in
this codebase — see [app/evaluation/judge.py](app/evaluation/judge.py). The
concepts (faithfulness, correctness, retrieval-vs-generation separation)
are identical to what Ragas/DeepEval compute; only the implementation is
homegrown. Swapping in a real framework later, once running against a
hosted or larger local judge model matters, is a Phase 11 scale-up item —
see [ROADMAP.md](ROADMAP.md).

## 6. How this maps to this project, concretely

| Concept | Where it lives in this repo |
|---|---|
| Hand-labeled test cases | [app/evaluation/test_cases.py](app/evaluation/test_cases.py) |
| Retrieval quality check (deterministic) | [app/evaluation/evaluate.py](app/evaluation/evaluate.py) — `check_retrieval()` |
| LLM-as-judge (faithfulness + correctness) | [app/evaluation/judge.py](app/evaluation/judge.py) |
| Evaluation runner + report | [app/evaluation/evaluate.py](app/evaluation/evaluate.py) — `run_evaluation()` |
| Deferred: swap in Ragas/DeepEval, different judge model | [ROADMAP.md](ROADMAP.md) Phase 11 |

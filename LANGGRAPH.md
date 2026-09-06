# LangGraph — Stateful Agent Orchestration

A from-first-principles reference for Phase 4, in the same style as
[RAG.md](RAG.md) — concepts tied directly to real files in this repo.

---

## 1. What problem LangGraph solves

Phases 2 and 3 built real logic (`classify_ticket`, `retrieve`,
`answer_with_context`), but we only ever *chained function calls manually*
in a script:

```python
classification = classify_ticket(ticket)
result = answer_with_context(ticket, category=classification.category.value)
```

This works, but it's a straight line — one direction, no memory of what
happened, no way to react to a bad outcome except crashing or returning a
bad answer. Real agent behavior needs:
- **State that persists and accumulates** across multiple steps (not just
  passed as function arguments one call at a time).
- **Branching** — different next-steps depending on what happened so far
  (e.g. "if the answer wasn't grounded enough, do something different").
- **Loops with an explicit exit condition** — retry, but not forever.

LangGraph is a library for building exactly this: a **directed graph of
nodes**, where each node is a function that reads and updates a shared
**state** object, and **edges** (including conditional ones) decide which
node runs next.

## 2. Core concepts

### 2.1 State schema

A single data structure that flows through the entire graph, that every
node can read from and write to. Unlike passing arguments between plain
function calls, the state *accumulates* — later nodes can see what earlier
nodes produced.

**In this project**: `TicketState` in `app/orchestration/graph.py` —
`ticket_text`, `classification`, `chunks`, `answer`, `retry_count`.

### 2.2 Nodes

A node is just a function: `(state) -> partial state update`. Each node in
our graph is a thin wrapper around code we *already wrote and tested in
isolation* in earlier phases — LangGraph doesn't replace that logic, it
orchestrates when each piece runs.

**In this project**: `classify_node` wraps `classify_ticket()` (Phase 2),
`retrieve_node` wraps `retrieve()` (Phase 3), `generate_node` wraps the
grounded-answer prompt + `llm_client.generate()` (Phase 1 + 3).

### 2.3 Edges

A plain edge (`A → B`) always goes from A to B. Nothing to decide.

### 2.4 Conditional edges — the actual "agentic" part

A conditional edge attaches a **router function** to a node: after that
node runs, the router inspects the current state and returns the *name* of
whichever node should run next. This is what turns a fixed pipeline into a
system that reacts to its own output.

**In this project**: after `generate_node` runs, `route_after_generate(state)`
checks `state["answer"].sufficient_context` (the exact field we built in
Phase 3 to catch when retrieval failed) and returns either `"retry"` or
`"end"`.

### 2.5 Loops need an explicit exit condition

A loop-back edge without a bound will spin forever on a genuinely
unanswerable question — the model will keep saying "not enough context,"
and the graph will keep retrying identically forever, burning inference
calls with no path to termination.

**In this project**: `route_after_generate` returns `"end"` if
`retry_count` has already reached `MAX_RETRIES`, regardless of whether the
answer was sufficient — the graph always terminates, even when it fails.
This is the single most important correctness property of any looping
agent, and it's easy to forget when you're focused on the happy path.

### 2.6 Making a retry actually different from the first attempt

Retrying with the *identical* query against the *identical* filtered search
will just fail identically again. A retry needs to change something about
the strategy, not just repeat it.

**In this project**: `retrieve_node` checks whether an `answer` already
exists in state (i.e. this is a second pass) — if so, it drops the category
filter and increases `top_k`, casting a wider net instead of repeating the
same narrow search that already failed. This is a simple version of what
"agentic RAG" (RAG.md §3) calls query reformulation.

## 3. What this project's graph looks like

```
START → classify → retrieve → generate ─┬─→ sufficient_context=True → END
             ▲                            │
             │                            │ sufficient_context=False
             └──────── retry ─────────────┘   AND retry_count < MAX_RETRIES
              (broadened retrieve)
                                          sufficient_context=False
                                          AND retry_count >= MAX_RETRIES
                                                     │
                                                     ▼
                                                    END
                                          (answer honestly says "don't know")
```

Note `classify` only ever runs once — a ticket's category doesn't change
between retries, only *how* we search for supporting context does.

## 4. Where this deliberately stays simple (see ROADMAP.md Phase 11)

- **In-memory state only** — if the process crashes mid-graph, the run is
  lost. Production agent systems checkpoint state (e.g. to a database)
  after every node so a run can resume rather than restart. Not needed at
  our single-user, synchronous scale yet.
- **One retry strategy** (broaden the filter) — a more sophisticated agent
  might have the LLM itself rewrite the query in natural language before
  retrying, rather than a fixed heuristic. Deferred as unnecessary
  complexity for a corpus this small.
- **Single-threaded, synchronous execution** — no parallel node execution,
  no distributed graph state. Fine for one ticket at a time; a real
  concurrent-tenant system needs more (Phase 11).

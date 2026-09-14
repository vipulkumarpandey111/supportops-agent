# Learning Log

A running record of what was built, why, and what concept it was meant to
teach — updated after every step. See [ROADMAP.md](ROADMAP.md) for the
phase plan and current checklist status.

---

## Phase 0 — Local skeleton

**What was done:**
- Wrote [docker-compose.yml](docker-compose.yml) defining three containers
  (`secdevagent-postgres` with the `pgvector` extension, `secdevagent-mongo`,
  `secdevagent-rabbitmq`), each on non-default ports and with fresh
  project-only credentials.
- Wrote [.env](.env) and [.gitignore](.gitignore) so config is project-local
  and never committed.
- Wrote [requirements.txt](requirements.txt) and created a project-local
  Python virtualenv (`.venv/`).
- Wrote [app/main.py](app/main.py): a FastAPI app with a `/health` endpoint
  that connects to all three services and reports status.
- Ran `docker compose up -d`, started uvicorn, and verified
  `GET /health` returns `{"status": "ok", ...}` for all three.

**Why:**
- Proves the plumbing works before any AI logic is added — cheapest possible
  point to catch infra mistakes.
- Establishes the isolation guarantees from [INSTRUCTIONS.md](INSTRUCTIONS.md)
  from the very first commit: dedicated containers, non-default ports, no
  reused credentials.

**Concepts covered:**
- `pgvector` as a Postgres extension (vs. a separate vector DB) — why it's
  attractive for someone already using Postgres.
- Docker Compose networking and named volumes.
- Why a `/health` endpoint matters once you have multiple stateful
  dependencies a request can silently fail against.

---

## Phase 1 — LLM access layer

**What was done:**
- Installed **Ollama** via Homebrew (global tool — asked permission first,
  per [INSTRUCTIONS.md](INSTRUCTIONS.md)).
- Pulled the `qwen2.5:7b` model (4.7GB of weights).
- Started `ollama serve` in the background (a local HTTP API on
  `localhost:11434`, not a persistent login service — must be restarted
  manually after a reboot).
- Wrote [app/llm_client.py](app/llm_client.py): a single `generate(prompt,
  response_model)` function built on `instructor` + an OpenAI-compatible
  client pointed at the local Ollama server (dummy API key, no data leaves
  the machine).
- Hit and fixed a real dependency conflict: `openai==1.51.0` broke against
  `httpx==0.28.1` (`proxies` kwarg removed) — pinned `httpx==0.27.2`.
- Verified end-to-end: `generate("...", Sentiment)` returned a validated
  `Sentiment(label='Negative', confidence=0.95)` Pydantic object.

**Why:**
- Ollama gives local, free, private inference — no API key, no per-token
  cost, nothing leaves the machine. Fits the isolation requirement and is
  the right tool for *dev*, distinct from `vLLM` which is the right tool for
  *production throughput* (deferred to the optional Phase 9).
- The `llm_client` abstraction means every future agent calls one function
  instead of the LLM API directly — swapping the backend later (e.g. to a
  cloud endpoint) means changing this one file, not every agent.
- Raw LLM output is just text; agents need strict typed data that FastAPI/
  Postgres can safely consume. `instructor` forces schema conformance and
  auto-retries (feeding the validation error back to the model) instead of
  us hand-writing JSON-parsing/retry logic per agent.

**Concepts covered:**
- Local model serving vs. hosted APIs — cost/privacy/latency tradeoffs.
- Why LLM output needs structural enforcement (Pydantic + `instructor`)
  rather than being trusted as-is.
- OpenAI-compatible APIs as a portability layer — why many local/self-hosted
  tools mimic OpenAI's request format instead of inventing their own.
- Diagnosing and pinning a transitive dependency conflict — a routine
  occurrence in this fast-moving ecosystem, not a design flaw.

---

## Phase 2 — Structured outputs + first agent ("Classifier")

**What was done:**
- Wrote [app/agents/classifier.py](app/agents/classifier.py): a
  `classify_ticket(text)` function that calls `llm_client.generate()` with a
  `TicketClassification` Pydantic schema (`category` enum, `urgency` int
  1-5, `sentiment` enum, `intent` free text).
- Tested against 3 realistic tickets (billing double-charge, casual feature
  request, login failure) — all classified sensibly (correct category,
  urgency scaled to severity, correct sentiment).

**Why:**
- Every later phase depends on trustworthy structured output. Proving this
  in isolation, before wiring into RabbitMQ/LangGraph, means prompt/schema
  problems get caught here, not buried inside a bigger pipeline.
- `category`/`sentiment` as **enums** (not free strings) because downstream
  phases (RAG doc selection in Phase 3, routing to Resolver/Responder in
  Phase 6) need to branch on a closed set of values — free text would make
  that unreliable.
- `urgency` constrained via Pydantic's `Field(ge=1, le=5)` — if the model
  outputs a value outside that range, validation fails and `instructor`
  auto-retries with the error fed back to the model. No hand-written retry
  logic needed.
- `intent` deliberately left as free text — "what does this person actually
  want" doesn't compress well into a fixed category.

**Concepts covered:**
- Using Enums inside a Pydantic schema to constrain LLM output to a closed
  set, vs. free text for open-ended nuance — knowing when to use which.
- Field-level validation constraints (`ge`/`le`) as a cheap correctness net
  on top of schema-shape enforcement.
- Prompt design: giving the model exactly the context it needs (the raw
  ticket text) and nothing else, since the schema itself carries the
  instructions for what to produce.

---

## Phase 3 — RAG

**What was done:**
- Wrote a full conceptual reference, [RAG.md](RAG.md) — chunking, embeddings,
  vector storage, similarity metrics, retrieval, re-ranking, agentic RAG,
  failure modes, and a table mapping every concept to its file in this repo.
- Wrote a fictional product corpus for "Cloudnest" (a cloud storage SaaS) in
  [data/docs/](data/docs/): `billing.md`, `account_access.md`,
  `technical_issue.md`, `feature_request.md` — one file per Classifier
  category, deliberately.
- Pulled `nomic-embed-text` (274MB) via Ollama — a dedicated embedding
  model, separate from the `qwen2.5:7b` chat model.
- Wrote [app/rag/embeddings.py](app/rag/embeddings.py): thin wrapper calling
  Ollama's `/api/embeddings` endpoint.
- Wrote [app/rag/ingest.py](app/rag/ingest.py): chunks each doc by `##`
  heading, embeds each chunk, stores in a new `ticket_docs` table
  (`pgvector` extension, `VECTOR(768)` column) in `secdevagent-postgres`.
  Ingested 16 chunks from 4 docs.
- Wrote [app/rag/retriever.py](app/rag/retriever.py): `retrieve(query,
  top_k, category)` — cosine-similarity search (`<=>` operator), with
  optional metadata filtering by category.
- Wrote [app/rag/answer.py](app/rag/answer.py): wires retrieval into
  `llm_client.generate()` to produce a `GroundedAnswer` — verified it
  correctly grounds an in-corpus billing question in the actual duplicate-
  charge policy, AND correctly flags `sufficient_context=False` instead of
  hallucinating on an out-of-corpus question (Salesforce integration).

**Why:**
- Real data was explicitly ruled out for this personal project — a
  fictional corpus lets us build and prove the entire RAG mechanism without
  any real customer/company data, and per our earlier discussion, swapping
  it for a real corpus later is low-friction since the ingestion pipeline
  is content-agnostic.
- Docs were named to match the Classifier's category enum exactly, so
  Phase 6 (Resolver/Responder) can filter retrieval by the ticket's
  classified category — this is the concrete link between Phase 2 and
  Phase 3 that RAG.md's metadata-filtering section describes.
- The out-of-corpus test matters more than the in-corpus one: proving the
  agent can recognize *insufficient* context and say so, instead of
  confidently fabricating an answer, is the actual point of RAG — grounding
  isn't just "add context," it's "constrain the model to what's true."

**Concepts covered:**
- See [RAG.md](RAG.md) in full — chunking strategy trade-offs, embeddings
  vs. chat models, pgvector + cosine similarity, metadata filtering,
  naive vs. agentic RAG, and common RAG failure modes.
- One implementation-level lesson: pgvector's array→vector cast is
  *implicit* only when a target column type is known (e.g. `INSERT`), not
  inside an operator expression like `<=>` — required an explicit `::vector`
  cast in the retrieval query. A good example of "the type system doesn't
  always infer what you'd expect" debugging.

---

## Phase 4 — Orchestration with LangGraph

**What was done:**
- Wrote [LANGGRAPH.md](LANGGRAPH.md) — state schemas, nodes, edges,
  conditional edges, why loops need explicit exit conditions, and how a
  retry must change strategy rather than repeat itself — each tied to the
  actual node in this repo.
- Wrote [app/orchestration/graph.py](app/orchestration/graph.py): a
  `TicketState` TypedDict, three nodes (`classify_node`, `retrieve_node`,
  `generate_node` — thin wrappers around the already-tested Phase 2/3
  functions, not reimplementations), and a conditional edge
  (`route_after_generate`) routing to `retry` or `end` based on
  `answer.sufficient_context`.
- `retrieve_node` behaves differently on retry: drops the category filter
  and raises `top_k` from 3 to 5, so a retry actually searches differently
  instead of repeating an identical failed query.
- Verified two cases: an in-corpus billing ticket resolved in one pass
  (`retry_count=0`), and an out-of-corpus question about Salesforce
  integration retried once (`retry_count=1`), still found nothing, and
  **stopped and answered honestly** instead of looping forever or
  hallucinating.

**Why:**
- Phases 2/3 only ever chained function calls in a straight line manually.
  Real agent behavior needs state that accumulates across steps, branching
  based on outcomes, and bounded loops — that's what a graph gives us that
  a script doesn't.
- The graph's actual node order (classify → retrieve → generate) deviated
  slightly from the roadmap's original abstract wording ("retrieve →
  classify → decide") — building Phase 2/3 revealed retrieval depends on
  classification's category, so classify has to run first. Worth noting as
  an example of the roadmap being a plan, not a spec — it adjusts once
  real constraints are discovered.
- The retry-loop bound (`MAX_RETRIES`) is the single most important
  correctness property here: an unconditional loop-back on a genuinely
  unanswerable question would retry forever, burning inference calls with
  no path to termination.

**Concepts covered:**
- See [LANGGRAPH.md](LANGGRAPH.md) in full — state graphs, conditional
  edges, why bounded loops matter, and where this deliberately stays simple
  (in-memory-only state, single-threaded execution — flagged for Phase 11).

---

## Phase 5 — Event-driven wiring

**What was done:**
- Wrote [app/storage.py](app/storage.py): MongoDB persistence for tickets
  (`save_new_ticket`, `get_ticket`, `update_ticket`), tracking a
  `status` field (`pending` → `processing` → `resolved`/`failed`).
- Wrote [app/queue.py](app/queue.py): a RabbitMQ publisher (`publish_ticket`)
  using a durable queue and persistent message delivery, so both the queue
  and its messages survive a RabbitMQ restart.
- Wrote [app/worker.py](app/worker.py): a standalone consumer process that
  pulls a ticket_id off the queue, fetches the full ticket from MongoDB,
  runs `resolve_ticket()` (the Phase 4 LangGraph flow), and writes the
  result back — with an idempotency check that skips any ticket already
  `processing` or `resolved`.
- Added `POST /tickets` (returns `202` immediately, doesn't wait for
  resolution) and `GET /tickets/{id}` (poll for status/result) to
  [app/main.py](app/main.py). Renamed the FastAPI app title from the old
  "SecDevAgent" to "SupportOps Agent" — a leftover from before the pivot.
- Verified end-to-end: posted a real ticket via HTTP, polled until
  `resolved`, got back the full classification/retrieval/answer trail.
  Then deliberately republished the same already-resolved ticket_id
  directly onto the queue and confirmed the worker acked it without
  reprocessing (`updated_at` timestamp unchanged).
- Fixed a minor but real issue along the way: Python's stdout is
  block-buffered when not attached to a terminal, so the worker's log
  lines weren't appearing in its log file in real time — added
  `flush=True` to its prints.

**Why:**
- Decouples "receive a ticket" from "resolve a ticket" — the API returns
  instantly instead of making a caller wait several seconds for an LLM
  pipeline (with possible retries) to finish.
- RabbitMQ's default delivery guarantee is *at-least-once*, not
  *exactly-once* — a message can be redelivered (e.g. if a worker crashes
  after processing but before acking). The idempotency check in
  `process_message` is what makes that safe: reprocessing a duplicate is a
  no-op instead of silently re-running (and potentially re-billing/
  re-answering) an already-resolved ticket.
- MongoDB is the single source of truth for ticket state; the queue message
  is deliberately just an ID, not a payload copy — avoids the two ever
  disagreeing about ticket content.

**Concepts covered:**
- Producer/consumer decoupling via a message queue — why it exists, what
  problem it solves that a direct function call can't.
- At-least-once delivery semantics and why idempotency is the
  application's responsibility, not the queue's.
- Durable queues + persistent messages (`durable=True`,
  `delivery_mode=2`) — the difference between a queue existing and a
  message actually surviving a broker restart.
- stdout buffering in non-interactive processes — a small but common gotcha
  when a long-running worker's logs seem to "go missing."

---

## Phase 6 — Multi-agent expansion (Resolver + Responder)

**What was done:**
- Wrote [app/tools/orders.py](app/tools/orders.py): a mock `orders` table in
  Postgres (order_id, customer_email, amount, charge_date, status), seeded
  with 3 fake orders, plus `get_order()`/`initiate_refund()`. The $50
  auto-approve threshold (`AUTO_APPROVE_REFUND_LIMIT`) is a plain Python
  constant checked in code — not something the LLM decides.
- Wrote [app/agents/resolver.py](app/agents/resolver.py): `plan_action()`
  asks the LLM to extract an order ID and proposed action from free-text
  ticket content into a structured `ResolverPlan`. `execute_plan()` is
  separate, deterministic Python that actually calls the DB tools and
  applies the threshold — the LLM never touches the database directly.
- Wrote [app/agents/responder.py](app/agents/responder.py): drafts the
  final customer-facing reply, wording it differently depending on whether
  the action auto-completed or needs human review.
- Extended [app/orchestration/graph.py](app/orchestration/graph.py) with
  `resolve` and `respond` nodes. `route_after_generate` now has a second
  branch: after a sufficiently-grounded answer, billing tickets continue to
  `resolve`; everything else goes straight to `END` as before (no action to
  take on a feature request, say).
- Extended [app/worker.py](app/worker.py)/[app/storage.py](app/storage.py)
  with a new terminal status, `pending_human_approval`, alongside
  `resolved`/`failed`.
- Verified 3 scenarios directly through the graph, then re-verified the
  first two through the real HTTP API + worker end-to-end: a $15 refund
  (auto-resolved, order status flipped to `refunded` in Postgres — checked
  directly, not just the returned value), a $75 refund (correctly landed on
  `pending_human_approval`, order status `refund_pending_approval`), and a
  nonexistent order ID (failed gracefully with an apology, no crash).

**Why:**
- This is the first phase where the system takes actions with real side
  effects instead of only producing text — a materially different risk
  category from everything before it.
- Splitting "LLM proposes a plan" from "code executes and enforces policy"
  is the core safety pattern here: a refund threshold is a hard business
  rule, and hard business rules should never be left to model discretion,
  however well-prompted. The model's job is judgment (what does this ticket
  need); the code's job is enforcement (is this actually allowed to
  proceed automatically).
- The conditional routing in `route_after_generate` (billing → resolve,
  everything else → end) is a second kind of branching beyond Phase 4's
  retry loop — routing on ticket *type*, not just on confidence.

**Concepts covered:**
- Tool-calling with side effects, vs. Phase 3's read-only retrieval.
- Agent handoff — Resolver's structured output becomes Responder's input,
  each agent doing one job rather than one agent doing everything.
- Human-in-the-loop gating as a first-class terminal state, not an
  afterthought bolted onto "resolved."
- Why deterministic business rules belong in code, not prompts — even a
  very well-written prompt is still probabilistic.

---

## Phase 7 — Evaluation

*Not started yet.*

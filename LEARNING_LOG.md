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

*Not started yet.*

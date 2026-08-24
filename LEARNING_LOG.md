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

*Not started yet.*

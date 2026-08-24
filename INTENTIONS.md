# Project Intentions

This captures what I (the user) am trying to do with this project, based on
our conversation so far. Refer back here before making scope decisions.

## Background

- Backend engineer, 4 years of experience.
- Primary stack: Python, Django, FastAPI, PostgreSQL, MongoDB, RabbitMQ.
- Already have hands-on experience loading and running open-source LLMs on
  VMs — not starting from zero on that front.

## Goal

- Transition into Agentic AI, with an eye toward being market-relevant
  (not just personal curiosity/tinkering).
- Learn agentic AI's core components — RAG, vector databases, orchestration
  (LangGraph), local/self-hosted model serving, fine-tuning, evaluation,
  observability, structured outputs/guardrails — through practical use
  rather than isolated tutorials.

## Explicit Learning Preferences

- Rejected: pure-fundamentals-first learning path.
- Rejected: learning each component separately/in isolation before
  integrating them.
- Preferred: a single hands-on capstone project that naturally forces
  integration of all the above components, using my existing backend stack
  as the skeleton (not throwaway toy demos).

## Project Ground Rules (see INSTRUCTIONS.md)

- All project work must stay isolated inside this folder (`Self_Dev/`).
- No reuse of existing local credentials/sessions/config from elsewhere on
  the machine.
- Any new credential, cloud resource, paid service, global install, or
  external data transfer requires explicit permission before proceeding.

## Decision: Capstone Domain

- Original proposal, "SecDevAgent" (security & code-compliance multi-agent
  pipeline), was evaluated and **rejected** in favor of better business/
  portfolio potential: an autonomous **Support Ticket Resolution Agent**.
- Rationale: support automation has a clearer ROI story, a lower trust
  barrier (worst case is a bad draft reply, not an auto-remediated
  production incident), and maps directly to an active hiring category
  (Sierra, Decagon, Intercom Fin-style products) — see [ROADMAP.md](ROADMAP.md)
  for the resulting architecture.
- An "AIOps/Incident Response Copilot" alternative was also considered and
  set aside — bigger potential deal size, but a much higher trust/compliance
  bar to actually sell, and a crowded incumbent field (Datadog, PagerDuty).
- **Niche/vertical is intentionally deferred** — not required until Phase 3
  (RAG corpus) and Phase 6 (mock order/account data) of the roadmap. All
  earlier phases are domain-agnostic.

## Open Questions (not yet answered)

1. Which niche/vertical to build the support agent around (deferred to
   Phase 3/6 of the roadmap — not blocking earlier work).
2. Target timeline / realistic hours-per-week commitment.
3. Whether the end goal is: a job-hunting portfolio piece, work-related
   upskilling, or something intended to be productionized/sold as a real
   business.
4. Whether fine-tuning (which likely needs GPU budget) should be treated as
   a required step or an optional stretch goal.

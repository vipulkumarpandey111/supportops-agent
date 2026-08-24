# Project Instructions & Ground Rules

This file is the source of truth for how work in this folder must be conducted.
Any assistant (or contributor) working here must read and follow this before
taking action.

## Isolation

- All work for this project must stay **contained within this folder**
  (`Self_Dev/`). Do not read from, write to, or reference files, configs, or
  state outside this directory unless explicitly instructed by the user.
- Do not use, reuse, or reference any credentials, API keys, tokens, SSH keys,
  cloud CLI sessions, `.env` files, or auth profiles that already exist
  elsewhere on this machine. Every credential this project needs must be
  created fresh, scoped to this project, and stored only inside this folder
  (e.g. in a local `.env` that is gitignored).
- No implicit reuse of "whatever is already logged in" — e.g. do not assume
  an existing `gcloud`/`aws`/`huggingface-cli`/`docker` login is available for
  use unless the user explicitly approves it for this project.

## Network & Service Isolation (strict)

The local machine already runs org-owned services (RabbitMQ, databases) on
their standard/default hosts and ports, configured with org credentials.
This project must **never** connect to, discover, or share infrastructure
with those.

- Every service this project needs (PostgreSQL, MongoDB, RabbitMQ, etc.) must
  run as a **dedicated container/process spun up by and for this project**
  (e.g. via a project-local `docker-compose.yml`), never by pointing at an
  already-running instance on the machine.
- Use **non-default ports** for every service, chosen specifically to avoid
  colliding with (or accidentally being mistaken for) existing local
  instances — e.g. Postgres on `55432` not `5432`, MongoDB on `27118` not
  `27017`, RabbitMQ on `56720`/`15682` not `5672`/`15672`. Confirm the actual
  ports already in use locally before picking numbers, rather than guessing.
- Connection strings, hostnames, and credentials for this project's services
  must only ever come from this project's own `.env`/compose file — never
  from an org config file, shell profile, or environment variable already
  set on the system. If a generic env var name (e.g. `DATABASE_URL`,
  `RABBITMQ_URL`) is already set globally on this machine, do not rely on
  inheriting it — this project must define and use its own explicitly.
- Before running anything that binds a port or starts a service, check for
  conflicts with what's already running locally, and flag it to the user
  rather than silently reusing or overriding it.

## Version Control Isolation

- This project's git history must be **its own local repository**, isolated
  from any org repository, and must not be added as a remote, submodule, or
  subtree of an existing org repo.
- Do not push this project to any remote (GitHub org, GitLab, etc.) without
  explicit permission — treat this as covered by the Permission Gate below.
- Do not assume the machine's global `git config` (user identity, credential
  helper, SSH keys) is appropriate to use for commits/pushes here if it is
  tied to org identity — confirm with the user first if a commit identity or
  a remote/push is ever needed.

## Permission Gate

Before doing any of the following, **stop and ask the user for explicit
permission first** — do not proceed silently or assume approval:

- Creating any new credential, account, API key, or token (including free-tier
  signups).
- Using any existing credential/session found on the local system.
- Provisioning or connecting to any cloud resource (VM, storage bucket,
  managed DB, GPU instance, etc.) — including anything cloud-hosted for model
  serving or fine-tuning.
- Installing global (non-project-scoped) system packages or tools.
- Any action with cost implications (paid API usage, cloud billing, GPU rental).
- Sending data outside this local environment (external APIs, third-party
  services) — call out what data would leave and where.
- Adding a git remote, pushing this project's repo anywhere, or committing
  using an identity other than one the user confirms is appropriate here.

## Scope Notes

- This project is the "Agentic AI" learning capstone discussed with the user
  (backend engineer, Python/Django/FastAPI/Postgres/MongoDB/RabbitMQ stack),
  intended to be hands-on and self-contained.
- When in doubt about whether something crosses a boundary above, ask rather
  than assume.

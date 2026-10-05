# NenuAIKadu

An Outpero-style AI outbound voice calling platform for Indian businesses. Creates AI voice agents that call leads, converse in Indian regional languages (and code-mixed speech), and drive the conversation end-to-end — from STT to LLM to TTS — over a telephony provider.

Docs: [`docs/`](docs/) · Spec source: `local://paste-1.md`

## Architecture

Modular monolith (FastAPI) with a Next.js web app. Every AI/telephony provider sits behind an interface so providers (Sarvam, Twilio today; OpenAI, Deepgram, ElevenLabs, Exotel later) can be swapped without touching business logic.

```
                 ┌────────────────────┐
                 │    FastAPI API     │
                 │  Agents/Leads/Calls│
                 │  Campaigns/Workers │
                 │  Voice Engine      │
                 │  Integrations      │
                 └─────────┬──────────┘
                   ┌───────┼────────┐
                   ▼       ▼        ▼
               PostgreSQL  Redis  Worker
```

Call pipeline:

```
Customer → Twilio → Sarvam Realtime STT → Conversation Orchestrator → Sarvam LLM → Sarvam Streaming TTS → Customer
```

## Stack

- **Frontend:** Next.js (App Router), React, TypeScript (strict), Tailwind CSS, shadcn/ui, TanStack Query, Zod, React Hook Form, Recharts
- **Backend:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, PostgreSQL + pgvector, Redis, Celery, WebSockets
- **Providers:** Sarvam AI (LLM/STT/TTS), Twilio (telephony)
- **Storage:** S3-compatible object storage (recordings, imports, docs)
- **Deploy:** Docker; frontend → Vercel, backend+worker → Render/Railway, DB → managed Postgres, Redis → managed Redis

## Prerequisites

- Python 3.12+, [`uv`](https://github.com/astral-sh/uv)
- Node.js 20+, `pnpm`
- Docker + Docker Compose
- Sarvam AI API key; Twilio account SID / auth token / phone number

## Quick Start

```bash
cp .env.example .env   # fill in values
make setup             # install backend + frontend deps
make db-up             # start postgres + redis
make db-migrate        # apply Alembic migrations
make dev               # backend + frontend + worker
```

Open http://localhost:3000 (web) and http://localhost:8000/docs (API).

For Twilio webhooks in local dev, point `TWILIO_WEBHOOK_BASE_URL` at an `ngrok` tunnel to port 8000.

## Services / Make targets

| Command | Purpose |
|---|---|
| `make backend` | FastAPI dev server on :8000 |
| `make frontend` | Next.js dev server on :3000 |
| `make worker` | Celery worker |
| `make db-up` / `db-migrate` | Postgres+Redis up, apply migrations |
| `make db-migrate-autogen m="msg"` | Autogen a migration |
| `make test` / `lint` / `typecheck` | Full quality gates |
| `make docker-up` | Full dev stack via Compose |
| `make backup` | pg_dump to scripts/backups |

## Repository layout

```
apps/
  web/     Next.js frontend
  api/     FastAPI backend (app/, tests/)
packages/
  shared/  shared TS types/constants
infra/
  docker/  service Dockerfiles
  nginx/   reverse proxy config
docs/      architecture + setup guides
scripts/   helpers + backups
```

## Current status (phased)

Phase 1 **Foundation** … Phase 9 **Hardening**. See `docs/roadmap.md` for the phase-by-phase breakdown and the exact Definition of Done in the project spec (§59).

## Security notes

- Secrets live only in `.env` (server-side). Never committed.
- API keys never returned to the frontend.
- Recordings are private; access via signed URLs.
- Webhook signature verification (Twilio) is enforced.
- Lead `DO_NOT_CALL` is honored before any call initiation.
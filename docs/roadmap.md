# Roadmap

Phased implementation of the VoiceAI MVP. Each phase ends with a working,
testable vertical slice. Do not move on until the previous phase's Definition of
Done is satisfied.

## Phase 1 — Foundation
- [x] Monorepo structure (`apps/web`, `apps/api`, `packages/shared`, `infra`, `docs`)
- [x] Docker Compose (dev + prod), Dockerfiles, nginx proxy
- [x] `.env.example` / `.env.development`
- [x] FastAPI skeleton: config, DB engine, structured logging, security (JWT + bcrypt)
- [ ] Database models (users, agents, leads, campaigns, calls, ...) + Alembic migrations
- [ ] Auth endpoints (register/login/refresh/logout/me)
- [ ] Next.js skeleton: providers, layout, home page
- [ ] Basic dashboard

## Phase 2 — Agent
- [ ] Agent CRUD + configuration
- [ ] Agent test chat console
- [ ] Sarvam LLM provider (`SarvamLLM`)

## Phase 3 — Voice
- [ ] Sarvam realtime STT provider
- [ ] Sarvam streaming TTS provider
- [ ] Conversation orchestrator
- [ ] Call state machine + barge-in/interruption

## Phase 4 — Telephony
- [ ] `TelephonyProvider` abstraction + `TwilioProvider`
- [ ] Outbound call + webhooks (status/answer/recording)
- [ ] Media streaming (WebSocket)
- [ ] Call SID tracking, duration, failure handling

## Phase 5 — Leads
- [ ] Lead CRUD
- [ ] CSV import + validation (duplicates/invalid)
- [ ] Lead statuses + `DO_NOT_CALL` guard

## Phase 6 — Campaigns
- [ ] Campaign CRUD + state transitions
- [ ] Campaign worker (Celery) with concurrency cap
- [ ] Retry logic (NO_ANSWER/BUSY/TEMPORARY_FAILURE) with backoff

## Phase 7 — Analytics
- [ ] Transcript storage + UI
- [ ] Post-call summary + structured data extraction
- [ ] Call outcomes, dashboards, language/agent analytics

## Phase 8 — Knowledge
- [ ] Knowledge base (documents + chunks)
- [ ] Embeddings + pgvector semantic retrieval (RAG)
- [ ] Agent knowledge selection

## Phase 9 — Hardening
- [ ] Structured logging + metrics across STT/LLM/TTS/telephony
- [ ] Security hardening (rate limiting, webhook sig, secure headers)
- [ ] Retry/backoff + dead-letter handling
- [ ] GitHub Actions CI (ruff, mypy, eslint, tsc, pytest)
- [ ] Tests for critical paths (auth, agents, leads, CSV, state machine, providers)

## Definition of Done (MVP)
See project spec §59. The minimum end-to-end path:
create account → create agent (+regional language, voice) → add lead → create
campaign → start campaign → Twilio calls lead → Sarvam STT → Sarvam LLM →
Sarvam TTS → customer hears AI → conversation + interruption → hang up →
transcript saved → summary generated → lead updated → dashboard updated.

Do not consider the MVP complete until this entire path works.
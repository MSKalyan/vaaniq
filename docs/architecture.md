# Architecture

## Provider abstraction

Every external service sits behind an interface so providers can be replaced without
touching business logic:

| Capability   | Interface            | Initial impl       | Future impls                 |
|--------------|----------------------|--------------------|------------------------------|
| Conversation | `LLMProvider`         | `SarvamLLM`        | OpenAI, Anthropic, Gemini    |
| Speech-to-text| `STTProvider`        | `SarvamRealtimeSTT`| Deepgram, Vosk               |
| Text-to-speech| `TTSProvider`        | `SarvamTTS`        | ElevenLabs, Cartesia         |
| Telephony    | `TelephonyProvider`   | `TwilioProvider`   | Exotel, Plivo, Vonage        |
| Embeddings   | `EmbeddingProvider`   | configurable       | OpenAI, local                |

Interfaces live in `app/integrations/base.py`. Provider packages (`sarvam/`, `twilio/`)
own all provider-specific HTTP/WebSocket code. Business logic never issues provider
API calls directly.

## Call pipeline

```
Customer → Twilio(media stream) → Sarvam Realtime STT (WebSocket)
        → Conversation Orchestrator
        → Sarvam LLM (structured output)
        → Sarvam Streaming TTS
        → Twilio → Customer
```

- STT uses Sarvam **realtime** WebSocket (partial transcripts + server VAD),
  not repeated short-audio uploads.
- TTS is **streaming** so audio starts before synthesis completes.
- Orchestrator owns the call state machine and barge-in handling (stop TTS,
  clear audio, capture customer speech).

## Communication

- **REST** `/api/v1/*` for CRUD and admin.
- **WebSocket** `/api/v1/ws/calls/{call_id}` for realtime audio/event stream.
- **Webhooks** `/api/v1/webhooks/twilio/*` for telephony lifecycle + recording.

## Data

PostgreSQL (primary). Redis for Celery broker/result backend, rate limiting,
temporary call state, WebSocket session state, distributed locks. Knowledge
embeddings in pgvector. Object storage (S3) for recordings/imports/docs.

## Security & compliance

- JWT access+refresh; bcrypt password hashing.
- Secrets server-side only; API keys never returned to the frontend.
- Webhook signature verification (Twilio) enforced.
- Recordings private, signed/private access URLs.
- `DO_NOT_CALL` honored before any call initiation.
- Consent/disclosure configurable per campaign.

## Deployment

Dev via `docker compose up`. Prod: nginx → frontend/backend/worker; managed
Postgres/Redis/S3. Portable to AWS later (frontend→Vercel, backend+worker→ECS,
DB→RDS, Redis→ElastiCache).
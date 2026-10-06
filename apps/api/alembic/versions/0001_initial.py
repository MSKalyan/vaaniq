"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-05

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)

    # --- agents ---
    op.create_table(
        "agents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("language", sa.String(16), nullable=False, server_default="auto"),
        sa.Column("voice", sa.String(64), nullable=True),
        sa.Column("greeting", sa.Text(), nullable=True),
        sa.Column("objectives", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("max_call_duration", sa.Integer(), nullable=False, server_default="600"),
        sa.Column("temperature", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("status", sa.String(16), nullable=False, server_default="DRAFT"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_agents_user_id", "agents", ["user_id"])

    op.create_table(
        "agent_voices",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False, server_default="sarvam"),
        sa.Column("voice_name", sa.String(64), nullable=False),
        sa.Column("language", sa.String(16), nullable=False, server_default="auto"),
        sa.Column(
            "voice_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_agent_voices_voice_name", "agent_voices", ["voice_name"])

    op.create_table(
        "knowledge_bases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_knowledge_bases_user_id", "knowledge_bases", ["user_id"])

    op.create_table(
        "agent_knowledge",
        sa.Column(
            "agent_id", sa.Uuid(), sa.ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column(
            "knowledge_base_id",
            sa.Uuid(),
            sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    # --- leads ---
    op.create_table(
        "leads",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("phone_number", sa.String(20), nullable=False),
        sa.Column("name", sa.String(120), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("language", sa.String(16), nullable=True),
        sa.Column("location", sa.String(120), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="NEW"),
        sa.Column("custom_fields", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_leads_phone_number", "leads", ["phone_number"])
    op.create_index("ix_leads_status", "leads", ["status"])
    op.create_index("ix_leads_user_id", "leads", ["user_id"])

    op.create_table(
        "lead_import_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imported", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("invalid", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(24), nullable=False, server_default="PENDING"),
        sa.Column("errors", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_lead_import_jobs_user_id", "lead_import_jobs", ["user_id"])

    op.create_table(
        "import_errors",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "job_id",
            sa.Uuid(),
            sa.ForeignKey("lead_import_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("raw_data", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )
    op.create_index("ix_import_errors_job_id", "import_errors", ["job_id"])

    # --- campaigns ---
    op.create_table(
        "campaigns",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "agent_id", sa.Uuid(), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="DRAFT"),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_concurrent_calls", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("retry_attempts", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("retry_delay_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_campaigns_user_id", "campaigns", ["user_id"])
    op.create_index("ix_campaigns_agent_id", "campaigns", ["agent_id"])
    op.create_index("ix_campaigns_status", "campaigns", ["status"])

    op.create_table(
        "campaign_leads",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "campaign_id",
            sa.Uuid(),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "lead_id", sa.Uuid(), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("status", sa.String(24), nullable=False, server_default="NEW"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_campaign_leads_campaign_id", "campaign_leads", ["campaign_id"])
    op.create_index("ix_campaign_leads_lead_id", "campaign_leads", ["lead_id"])

    # --- calls ---
    op.create_table(
        "calls",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "campaign_lead_id",
            sa.Uuid(),
            sa.ForeignKey("campaign_leads.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "lead_id", sa.Uuid(), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "agent_id", sa.Uuid(), sa.ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "campaign_id",
            sa.Uuid(),
            sa.ForeignKey("campaigns.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("provider_call_id", sa.String(64), nullable=True),
        sa.Column("state", sa.String(24), nullable=False, server_default="INITIALIZING"),
        sa.Column("outcome", sa.String(24), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="INITIALIZING"),
        sa.Column("direction", sa.String(12), nullable=False, server_default=sa.text("'outbound'")),
        sa.Column("phone_number", sa.String(20), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_calls_user_id", "calls", ["user_id"])
    op.create_index("ix_calls_campaign_lead_id", "calls", ["campaign_lead_id"])
    op.create_index("ix_calls_lead_id", "calls", ["lead_id"])
    op.create_index("ix_calls_agent_id", "calls", ["agent_id"])
    op.create_index("ix_calls_campaign_id", "calls", ["campaign_id"])
    op.create_index("ix_calls_provider_call_id", "calls", ["provider_call_id"])
    op.create_index("ix_calls_state", "calls", ["state"])
    op.create_index("ix_calls_outcome", "calls", ["outcome"])

    op.create_table(
        "call_transcripts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "call_id", sa.Uuid(), sa.ForeignKey("calls.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("speaker", sa.String(12), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("language", sa.String(16), nullable=True),
        sa.Column(
            "timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("sequence_number", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_call_transcripts_call_id", "call_transcripts", ["call_id"])

    op.create_table(
        "call_recordings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "call_id", sa.Uuid(), sa.ForeignKey("calls.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("storage_key", sa.String(512), nullable=True),
        sa.Column("recording_url", sa.Text(), nullable=True),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="PENDING"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_call_recordings_call_id", "call_recordings", ["call_id"])

    op.create_table(
        "call_analysis",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "call_id", sa.Uuid(), sa.ForeignKey("calls.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("sentiment", sa.String(16), nullable=True),
        sa.Column("intent", sa.String(64), nullable=True),
        sa.Column("interest_level", sa.String(16), nullable=True),
        sa.Column("key_points", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column(
            "extracted_data", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")
        ),
        sa.Column("objections", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("next_action", sa.Text(), nullable=True),
        sa.Column(
            "callback_required", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("callback_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hllm_version", sa.String(32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_call_analysis_call_id", "call_analysis", ["call_id"])

    # --- customer memory ---
    op.create_table(
        "customer_memory",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "lead_id", sa.Uuid(), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("preferred_language", sa.String(16), nullable=True),
        sa.Column("budget", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("location", sa.String(120), nullable=True),
        sa.Column("requirements", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("interest_level", sa.String(16), nullable=True),
        sa.Column("preferred_callback_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("previous_call_summary", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_customer_memory_lead_id", "customer_memory", ["lead_id"], unique=True)

    # --- callbacks ---
    op.create_table(
        "callbacks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "lead_id", sa.Uuid(), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "call_id", sa.Uuid(), sa.ForeignKey("calls.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "agent_id", sa.Uuid(), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="SCHEDULED"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_callbacks_lead_id", "callbacks", ["lead_id"])
    op.create_index("ix_callbacks_agent_id", "callbacks", ["agent_id"])

    # --- knowledge ---
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "knowledge_base_id",
            sa.Uuid(),
            sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False, server_default="text"),
        sa.Column("storage_key", sa.String(512), nullable=True),
        sa.Column("doc_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_knowledge_documents_knowledge_base_id", "knowledge_documents", ["knowledge_base_id"]
    )

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column(
            "chunk_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"])
    # HNSW index on the vector column requires an operator class (cosine distance).
    op.execute(
        "CREATE INDEX ix_knowledge_chunks_embedding ON knowledge_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    # --- audit ---
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(32), nullable=True),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_embedding")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")
    op.drop_table("callbacks")
    op.drop_table("customer_memory")
    op.drop_table("call_analysis")
    op.drop_table("call_recordings")
    op.drop_table("call_transcripts")
    op.drop_table("calls")
    op.drop_table("campaign_leads")
    op.drop_table("campaigns")
    op.drop_table("import_errors")
    op.drop_table("lead_import_jobs")
    op.drop_table("leads")
    op.drop_table("agent_knowledge")
    op.drop_table("knowledge_bases")
    op.drop_table("agent_voices")
    op.drop_table("agents")
    op.drop_table("refresh_tokens")
    op.drop_table("users")

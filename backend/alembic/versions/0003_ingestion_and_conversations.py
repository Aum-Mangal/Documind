"""Ingestion queue on documents, chunks with embeddings, conversations.

Existing documents become 'queued', so the worker chunks and embeds them from the
text they already have; nobody needs to upload anything again.

Revision ID: 0003_ingestion_conversations
Revises: 0002_pgvector_and_indexes
Create Date: 2026-11-04
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import HALFVEC
from sqlalchemy.dialects import postgresql

revision = "0003_ingestion_conversations"
down_revision = "0002_pgvector_and_indexes"
branch_labels = None
depends_on = None

EMBEDDING_DIM = 384


def upgrade() -> None:
    # ── documents: original file + processing state ──
    op.add_column("documents", sa.Column("mime_type", sa.String(100)))
    op.add_column("documents", sa.Column("size_bytes", sa.BigInteger()))
    op.add_column("documents", sa.Column("sha256", sa.String(64)))
    op.add_column("documents", sa.Column("storage_key", sa.String(512)))
    op.add_column("documents", sa.Column("page_count", sa.Integer()))
    op.add_column("documents", sa.Column("status", sa.String(16), server_default="queued", nullable=False))
    op.add_column("documents", sa.Column("stage", sa.String(32)))
    op.add_column("documents", sa.Column("progress", sa.Integer(), server_default="0", nullable=False))
    op.add_column("documents", sa.Column("error", sa.Text()))
    op.add_column("documents", sa.Column("attempts", sa.Integer(), server_default="0", nullable=False))
    op.add_column("documents", sa.Column("locked_at", sa.DateTime(timezone=True)))
    op.add_column("documents", sa.Column("run_after", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.add_column("documents", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_check_constraint(
        "documents_status_check", "documents", "status IN ('queued', 'processing', 'ready', 'failed')"
    )
    op.create_index(
        "uq_documents_user_id_sha256", "documents", ["user_id", "sha256"], unique=True,
        postgresql_where=sa.text("sha256 IS NOT NULL"),
    )
    op.create_index("ix_documents_status_run_after", "documents", ["status", "run_after"])

    # ── chunks ───────────────────────────────────────
    op.create_table(
        "chunks",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ord", sa.Integer(), nullable=False),
        sa.Column("page_start", sa.Integer()),
        sa.Column("page_end", sa.Integer()),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("embedding", HALFVEC(EMBEDDING_DIM), nullable=False),
        sa.Column("tsv", postgresql.TSVECTOR(), sa.Computed("to_tsvector('english', content)", persisted=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="chunks_pkey"),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    op.create_index("ix_chunks_user_id_document_id", "chunks", ["user_id", "document_id"])
    op.create_index("ix_chunks_tsv", "chunks", ["tsv"], postgresql_using="gin")
    op.create_index(
        "ix_chunks_embedding_hnsw", "chunks", ["embedding"], postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "halfvec_cosine_ops"},
    )

    # ── conversations ────────────────────────────────
    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("document_ids", postgresql.ARRAY(sa.Integer())),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="conversations_pkey"),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sources", postgresql.JSONB()),
        sa.Column("abstained", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="messages_role_check"),
        sa.PrimaryKeyConstraint("id", name="messages_pkey"),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])


def downgrade() -> None:
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("chunks")
    op.drop_index("ix_documents_status_run_after", table_name="documents")
    op.drop_index("uq_documents_user_id_sha256", table_name="documents")
    op.drop_constraint("documents_status_check", "documents", type_="check")
    for column in ("updated_at", "run_after", "locked_at", "attempts", "error", "progress", "stage",
                   "status", "page_count", "storage_key", "sha256", "size_bytes", "mime_type"):
        op.drop_column("documents", column)

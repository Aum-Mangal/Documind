"""Persisted knowledge graph: entities, their mentions in chunks, and relations.

Ready documents are queued again so the worker builds their graph (and re-chunks them
with the current settings) without anyone re-uploading.

Revision ID: 0005_knowledge_graph
Revises: 0004_usage_events
Create Date: 2026-11-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_knowledge_graph"
down_revision = "0004_usage_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "entities",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("canonical", sa.String(200), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.PrimaryKeyConstraint("id", name="entities_pkey"),
        sa.UniqueConstraint("user_id", "canonical", name="entities_user_id_key"),
    )
    op.create_table(
        "entity_mentions",
        sa.Column("entity_id", sa.BigInteger(), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_id", sa.BigInteger(), sa.ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("entity_id", "chunk_id", name="entity_mentions_pkey"),
    )
    op.create_index("ix_entity_mentions_document_id", "entity_mentions", ["document_id"])
    op.create_table(
        "relations",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_id", sa.BigInteger(), sa.ForeignKey("chunks.id", ondelete="CASCADE")),
        sa.Column("source_id", sa.BigInteger(), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_id", sa.BigInteger(), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("predicate", sa.String(60), nullable=False),
        sa.PrimaryKeyConstraint("id", name="relations_pkey"),
        sa.UniqueConstraint("document_id", "source_id", "target_id", "predicate", name="relations_document_id_key"),
    )
    op.create_index("ix_relations_source_id", "relations", ["source_id"])
    op.create_index("ix_relations_target_id", "relations", ["target_id"])

    op.execute("UPDATE documents SET status = 'queued', stage = NULL, progress = 0, attempts = 0, run_after = now() "
               "WHERE status = 'ready'")


def downgrade() -> None:
    op.drop_table("relations")
    op.drop_table("entity_mentions")
    op.drop_table("entities")

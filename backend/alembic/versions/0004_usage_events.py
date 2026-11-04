"""Usage events for per-user daily AI quotas.

Revision ID: 0004_usage_events
Revises: 0003_ingestion_conversations
Create Date: 2026-11-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_usage_events"
down_revision = "0003_ingestion_conversations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usage_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="usage_events_pkey"),
    )
    op.create_index("ix_usage_events_user_id_created_at", "usage_events", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_table("usage_events")

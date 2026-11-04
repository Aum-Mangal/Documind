"""Enable pgvector, index documents by owner, cascade deletes from users.

Revision ID: 0002_pgvector_and_indexes
Revises: 0001_baseline
Create Date: 2026-10-29
"""
from alembic import op

revision = "0002_pgvector_and_indexes"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Used by the chunk embeddings added in the ingestion phase
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute("CREATE INDEX IF NOT EXISTS ix_documents_user_id ON documents (user_id)")

    # Deleting a user removes their documents instead of failing on the foreign key
    op.execute("ALTER TABLE documents DROP CONSTRAINT IF EXISTS documents_user_id_fkey")
    op.create_foreign_key(
        "documents_user_id_fkey", "documents", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )


def downgrade() -> None:
    op.drop_constraint("documents_user_id_fkey", "documents", type_="foreignkey")
    op.create_foreign_key("documents_user_id_fkey", "documents", "users", ["user_id"], ["id"])
    op.drop_index("ix_documents_user_id", table_name="documents")
    # The vector extension is left installed; other objects may depend on it.

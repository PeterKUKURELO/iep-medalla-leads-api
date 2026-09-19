"""Create the separate consumer complaints domain table."""

from alembic import op
import sqlalchemy as sa

revision = "20260911_03"
down_revision = "20260911_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "consumer_complaints",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("complaint_type", sa.String(20), nullable=False),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("document_type", sa.String(20), nullable=False),
        sa.Column("document_number", sa.String(30), nullable=False),
        sa.Column("address", sa.String(300), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("phone", sa.String(30), nullable=False),
        sa.Column("is_minor", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("representative_name", sa.String(150)),
        sa.Column("item_type", sa.String(20), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2)),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("requested_action", sa.Text(), nullable=False),
        sa.Column("privacy_accepted", sa.Boolean(), nullable=False),
        sa.Column("source_url", sa.String(500)),
        sa.Column("status", sa.String(30), server_default="received", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_consumer_complaints_created_at", "consumer_complaints", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_consumer_complaints_created_at", table_name="consumer_complaints")
    op.drop_table("consumer_complaints")

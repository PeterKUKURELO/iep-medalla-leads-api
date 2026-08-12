"""Create leads table."""

from alembic import op
import sqlalchemy as sa

revision = "20260811_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "leads",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("form_type", sa.String(20), nullable=False),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("phone", sa.String(30), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("education_level", sa.String(50)),
        sa.Column("grade", sa.String(50)),
        sa.Column("contact_reason", sa.String(150)),
        sa.Column("message", sa.Text()),
        sa.Column("privacy_accepted", sa.Boolean(), nullable=False),
        sa.Column("privacy_accepted_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("source_url", sa.String(500)),
        sa.Column("utm_source", sa.String(100)),
        sa.Column("utm_medium", sa.String(100)),
        sa.Column("utm_campaign", sa.String(150)),
        sa.Column("status", sa.String(30), server_default="new", nullable=False),
        sa.Column("admin_email_status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("admin_email_sent_at", sa.DateTime()),
        sa.Column("user_email_status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("user_email_sent_at", sa.DateTime()),
        sa.Column("email_error", sa.String(500)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_leads_email", "leads", ["email"])
    op.create_index("ix_leads_form_type", "leads", ["form_type"])


def downgrade() -> None:
    op.drop_index("ix_leads_form_type", table_name="leads")
    op.drop_index("ix_leads_email", table_name="leads")
    op.drop_table("leads")

"""Create durable lead notification jobs."""

from alembic import op
import sqlalchemy as sa

revision = "20260911_02"
down_revision = "20260911_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lead_notifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime()),
        sa.Column("locked_until", sa.DateTime()),
        sa.Column("claim_token", sa.String(36)),
        sa.Column("sent_at", sa.DateTime()),
        sa.Column("last_error_code", sa.String(100)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lead_id", "kind", name="uq_lead_notifications_lead_kind"),
    )
    op.create_index("ix_lead_notifications_lead_id", "lead_notifications", ["lead_id"])
    op.create_index(
        "ix_lead_notifications_due",
        "lead_notifications",
        ["status", "next_attempt_at", "locked_until"],
    )

    # Project legacy state without resending deliveries already marked sent.
    op.execute(
        sa.text(
            "INSERT INTO lead_notifications (lead_id, kind, status, sent_at) "
            "SELECT id, 'admin', CASE WHEN admin_email_status = 'sent' THEN 'sent' ELSE 'pending' END, "
            "admin_email_sent_at FROM leads"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO lead_notifications (lead_id, kind, status, sent_at) "
            "SELECT id, 'user', CASE WHEN user_email_status = 'sent' THEN 'sent' ELSE 'pending' END, "
            "user_email_sent_at FROM leads"
        )
    )


def downgrade() -> None:
    op.drop_index("ix_lead_notifications_due", table_name="lead_notifications")
    op.drop_index("ix_lead_notifications_lead_id", table_name="lead_notifications")
    op.drop_table("lead_notifications")

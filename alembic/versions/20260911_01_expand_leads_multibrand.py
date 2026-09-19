"""Expand leads for multi-brand coexistence.

Legacy data is backfilled as IEP Medalla because the only versioned writer before
this revision is the Medalla v1 endpoint. Production operators must verify that
assumption against the real data before applying this revision.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260911_01"
down_revision = "20260811_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    with op.batch_alter_table("leads") as batch:
        batch.add_column(sa.Column("brand_key", sa.String(50), nullable=True))
        batch.add_column(sa.Column("source_key", sa.String(100)))
        batch.add_column(sa.Column("phone_country", sa.String(2)))
        batch.add_column(sa.Column("organization_name", sa.String(200)))
        batch.add_column(sa.Column("job_title", sa.String(120)))
        batch.add_column(sa.Column("form_data", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("classification", sa.String(30)))
        batch.add_column(sa.Column("assigned_to", sa.String(120)))
        batch.add_column(sa.Column("next_follow_up_at", sa.DateTime()))
        batch.add_column(sa.Column("device_type", sa.String(30)))
        batch.add_column(sa.Column("utm_content", sa.String(150)))
        batch.add_column(sa.Column("utm_term", sa.String(150)))
        batch.alter_column("form_type", existing_type=sa.String(20), type_=sa.String(50), existing_nullable=False)

    empty_json = "JSON_OBJECT()" if dialect == "mysql" else "'{}'"
    op.execute(sa.text("UPDATE leads SET brand_key = 'iep-medalla' WHERE brand_key IS NULL"))
    op.execute(sa.text(f"UPDATE leads SET form_data = {empty_json} WHERE form_data IS NULL"))

    with op.batch_alter_table("leads") as batch:
        batch.alter_column("brand_key", existing_type=sa.String(50), nullable=False, server_default="iep-medalla")
        batch.alter_column("form_data", existing_type=sa.JSON(), nullable=False)
        batch.create_index("ix_leads_brand_key", ["brand_key"])
        batch.create_index("ix_leads_brand_created_at", ["brand_key", "created_at"])
        batch.create_index("ix_leads_brand_form_created_at", ["brand_key", "form_type", "created_at"])


def downgrade() -> None:
    with op.batch_alter_table("leads") as batch:
        batch.drop_index("ix_leads_brand_form_created_at")
        batch.drop_index("ix_leads_brand_created_at")
        batch.drop_index("ix_leads_brand_key")
        batch.alter_column("form_type", existing_type=sa.String(50), type_=sa.String(20), existing_nullable=False)
        for column in (
            "utm_term",
            "utm_content",
            "device_type",
            "next_follow_up_at",
            "assigned_to",
            "classification",
            "form_data",
            "job_title",
            "organization_name",
            "phone_country",
            "source_key",
            "brand_key",
        ):
            batch.drop_column(column)

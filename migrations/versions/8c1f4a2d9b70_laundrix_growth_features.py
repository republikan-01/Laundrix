"""Add rider GPS, promotions, reviews and refund workflow.

Revision ID: 8c1f4a2d9b70
Revises: 57ebad6fd5fe
"""
from alembic import op
import sqlalchemy as sa

revision = "8c1f4a2d9b70"
down_revision = "57ebad6fd5fe"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("delivery_personnel") as b:
        b.add_column(sa.Column("tracking_token", sa.String(64), nullable=True))
        b.add_column(sa.Column("current_lat", sa.Float(), nullable=True))
        b.add_column(sa.Column("current_lng", sa.Float(), nullable=True))
        b.add_column(sa.Column("location_updated_at", sa.DateTime(), nullable=True))
        b.create_index("ix_delivery_personnel_tracking_token", ["tracking_token"], unique=True)
    with op.batch_alter_table("bookings") as b:
        b.add_column(sa.Column("discount_code", sa.String(32), nullable=True))
        b.add_column(sa.Column("discount_amount", sa.Numeric(10, 2), nullable=False, server_default="0"))
    with op.batch_alter_table("payments") as b:
        b.add_column(sa.Column("refund_status", sa.Enum("none", "requested", "approved", "refunded", "rejected", name="refund_status"), nullable=False, server_default="none"))
        b.add_column(sa.Column("refund_note", sa.String(500), nullable=True))
    op.create_table("promotions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("discount_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("uses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_promotions_code", "promotions", ["code"], unique=True)
    op.create_table("reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id"), nullable=False, unique=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_reviews_user_id", "reviews", ["user_id"])


def downgrade():
    op.drop_index("ix_reviews_user_id", table_name="reviews")
    op.drop_table("reviews")
    op.drop_index("ix_promotions_code", table_name="promotions")
    op.drop_table("promotions")
    with op.batch_alter_table("payments") as b:
        b.drop_column("refund_note")
        b.drop_column("refund_status")
    with op.batch_alter_table("bookings") as b:
        b.drop_column("discount_amount")
        b.drop_column("discount_code")
    with op.batch_alter_table("delivery_personnel") as b:
        b.drop_index("ix_delivery_personnel_tracking_token")
        b.drop_column("location_updated_at")
        b.drop_column("current_lng")
        b.drop_column("current_lat")
        b.drop_column("tracking_token")

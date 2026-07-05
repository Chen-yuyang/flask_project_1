"""add overdue_reminder_sent to record

Revision ID: add_overdue_reminder_field
Revises: 1524dbdc07d4
Create Date: 2026-03-06

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_overdue_reminder_field'
down_revision = '1524dbdc07d4'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('record', sa.Column('overdue_reminder_sent', sa.Boolean(), nullable=True, server_default='0'))
    op.execute("UPDATE record SET overdue_reminder_sent = 0 WHERE overdue_reminder_sent IS NULL")


def downgrade():
    op.drop_column('record', 'overdue_reminder_sent')

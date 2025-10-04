"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2025-09-03 00:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'sms_messages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('to', sa.String(length=32), nullable=False),
        sa.Column('message', sa.String(length=500), nullable=False),
        sa.Column('status', sa.String(length=32)),
        sa.Column('task_id', sa.String(length=64)),
        sa.Column('correlation_id', sa.String(length=64)),
        sa.Column('attempts', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True)),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_sms_messages_to', 'sms_messages', ['to'])
    op.create_index('ix_sms_messages_status', 'sms_messages', ['status'])
    op.create_index('ix_sms_messages_correlation_id', 'sms_messages', ['correlation_id'])
    op.create_index('ix_sms_messages_created_at', 'sms_messages', ['created_at'])
    op.create_unique_constraint('uq_sms_messages_task_id', 'sms_messages', ['task_id'])


def downgrade() -> None:
    op.drop_constraint('uq_sms_messages_task_id', 'sms_messages', type_='unique')
    op.drop_index('ix_sms_messages_created_at', table_name='sms_messages')
    op.drop_index('ix_sms_messages_correlation_id', table_name='sms_messages')
    op.drop_index('ix_sms_messages_status', table_name='sms_messages')
    op.drop_index('ix_sms_messages_to', table_name='sms_messages')
    op.drop_table('sms_messages')


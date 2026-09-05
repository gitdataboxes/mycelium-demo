"""add messaging context and responder edge type

Revision ID: c3f14d567890
Revises: b1e02c438a91
Create Date: 2026-04-03 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3f14d567890'
down_revision: Union[str, None] = 'b1e02c438a91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add 'responder' to edge_type enum
    op.execute("ALTER TYPE edge_type ADD VALUE IF NOT EXISTS 'responder'")

    # Add context_node_id column to messages
    op.add_column('messages', sa.Column(
        'context_node_id', sa.UUID(), nullable=True,
    ))
    op.create_foreign_key(
        'fk_messages_context_node', 'messages', 'nodes',
        ['context_node_id'], ['id'],
    )
    op.create_index(
        'idx_messages_context', 'messages',
        ['context_node_id', 'created_at'],
        postgresql_where=sa.text('context_node_id IS NOT NULL'),
    )


def downgrade() -> None:
    op.drop_index('idx_messages_context', table_name='messages')
    op.drop_constraint('fk_messages_context_node', 'messages', type_='foreignkey')
    op.drop_column('messages', 'context_node_id')
    # Note: cannot remove enum value in PostgreSQL

"""migrate to node/edge pattern

Revision ID: b1e02c438a91
Revises: a0f05b925247
Create Date: 2026-04-03 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy.vector


# revision identifiers, used by Alembic.
revision: str = 'b1e02c438a91'
down_revision: Union[str, None] = 'a0f05b925247'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ──────────────────────────────────────────────────────────────
    # 1. Create new foundation tables: communities, nodes
    # ──────────────────────────────────────────────────────────────
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'node_type') THEN
                CREATE TYPE node_type AS ENUM ('user', 'organization', 'event');
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'event_urgency') THEN
                CREATE TYPE event_urgency AS ENUM ('standard', 'spontaneous');
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'edge_type') THEN
                CREATE TYPE edge_type AS ENUM ('vouch', 'cool', 'block', 'report', 'member', 'participant', 'host');
            END IF;
        END $$;
    """)

    op.create_table('communities',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('code_of_conduct', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('nodes',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('community_id', sa.UUID(), nullable=False),
        sa.Column('type', sa.Enum('user', 'organization', 'event', name='node_type', create_type=False), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['community_id'], ['communities.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_nodes_community', 'nodes', ['community_id'])
    op.create_index('idx_nodes_type', 'nodes', ['community_id', 'type'])

    # ──────────────────────────────────────────────────────────────
    # 2. Create a default community & migrate existing users to nodes
    # ──────────────────────────────────────────────────────────────
    # Insert a default community
    op.execute("""
        INSERT INTO communities (id, name, description)
        VALUES (gen_random_uuid(), 'Default', 'Initial community')
    """)

    # Create a node row for every existing user, copying their id and created_at
    op.execute("""
        INSERT INTO nodes (id, community_id, type, created_at, updated_at)
        SELECT u.id, c.id, 'user', u.created_at, u.created_at
        FROM users u
        CROSS JOIN communities c
        LIMIT (SELECT count(*) FROM users)
    """)

    # ──────────────────────────────────────────────────────────────
    # 3. Refactor users table: add node_id, migrate data, drop id
    # ──────────────────────────────────────────────────────────────

    # Add node_id column (nullable initially)
    op.add_column('users', sa.Column('node_id', sa.UUID(), nullable=True))
    op.add_column('users', sa.Column('name', sa.String(255), nullable=True))

    # Copy id -> node_id for all existing users
    op.execute("UPDATE users SET node_id = id")

    # Drop all foreign keys and constraints that reference users.id
    # We need to drop child table FKs first, then modify users, then re-add
    op.drop_constraint('coolings_cooler_id_fkey', 'coolings', type_='foreignkey')
    op.drop_constraint('coolings_target_id_fkey', 'coolings', type_='foreignkey')
    op.drop_constraint('vouches_voucher_id_fkey', 'vouches', type_='foreignkey')
    op.drop_constraint('vouches_vouchee_id_fkey', 'vouches', type_='foreignkey')
    op.drop_constraint('magic_link_tokens_user_id_fkey', 'magic_link_tokens', type_='foreignkey')
    op.drop_constraint('sessions_user_id_fkey', 'sessions', type_='foreignkey')
    op.drop_constraint('match_history_user_a_id_fkey', 'match_history', type_='foreignkey')
    op.drop_constraint('match_history_user_b_id_fkey', 'match_history', type_='foreignkey')
    op.drop_constraint('membrane_attributes_user_id_fkey', 'membrane_attributes', type_='foreignkey')
    op.drop_constraint('signals_user_id_fkey', 'signals', type_='foreignkey')

    # Now drop the old PK and set node_id as the new PK
    op.drop_constraint('users_pkey', 'users', type_='primary')
    op.alter_column('users', 'node_id', nullable=False)
    op.create_primary_key('users_pkey', 'users', ['node_id'])
    op.create_foreign_key('users_node_id_fkey', 'users', 'nodes', ['node_id'], ['id'])

    # Drop the old id column and created_at (now on nodes)
    op.drop_column('users', 'id')
    op.drop_column('users', 'created_at')

    # Re-create FKs from auth tables to users.node_id
    op.create_foreign_key('magic_link_tokens_user_id_fkey', 'magic_link_tokens', 'users', ['user_id'], ['node_id'])
    op.create_foreign_key('sessions_user_id_fkey', 'sessions', 'users', ['user_id'], ['node_id'])

    # ──────────────────────────────────────────────────────────────
    # 4. Rename membrane_attributes -> membrane_entries, user_id -> node_id
    # ──────────────────────────────────────────────────────────────
    op.rename_table('membrane_attributes', 'membrane_entries')
    op.alter_column('membrane_entries', 'user_id', new_column_name='node_id')
    op.add_column('membrane_entries', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.create_foreign_key('membrane_entries_node_id_fkey', 'membrane_entries', 'nodes', ['node_id'], ['id'])
    op.create_index('idx_membrane_node', 'membrane_entries', ['node_id'])

    # ──────────────────────────────────────────────────────────────
    # 5. Signals: user_id -> node_id, make expires_at nullable
    # ──────────────────────────────────────────────────────────────
    op.alter_column('signals', 'user_id', new_column_name='node_id')
    op.alter_column('signals', 'expires_at', nullable=True)
    op.create_foreign_key('signals_node_id_fkey', 'signals', 'nodes', ['node_id'], ['id'])
    op.create_index('idx_signals_node', 'signals', ['node_id'])
    op.create_index('idx_signals_expires', 'signals', ['expires_at'])

    # ──────────────────────────────────────────────────────────────
    # 6. Create unified edges table & migrate vouches + coolings
    # ──────────────────────────────────────────────────────────────
    op.create_table('edges',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('source_node_id', sa.UUID(), nullable=False),
        sa.Column('target_node_id', sa.UUID(), nullable=False),
        sa.Column('type', sa.Enum('vouch', 'cool', 'block', 'report', 'member', 'participant', 'host', name='edge_type', create_type=False), nullable=False),
        sa.Column('context_node_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['source_node_id'], ['nodes.id']),
        sa.ForeignKeyConstraint(['target_node_id'], ['nodes.id']),
        sa.ForeignKeyConstraint(['context_node_id'], ['nodes.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_node_id', 'target_node_id', 'type', 'context_node_id', name='uq_edge')
    )
    op.create_index('idx_edges_source', 'edges', ['source_node_id'])
    op.create_index('idx_edges_target', 'edges', ['target_node_id'])
    op.create_index('idx_edges_type', 'edges', ['type'])
    op.execute("CREATE INDEX idx_edges_context ON edges(context_node_id) WHERE context_node_id IS NOT NULL")

    # Migrate active vouches (non-withdrawn) to edges
    op.execute("""
        INSERT INTO edges (id, source_node_id, target_node_id, type, created_at, updated_at)
        SELECT id, voucher_id, vouchee_id, 'vouch', created_at, created_at
        FROM vouches
        WHERE withdrawn_at IS NULL
    """)

    # Migrate coolings to edges
    op.execute("""
        INSERT INTO edges (id, source_node_id, target_node_id, type, created_at, updated_at)
        SELECT id, cooler_id, target_id, 'cool', created_at, created_at
        FROM coolings
    """)

    # Drop old tables
    op.drop_table('vouches')
    op.drop_constraint('uq_cooling_pair', 'coolings', type_='unique')
    op.drop_table('coolings')

    # ──────────────────────────────────────────────────────────────
    # 7. Update match_history: user_a_id/user_b_id -> node_a_id/node_b_id
    # ──────────────────────────────────────────────────────────────
    op.alter_column('match_history', 'user_a_id', new_column_name='node_a_id')
    op.alter_column('match_history', 'user_b_id', new_column_name='node_b_id')
    op.create_foreign_key('match_history_node_a_id_fkey', 'match_history', 'nodes', ['node_a_id'], ['id'])
    op.create_foreign_key('match_history_node_b_id_fkey', 'match_history', 'nodes', ['node_b_id'], ['id'])
    op.create_index('idx_match_history_nodes', 'match_history', ['node_a_id', 'node_b_id'])

    # ──────────────────────────────────────────────────────────────
    # 8. Create extension tables (organizations, events) and messages
    # ──────────────────────────────────────────────────────────────
    op.create_table('organizations',
        sa.Column('node_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['node_id'], ['nodes.id']),
        sa.PrimaryKeyConstraint('node_id')
    )

    op.create_table('events',
        sa.Column('node_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('location', sa.Text(), nullable=True),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('urgency', sa.Enum('standard', 'spontaneous', name='event_urgency', create_type=False), nullable=False, server_default='standard'),
        sa.ForeignKeyConstraint(['node_id'], ['nodes.id']),
        sa.PrimaryKeyConstraint('node_id')
    )

    op.create_table('messages',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('from_user', sa.UUID(), nullable=False),
        sa.Column('to_user', sa.UUID(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['from_user'], ['users.node_id']),
        sa.ForeignKeyConstraint(['to_user'], ['users.node_id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_messages_to', 'messages', ['to_user', 'created_at'])


def downgrade() -> None:
    # Drop new tables
    op.drop_index('idx_messages_to', table_name='messages')
    op.drop_table('messages')
    op.drop_table('events')
    op.drop_table('organizations')

    # Restore match_history columns
    op.drop_index('idx_match_history_nodes', table_name='match_history')
    op.drop_constraint('match_history_node_a_id_fkey', 'match_history', type_='foreignkey')
    op.drop_constraint('match_history_node_b_id_fkey', 'match_history', type_='foreignkey')
    op.alter_column('match_history', 'node_a_id', new_column_name='user_a_id')
    op.alter_column('match_history', 'node_b_id', new_column_name='user_b_id')

    # Recreate vouches and coolings from edges (best-effort)
    op.create_table('vouches',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('voucher_id', sa.UUID(), nullable=False),
        sa.Column('vouchee_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('withdrawn_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.execute("""
        INSERT INTO vouches (id, voucher_id, vouchee_id, created_at)
        SELECT id, source_node_id, target_node_id, created_at
        FROM edges WHERE type = 'vouch'
    """)

    op.create_table('coolings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('cooler_id', sa.UUID(), nullable=False),
        sa.Column('target_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cooler_id', 'target_id', name='uq_cooling_pair')
    )
    op.execute("""
        INSERT INTO coolings (id, cooler_id, target_id, created_at)
        SELECT id, source_node_id, target_node_id, created_at
        FROM edges WHERE type = 'cool'
    """)

    # Drop edges
    op.drop_index('idx_edges_source', table_name='edges')
    op.drop_index('idx_edges_target', table_name='edges')
    op.drop_index('idx_edges_type', table_name='edges')
    op.execute("DROP INDEX IF EXISTS idx_edges_context")
    op.drop_table('edges')

    # Restore signals
    op.drop_index('idx_signals_node', table_name='signals')
    op.drop_index('idx_signals_expires', table_name='signals')
    op.drop_constraint('signals_node_id_fkey', 'signals', type_='foreignkey')
    op.alter_column('signals', 'node_id', new_column_name='user_id')
    op.alter_column('signals', 'expires_at', nullable=False)

    # Restore membrane_attributes
    op.drop_index('idx_membrane_node', table_name='membrane_entries')
    op.drop_constraint('membrane_entries_node_id_fkey', 'membrane_entries', type_='foreignkey')
    op.drop_column('membrane_entries', 'updated_at')
    op.alter_column('membrane_entries', 'node_id', new_column_name='user_id')
    op.rename_table('membrane_entries', 'membrane_attributes')

    # Restore users table: add id column back, drop node_id
    op.drop_constraint('sessions_user_id_fkey', 'sessions', type_='foreignkey')
    op.drop_constraint('magic_link_tokens_user_id_fkey', 'magic_link_tokens', type_='foreignkey')
    op.drop_constraint('users_node_id_fkey', 'users', type_='foreignkey')
    op.drop_constraint('users_pkey', 'users', type_='primary')

    op.add_column('users', sa.Column('id', sa.UUID(), nullable=True))
    op.add_column('users', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.execute("UPDATE users SET id = node_id")
    op.alter_column('users', 'id', nullable=False)
    op.create_primary_key('users_pkey', 'users', ['id'])
    op.drop_column('users', 'node_id')
    op.drop_column('users', 'name')

    # Restore FKs to users.id
    op.create_foreign_key('magic_link_tokens_user_id_fkey', 'magic_link_tokens', 'users', ['user_id'], ['id'])
    op.create_foreign_key('sessions_user_id_fkey', 'sessions', 'users', ['user_id'], ['id'])
    op.create_foreign_key('membrane_attributes_user_id_fkey', 'membrane_attributes', 'users', ['user_id'], ['id'])
    op.create_foreign_key('signals_user_id_fkey', 'signals', 'users', ['user_id'], ['id'])
    op.create_foreign_key('match_history_user_a_id_fkey', 'match_history', 'users', ['user_a_id'], ['id'])
    op.create_foreign_key('match_history_user_b_id_fkey', 'match_history', 'users', ['user_b_id'], ['id'])
    op.create_foreign_key('vouches_voucher_id_fkey', 'vouches', 'users', ['voucher_id'], ['id'])
    op.create_foreign_key('vouches_vouchee_id_fkey', 'vouches', 'users', ['vouchee_id'], ['id'])
    op.create_foreign_key('coolings_cooler_id_fkey', 'coolings', 'users', ['cooler_id'], ['id'])
    op.create_foreign_key('coolings_target_id_fkey', 'coolings', 'users', ['target_id'], ['id'])

    # Drop nodes and communities
    op.drop_index('idx_nodes_community', table_name='nodes')
    op.drop_index('idx_nodes_type', table_name='nodes')
    op.drop_table('nodes')
    op.drop_table('communities')

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS edge_type")
    op.execute("DROP TYPE IF EXISTS event_urgency")
    op.execute("DROP TYPE IF EXISTS node_type")

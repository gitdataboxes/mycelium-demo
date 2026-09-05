"""Persist attribute directions using the same values as matching queries.

Revision ID: e5f36a789012
Revises: d4e25f678901
"""
from alembic import op

revision = "e5f36a789012"
down_revision = "d4e25f678901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE attribute_direction RENAME VALUE 'INPUT' TO 'input'")
    op.execute("ALTER TYPE attribute_direction RENAME VALUE 'OUTPUT' TO 'output'")


def downgrade() -> None:
    op.execute("ALTER TYPE attribute_direction RENAME VALUE 'input' TO 'INPUT'")
    op.execute("ALTER TYPE attribute_direction RENAME VALUE 'output' TO 'OUTPUT'")

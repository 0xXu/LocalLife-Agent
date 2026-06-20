"""Record the existing Flyway V1--V6 schema as Alembic's baseline.

Revision ID: 0001_existing_schema_baseline
Revises:
Create Date: 2026-06-20
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0001_existing_schema_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op: Flyway V1--V6 already created these production tables."""
    pass


def downgrade() -> None:
    """No-op: ownership of the existing tables remains with Flyway."""
    pass

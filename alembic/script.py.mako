"""${message}

Revisión: ${up_revision}
Anterior: ${down_revision | comma,n}
Fecha:    ${create_date}
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, Sequence[str], None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    """Aplica el cambio."""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Deshace el cambio (alembic downgrade -1)."""
    ${downgrades if downgrades else "pass"}

"""after-visit memory, translations, cached audio and privacy tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-27
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

TABLES = ["mm_visits", "mm_visit_instructions", "mm_instruction_translations", "mm_audio_clips", "mm_phrase_translations"]


def upgrade() -> None:
    # Created from the models so the column definitions (including encrypted columns) stay in one place.
    from app import models  # noqa: F401  (registers every table)
    from app.database.session import Base
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, tables=[Base.metadata.tables[t] for t in TABLES], checkfirst=True)


def downgrade() -> None:
    for t in reversed(TABLES):
        op.drop_table(t)

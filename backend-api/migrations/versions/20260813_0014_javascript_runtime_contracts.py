"""Define independent JavaScript ACM runtime contracts and starter templates.

Revision ID: 20260813_0014
Revises: 20260813_0013
Create Date: 2026-08-13
"""

from collections.abc import Sequence
from typing import Optional, Union

from alembic import op

revision: str = "20260813_0014"
down_revision: Optional[str] = "20260813_0013"
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    op.execute("ALTER TABLE languages ADD COLUMN runtime_mode VARCHAR(20)")
    op.execute("ALTER TABLE languages ADD COLUMN input_api VARCHAR(100)")
    op.execute("ALTER TABLE languages ADD COLUMN output_api VARCHAR(100)")
    op.execute("ALTER TABLE languages ADD COLUMN eof_value VARCHAR(30)")
    op.execute("ALTER TABLE problems ADD COLUMN starter_code_v8 TEXT")
    op.execute("ALTER TABLE problems ADD COLUMN starter_code_nodejs TEXT")
    op.execute(
        "ALTER TABLE languages ADD CONSTRAINT ck_languages_runtime_mode "
        "CHECK (runtime_mode IS NULL OR runtime_mode IN ('v8-compat', 'nodejs'))"
    )
    op.execute(
        """
        UPDATE languages SET
            display_name = 'JavaScript V8', version = 'ECMAScript 2023',
            monaco_language = 'javascript', source_filename = 'main.js',
            runtime_mode = 'v8-compat', input_api = 'readline()',
            output_api = 'print(...args)', eof_value = 'undefined',
            compile_command = NULL, run_command = 'node v8-runner.cjs',
            docker_image = 'node:22-bookworm-slim', enabled = TRUE, sort_order = 10
        WHERE slug = 'javascript-v8'
        """
    )
    op.execute(
        """
        UPDATE languages SET
            display_name = 'Node.js', version = '22',
            monaco_language = 'javascript', source_filename = 'main.js',
            runtime_mode = 'nodejs', input_api = 'fs.readFileSync(0, ''utf8'')',
            output_api = 'console.log/process.stdout.write', eof_value = NULL,
            compile_command = NULL, run_command = 'node main.js',
            docker_image = 'node:22-alpine', enabled = TRUE, sort_order = 20
        WHERE slug = 'nodejs'
        """
    )
    op.execute(
        "UPDATE languages SET enabled = FALSE "
        "WHERE slug NOT IN ('javascript-v8', 'nodejs')"
    )
    op.execute(
        "ALTER TABLE languages ADD CONSTRAINT ck_languages_enabled_runtime_contract "
        "CHECK (NOT enabled OR (runtime_mode IS NOT NULL AND input_api IS NOT NULL "
        "AND output_api IS NOT NULL))"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE languages DROP CONSTRAINT ck_languages_enabled_runtime_contract"
    )
    op.execute("ALTER TABLE problems DROP COLUMN starter_code_nodejs")
    op.execute("ALTER TABLE problems DROP COLUMN starter_code_v8")
    op.execute("ALTER TABLE languages DROP CONSTRAINT ck_languages_runtime_mode")
    for column in ("eof_value", "output_api", "input_api", "runtime_mode"):
        op.execute(f"ALTER TABLE languages DROP COLUMN {column}")

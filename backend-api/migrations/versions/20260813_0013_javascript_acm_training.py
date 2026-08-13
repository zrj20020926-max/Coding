"""Reposition the catalog for JavaScript ACM input/output training.

Revision ID: 20260813_0013
Revises: 20260813_0012
Create Date: 2026-08-13
"""

from collections.abc import Sequence
from typing import Optional, Union

from alembic import op

revision: str = "20260813_0013"
down_revision: Optional[str] = "20260813_0012"
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE training_category AS ENUM ("
        "'single-value', 'single-line-multiple-values', 'multi-line', "
        "'test-cases', 'read-until-eof', 'sentinel', 'array-input', "
        "'string-input', 'matrix-input', 'mixed-input', 'large-input', "
        "'output-format', 'comprehensive')"
    )
    op.execute(
        "ALTER TABLE problems ADD COLUMN training_category training_category "
        "NOT NULL DEFAULT 'comprehensive'"
    )
    op.execute(
        """
        UPDATE problems SET training_category = CASE slug
            WHEN 'a-plus-b' THEN 'single-line-multiple-values'::training_category
            WHEN 'array-total' THEN 'array-input'::training_category
            WHEN 'reverse-line' THEN 'string-input'::training_category
            WHEN 'frequency-queries' THEN 'multi-line'::training_category
            WHEN 'sorted-pair-exists' THEN 'array-input'::training_category
            WHEN 'balanced-brackets' THEN 'string-input'::training_category
            WHEN 'queue-commands' THEN 'multi-line'::training_category
            WHEN 'first-occurrence' THEN 'array-input'::training_category
            WHEN 'stable-score-sort' THEN 'output-format'::training_category
            WHEN 'matrix-diagonal-sum' THEN 'matrix-input'::training_category
            WHEN 'longest-unique-segment' THEN 'string-input'::training_category
            WHEN 'range-sum-queries' THEN 'large-input'::training_category
            WHEN 'merge-intervals' THEN 'multi-line'::training_category
            WHEN 'rotated-array-search' THEN 'array-input'::training_category
            WHEN 'island-count' THEN 'matrix-input'::training_category
            WHEN 'maze-shortest-steps' THEN 'matrix-input'::training_category
            WHEN 'graph-component-count' THEN 'mixed-input'::training_category
            WHEN 'union-find-queries' THEN 'mixed-input'::training_category
            WHEN 'directed-shortest-paths' THEN 'large-input'::training_category
            WHEN 'minimum-spanning-network' THEN 'large-input'::training_category
            WHEN 'maximum-compatible-events' THEN 'multi-line'::training_category
            WHEN 'zero-one-knapsack' THEN 'mixed-input'::training_category
            WHEN 'minimum-coin-count' THEN 'single-line-multiple-values'::training_category
            WHEN 'longest-increasing-subsequence' THEN 'array-input'::training_category
            WHEN 'string-edit-distance' THEN 'multi-line'::training_category
            WHEN 'weighted-grid-route' THEN 'matrix-input'::training_category
            WHEN 'exact-k-nonadjacent' THEN 'array-input'::training_category
            WHEN 'offline-edge-deletions' THEN 'large-input'::training_category
            WHEN 'kth-pair-distance' THEN 'large-input'::training_category
            ELSE 'comprehensive'::training_category
        END
        """
    )
    op.execute(
        "CREATE INDEX idx_problems_public_training_category "
        "ON problems (training_category, id) WHERE visibility = 'public'"
    )

    # Keep the existing language row id so historical foreign keys remain stable.
    op.execute(
        """
        UPDATE languages
           SET slug = 'nodejs', display_name = 'Node.js', version = '22',
               monaco_language = 'javascript', source_filename = 'main.js',
            compile_command = NULL, run_command = 'node main.js',
               docker_image = 'node:22-alpine', enabled = TRUE, sort_order = 20
         WHERE slug = 'javascript'
        """
    )
    op.execute(
        """
        INSERT INTO languages (
            slug, display_name, version, monaco_language, source_filename,
            compile_command, run_command, docker_image, enabled, sort_order
        ) VALUES (
            'javascript-v8', 'JavaScript V8', 'ES2023', 'javascript', 'main.js',
            NULL, 'node v8-runner.cjs', 'node:22-alpine', TRUE, 10
        ) ON CONFLICT (slug) DO UPDATE SET
            display_name = EXCLUDED.display_name,
            version = EXCLUDED.version,
            monaco_language = EXCLUDED.monaco_language,
            source_filename = EXCLUDED.source_filename,
            enabled = TRUE,
            sort_order = EXCLUDED.sort_order
        """
    )
    op.execute(
        "UPDATE languages SET enabled = FALSE "
        "WHERE slug NOT IN ('javascript-v8', 'nodejs')"
    )


def downgrade() -> None:
    op.execute("UPDATE languages SET enabled = TRUE WHERE slug IN ('python', 'cpp')")
    op.execute("DELETE FROM languages WHERE slug = 'javascript-v8'")
    op.execute(
        "UPDATE languages SET slug = 'javascript', display_name = 'JavaScript (Node.js)', "
        "sort_order = 40 WHERE slug = 'nodejs'"
    )
    op.execute("DROP INDEX IF EXISTS idx_problems_public_training_category")
    op.execute("ALTER TABLE problems DROP COLUMN training_category")
    op.execute("DROP TYPE training_category")

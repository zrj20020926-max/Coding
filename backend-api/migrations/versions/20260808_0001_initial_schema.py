# ruff: noqa: E501
"""Create the initial ACM platform schema.

Revision ID: 20260808_0001
Revises:
Create Date: 2026-08-08
"""

from collections.abc import Sequence
from typing import Optional, Union

from alembic import op

revision: str = "20260808_0001"
down_revision: Optional[str] = None
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None

UPGRADE_STATEMENTS = (
    "CREATE EXTENSION IF NOT EXISTS pgcrypto",
    "CREATE EXTENSION IF NOT EXISTS citext",
    "CREATE TYPE problem_difficulty AS ENUM ('easy', 'medium', 'hard')",
    "CREATE TYPE problem_visibility AS ENUM ('draft', 'public', 'private')",
    """
    CREATE TYPE submission_status AS ENUM (
        'Pending', 'Compiling', 'Running', 'Accepted', 'Wrong Answer',
        'Compile Error', 'Runtime Error', 'Time Limit Exceeded',
        'Memory Limit Exceeded', 'System Error'
    )
    """,
    "CREATE TYPE ai_analysis_status AS ENUM ('pending', 'running', 'completed', 'failed')",
    """
    CREATE TABLE users (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        username CITEXT NOT NULL UNIQUE CHECK (char_length(username) BETWEEN 3 AND 32),
        email CITEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        nickname VARCHAR(50) NOT NULL,
        avatar_url TEXT,
        bio VARCHAR(300),
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        is_admin BOOLEAN NOT NULL DEFAULT FALSE,
        solved_count INTEGER NOT NULL DEFAULT 0 CHECK (solved_count >= 0),
        submission_count INTEGER NOT NULL DEFAULT 0 CHECK (submission_count >= 0),
        accepted_count INTEGER NOT NULL DEFAULT 0 CHECK (accepted_count >= 0),
        last_login_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE languages (
        id SMALLSERIAL PRIMARY KEY,
        slug VARCHAR(30) NOT NULL UNIQUE,
        display_name VARCHAR(50) NOT NULL,
        version VARCHAR(30) NOT NULL,
        monaco_language VARCHAR(30) NOT NULL,
        source_filename VARCHAR(100) NOT NULL,
        compile_command TEXT,
        run_command TEXT NOT NULL,
        docker_image TEXT NOT NULL,
        enabled BOOLEAN NOT NULL DEFAULT TRUE,
        sort_order SMALLINT NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE problems (
        id BIGSERIAL PRIMARY KEY,
        slug VARCHAR(100) NOT NULL UNIQUE,
        title VARCHAR(200) NOT NULL,
        description TEXT NOT NULL,
        difficulty problem_difficulty NOT NULL,
        input_description TEXT NOT NULL,
        output_description TEXT NOT NULL,
        sample_input TEXT NOT NULL DEFAULT '',
        sample_output TEXT NOT NULL DEFAULT '',
        time_limit_ms INTEGER NOT NULL DEFAULT 1000 CHECK (time_limit_ms BETWEEN 100 AND 30000),
        memory_limit_mb INTEGER NOT NULL DEFAULT 256 CHECK (memory_limit_mb BETWEEN 16 AND 2048),
        visibility problem_visibility NOT NULL DEFAULT 'draft',
        source VARCHAR(200),
        created_by UUID REFERENCES users(id) ON DELETE SET NULL,
        accepted_count INTEGER NOT NULL DEFAULT 0 CHECK (accepted_count >= 0),
        submission_count INTEGER NOT NULL DEFAULT 0 CHECK (submission_count >= 0),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE tags (
        id SERIAL PRIMARY KEY,
        slug VARCHAR(50) NOT NULL UNIQUE,
        name VARCHAR(50) NOT NULL UNIQUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE problem_tags (
        problem_id BIGINT NOT NULL REFERENCES problems(id) ON DELETE CASCADE,
        tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
        PRIMARY KEY (problem_id, tag_id)
    )
    """,
    """
    CREATE TABLE test_cases (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        problem_id BIGINT NOT NULL REFERENCES problems(id) ON DELETE CASCADE,
        input_object_key TEXT NOT NULL,
        output_object_key TEXT NOT NULL,
        checksum CHAR(64) NOT NULL,
        score NUMERIC(6, 2) NOT NULL DEFAULT 0 CHECK (score >= 0),
        sequence INTEGER NOT NULL CHECK (sequence >= 0),
        is_sample BOOLEAN NOT NULL DEFAULT FALSE,
        is_hidden BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (problem_id, sequence)
    )
    """,
    """
    CREATE TABLE submissions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
        problem_id BIGINT NOT NULL REFERENCES problems(id) ON DELETE RESTRICT,
        language_id SMALLINT NOT NULL REFERENCES languages(id) ON DELETE RESTRICT,
        status submission_status NOT NULL DEFAULT 'Pending',
        source_code TEXT,
        source_object_key TEXT,
        source_checksum CHAR(64) NOT NULL,
        queue_message_id TEXT,
        compiler_output TEXT,
        error_message TEXT,
        time_used_ms INTEGER CHECK (time_used_ms >= 0),
        memory_used_kb INTEGER CHECK (memory_used_kb >= 0),
        passed_case_count INTEGER NOT NULL DEFAULT 0 CHECK (passed_case_count >= 0),
        total_case_count INTEGER NOT NULL DEFAULT 0 CHECK (total_case_count >= 0),
        score NUMERIC(7, 2) NOT NULL DEFAULT 0 CHECK (score >= 0),
        judged_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CHECK (source_code IS NOT NULL OR source_object_key IS NOT NULL)
    )
    """,
    """
    CREATE TABLE submission_case_results (
        id BIGSERIAL PRIMARY KEY,
        submission_id UUID NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
        test_case_id UUID NOT NULL REFERENCES test_cases(id) ON DELETE RESTRICT,
        status submission_status NOT NULL,
        time_used_ms INTEGER CHECK (time_used_ms >= 0),
        memory_used_kb INTEGER CHECK (memory_used_kb >= 0),
        exit_code INTEGER,
        stdout_excerpt TEXT,
        stderr_excerpt TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (submission_id, test_case_id)
    )
    """,
    """
    CREATE TABLE user_problem_progress (
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        problem_id BIGINT NOT NULL REFERENCES problems(id) ON DELETE CASCADE,
        attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
        accepted BOOLEAN NOT NULL DEFAULT FALSE,
        first_accepted_at TIMESTAMPTZ,
        last_submission_id UUID REFERENCES submissions(id) ON DELETE SET NULL,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (user_id, problem_id)
    )
    """,
    """
    CREATE TABLE discussions (
        id BIGSERIAL PRIMARY KEY,
        problem_id BIGINT NOT NULL REFERENCES problems(id) ON DELETE CASCADE,
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        title VARCHAR(200) NOT NULL,
        content TEXT NOT NULL,
        is_pinned BOOLEAN NOT NULL DEFAULT FALSE,
        is_locked BOOLEAN NOT NULL DEFAULT FALSE,
        like_count INTEGER NOT NULL DEFAULT 0 CHECK (like_count >= 0),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE discussion_comments (
        id BIGSERIAL PRIMARY KEY,
        discussion_id BIGINT NOT NULL REFERENCES discussions(id) ON DELETE CASCADE,
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        parent_id BIGINT REFERENCES discussion_comments(id) ON DELETE CASCADE,
        content TEXT NOT NULL,
        like_count INTEGER NOT NULL DEFAULT 0 CHECK (like_count >= 0),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE favorites (
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        problem_id BIGINT NOT NULL REFERENCES problems(id) ON DELETE CASCADE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (user_id, problem_id)
    )
    """,
    """
    CREATE TABLE collections (
        id BIGSERIAL PRIMARY KEY,
        slug VARCHAR(100) NOT NULL UNIQUE,
        title VARCHAR(200) NOT NULL,
        description TEXT,
        company VARCHAR(50),
        cover_url TEXT,
        is_public BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE collection_problems (
        collection_id BIGINT NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
        problem_id BIGINT NOT NULL REFERENCES problems(id) ON DELETE CASCADE,
        sequence INTEGER NOT NULL CHECK (sequence >= 0),
        PRIMARY KEY (collection_id, problem_id),
        UNIQUE (collection_id, sequence)
    )
    """,
    """
    CREATE TABLE ai_analyses (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        submission_id UUID NOT NULL UNIQUE REFERENCES submissions(id) ON DELETE CASCADE,
        status ai_analysis_status NOT NULL DEFAULT 'pending',
        failure_reason TEXT,
        time_complexity VARCHAR(100),
        space_complexity VARCHAR(100),
        suggestions JSONB,
        model_name VARCHAR(100),
        prompt_tokens INTEGER CHECK (prompt_tokens >= 0),
        completion_tokens INTEGER CHECK (completion_tokens >= 0),
        error_message TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE daily_challenges (
        challenge_date DATE PRIMARY KEY,
        problem_id BIGINT NOT NULL REFERENCES problems(id) ON DELETE RESTRICT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX idx_problems_public_difficulty ON problems (difficulty, id) WHERE visibility = 'public'",
    "CREATE INDEX idx_problem_tags_tag_id ON problem_tags (tag_id, problem_id)",
    "CREATE INDEX idx_test_cases_problem ON test_cases (problem_id, sequence)",
    "CREATE INDEX idx_submissions_user_created ON submissions (user_id, created_at DESC)",
    "CREATE INDEX idx_submissions_problem_status ON submissions (problem_id, status, created_at DESC)",
    "CREATE INDEX idx_submissions_pending ON submissions (created_at) WHERE status = 'Pending'",
    "CREATE UNIQUE INDEX idx_submissions_queue_message ON submissions (queue_message_id) WHERE queue_message_id IS NOT NULL",
    "CREATE INDEX idx_progress_user_accepted ON user_problem_progress (user_id, accepted)",
    "CREATE INDEX idx_discussions_problem_created ON discussions (problem_id, created_at DESC)",
    "CREATE INDEX idx_comments_discussion_created ON discussion_comments (discussion_id, created_at)",
    """
    CREATE FUNCTION set_updated_at()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = now();
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql
    """,
    "CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION set_updated_at()",
    "CREATE TRIGGER trg_languages_updated_at BEFORE UPDATE ON languages FOR EACH ROW EXECUTE FUNCTION set_updated_at()",
    "CREATE TRIGGER trg_problems_updated_at BEFORE UPDATE ON problems FOR EACH ROW EXECUTE FUNCTION set_updated_at()",
    "CREATE TRIGGER trg_submissions_updated_at BEFORE UPDATE ON submissions FOR EACH ROW EXECUTE FUNCTION set_updated_at()",
    "CREATE TRIGGER trg_progress_updated_at BEFORE UPDATE ON user_problem_progress FOR EACH ROW EXECUTE FUNCTION set_updated_at()",
    "CREATE TRIGGER trg_discussions_updated_at BEFORE UPDATE ON discussions FOR EACH ROW EXECUTE FUNCTION set_updated_at()",
    "CREATE TRIGGER trg_comments_updated_at BEFORE UPDATE ON discussion_comments FOR EACH ROW EXECUTE FUNCTION set_updated_at()",
    "CREATE TRIGGER trg_collections_updated_at BEFORE UPDATE ON collections FOR EACH ROW EXECUTE FUNCTION set_updated_at()",
    "CREATE TRIGGER trg_ai_analyses_updated_at BEFORE UPDATE ON ai_analyses FOR EACH ROW EXECUTE FUNCTION set_updated_at()",
    """
    INSERT INTO languages (
        slug, display_name, version, monaco_language, source_filename,
        compile_command, run_command, docker_image, sort_order
    ) VALUES
        ('cpp', 'C++', 'C++20', 'cpp', 'main.cpp', 'g++ -O2 -std=c++20 -o /tmp/app main.cpp', '/tmp/app', 'acm-judge/cpp:20', 10),
        ('java', 'Java', '21', 'java', 'Main.java', 'javac -encoding UTF-8 -d /tmp/classes Main.java', 'java -cp /tmp/classes Main', 'acm-judge/java:21', 20),
        ('python', 'Python', '3.12', 'python', 'main.py', NULL, 'python -I main.py', 'acm-judge/python:3.12', 30),
        ('javascript', 'JavaScript (Node.js)', '22', 'javascript', 'main.js', NULL, 'node main.js', 'acm-judge/node:22', 40),
        ('go', 'Go', '1.24', 'go', 'main.go', 'go build -o /tmp/app main.go', '/tmp/app', 'acm-judge/go:1.24', 50)
    ON CONFLICT (slug) DO NOTHING
    """,
    """
    INSERT INTO tags (slug, name) VALUES
        ('array', '数组'), ('linked-list', '链表'), ('binary-tree', '二叉树'),
        ('dfs', 'DFS'), ('bfs', 'BFS'), ('dynamic-programming', '动态规划'),
        ('greedy', '贪心'), ('graph', '图论'), ('union-find', '并查集'),
        ('sliding-window', '滑动窗口')
    ON CONFLICT (slug) DO NOTHING
    """,
)

DOWNGRADE_STATEMENTS = (
    "DROP TABLE IF EXISTS daily_challenges CASCADE",
    "DROP TABLE IF EXISTS ai_analyses CASCADE",
    "DROP TABLE IF EXISTS collection_problems CASCADE",
    "DROP TABLE IF EXISTS collections CASCADE",
    "DROP TABLE IF EXISTS favorites CASCADE",
    "DROP TABLE IF EXISTS discussion_comments CASCADE",
    "DROP TABLE IF EXISTS discussions CASCADE",
    "DROP TABLE IF EXISTS user_problem_progress CASCADE",
    "DROP TABLE IF EXISTS submission_case_results CASCADE",
    "DROP TABLE IF EXISTS submissions CASCADE",
    "DROP TABLE IF EXISTS test_cases CASCADE",
    "DROP TABLE IF EXISTS problem_tags CASCADE",
    "DROP TABLE IF EXISTS tags CASCADE",
    "DROP TABLE IF EXISTS problems CASCADE",
    "DROP TABLE IF EXISTS languages CASCADE",
    "DROP TABLE IF EXISTS users CASCADE",
    "DROP FUNCTION IF EXISTS set_updated_at()",
    "DROP TYPE IF EXISTS ai_analysis_status",
    "DROP TYPE IF EXISTS submission_status",
    "DROP TYPE IF EXISTS problem_visibility",
    "DROP TYPE IF EXISTS problem_difficulty",
)


def upgrade() -> None:
    for statement in UPGRADE_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE_STATEMENTS:
        op.execute(statement)

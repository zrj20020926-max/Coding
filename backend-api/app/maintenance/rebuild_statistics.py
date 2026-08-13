"""Rebuild all training progress and denormalized counters from terminal submissions."""

import argparse
import asyncio
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings

TERMINAL_SQL = (
    "'Accepted', 'Wrong Answer', 'Compile Error', 'Runtime Error', "
    "'Time Limit Exceeded', 'Memory Limit Exceeded', 'Output Limit Exceeded'"
)


@dataclass(frozen=True)
class RebuildResult:
    progress_rows: int
    stat_event_rows: int
    user_submission_count: int
    problem_submission_count: int


async def rebuild_statistics(database_url: str) -> RebuildResult:
    """Rebuild derived state in one transaction while excluding live finalizers."""

    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "SELECT pg_advisory_xact_lock("
                    "hashtext('codearena:training-statistics'))"
                )
            )
            await connection.execute(text("DELETE FROM user_problem_progress"))
            await connection.execute(text("DELETE FROM submission_stat_events"))
            await connection.execute(
                text(
                    f"""
                    INSERT INTO user_problem_progress (
                        user_id, problem_id, attempt_count, accepted,
                        first_accepted_at, last_submission_id, updated_at
                    )
                    SELECT
                        s.user_id,
                        s.problem_id,
                        count(*)::integer,
                        bool_or(s.status = 'Accepted'),
                        min(s.judged_at) FILTER (WHERE s.status = 'Accepted'),
                        (array_agg(
                            s.id ORDER BY COALESCE(s.judged_at, s.updated_at, s.created_at) DESC,
                            s.id DESC
                        ))[1],
                        now()
                    FROM submissions s
                    WHERE s.mode = 'judge' AND s.status IN ({TERMINAL_SQL})
                    GROUP BY s.user_id, s.problem_id
                    """
                )
            )
            await connection.execute(
                text(
                    f"""
                    INSERT INTO submission_stat_events (
                        submission_id, user_id, problem_id,
                        terminal_status, accepted, applied_at
                    )
                    SELECT
                        s.id, s.user_id, s.problem_id, s.status,
                        s.status = 'Accepted',
                        COALESCE(s.judged_at, s.updated_at, s.created_at)
                    FROM submissions s
                    WHERE s.mode = 'judge' AND s.status IN ({TERMINAL_SQL})
                    ON CONFLICT (submission_id) DO NOTHING
                    """
                )
            )
            await connection.execute(
                text(
                    "UPDATE users SET solved_count = 0, submission_count = 0, "
                    "accepted_count = 0"
                )
            )
            await connection.execute(
                text(
                    f"""
                    UPDATE users u
                    SET submission_count = totals.submission_count,
                        accepted_count = totals.accepted_count,
                        solved_count = totals.solved_count
                    FROM (
                        SELECT
                            s.user_id,
                            count(*)::integer AS submission_count,
                            count(*) FILTER (WHERE s.status = 'Accepted')::integer
                                AS accepted_count,
                            count(DISTINCT s.problem_id) FILTER (
                                WHERE s.status = 'Accepted'
                            )::integer AS solved_count
                        FROM submissions s
                        WHERE s.mode = 'judge' AND s.status IN ({TERMINAL_SQL})
                        GROUP BY s.user_id
                    ) totals
                    WHERE u.id = totals.user_id
                    """
                )
            )
            await connection.execute(
                text("UPDATE problems SET submission_count = 0, accepted_count = 0")
            )
            await connection.execute(
                text(
                    f"""
                    UPDATE problems p
                    SET submission_count = totals.submission_count,
                        accepted_count = totals.accepted_count
                    FROM (
                        SELECT
                            s.problem_id,
                            count(*)::integer AS submission_count,
                            count(*) FILTER (WHERE s.status = 'Accepted')::integer
                                AS accepted_count
                        FROM submissions s
                        WHERE s.mode = 'judge' AND s.status IN ({TERMINAL_SQL})
                        GROUP BY s.problem_id
                    ) totals
                    WHERE p.id = totals.problem_id
                    """
                )
            )
            progress_rows = int(
                await connection.scalar(text("SELECT count(*) FROM user_problem_progress"))
                or 0
            )
            stat_event_rows = int(
                await connection.scalar(text("SELECT count(*) FROM submission_stat_events"))
                or 0
            )
            user_submission_count = int(
                await connection.scalar(
                    text("SELECT COALESCE(sum(submission_count), 0) FROM users")
                )
                or 0
            )
            problem_submission_count = int(
                await connection.scalar(
                    text("SELECT COALESCE(sum(submission_count), 0) FROM problems")
                )
                or 0
            )
            return RebuildResult(
                progress_rows=progress_rows,
                stat_event_rows=stat_event_rows,
                user_submission_count=user_submission_count,
                problem_submission_count=problem_submission_count,
            )
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="required confirmation because the command replaces derived statistics",
    )
    args = parser.parse_args()
    if not args.apply:
        parser.error("refusing to modify statistics without --apply")
    result = asyncio.run(rebuild_statistics(settings.database_url))
    print(
        "statistics rebuilt: "
        f"progress={result.progress_rows}, events={result.stat_event_rows}, "
        f"users={result.user_submission_count}, problems={result.problem_submission_count}"
    )


if __name__ == "__main__":
    main()

# Alembic migrations

`versions/` is the authoritative PostgreSQL schema history. The initial revision intentionally
uses PostgreSQL DDL so CITEXT, named ENUMs, partial indexes, and update triggers remain explicit.

Run commands from `backend-api/`:

```text
alembic current
alembic upgrade head
alembic revision -m "describe_change"
```

The problem catalog plus `submissions`, `submission_case_results`, and `outbox_events` now have
matching SQLAlchemy 2.0 metadata. Hidden test-case and community tables are still DDL-only, so do
not use unreviewed `--autogenerate`: it would incorrectly propose dropping tables outside this
slice.

Legacy databases are stamped only at `20260808_0001` after structural verification. The normal
upgrade then applies every later revision, including the submission control-plane migration.

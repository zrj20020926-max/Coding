# Alembic migrations

`versions/` is the authoritative PostgreSQL schema history. The initial revision intentionally
uses PostgreSQL DDL so CITEXT, named ENUMs, partial indexes, and update triggers remain explicit.

Run commands from `backend-api/`:

```text
alembic current
alembic upgrade head
alembic revision -m "describe_change"
```

The problem catalog, versioned `test_sets` / `test_cases`, `submissions`,
`submission_case_results`, and `outbox_events` have matching SQLAlchemy 2.0 metadata. Some
community/operations tables remain explicit DDL, so do not use unreviewed `--autogenerate`: it
can still propose destructive changes outside the selected model slice.

Legacy databases are stamped only at `20260808_0001` after structural verification. The normal
upgrade then applies every later revision. Revision `20260812_0009` backfills legacy hidden cases
and immutable submission snapshots; test its table-lock and scan time on a production-sized copy
before rollout.

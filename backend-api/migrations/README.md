# Alembic migrations

`versions/` is the authoritative PostgreSQL schema history. The initial revision intentionally
uses PostgreSQL DDL so CITEXT, named ENUMs, partial indexes, and update triggers remain explicit.

Run commands from `backend-api/`:

```text
alembic current
alembic upgrade head
alembic revision -m "describe_change"
```

Do not use `--autogenerate` until all database tables have matching SQLAlchemy metadata.

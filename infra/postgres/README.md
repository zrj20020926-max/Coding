# PostgreSQL schema management

The one-shot `init/001_schema.sql` bootstrap was retired in Sprint 0. Alembic migrations under
`backend-api/migrations/versions/` are now the only schema source of truth.

Existing volumes created by the legacy SQL are adopted through
`python -m app.db.migration_bootstrap`, which validates the complete legacy signature before it
stamps the initial revision.

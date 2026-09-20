# Database — auto-run on deployment

`db/*.sql` scripts run **automatically** in two places:

1. **Postgres container init** — `docker-compose.yml` mounts `./backend_task_code/db`
   to `/docker-entrypoint-initdb.d` so a fresh volume is initialised.
2. **Backend startup** — `app/core/db_init.py` executes every `db/*.sql` file in
   lexicographic order inside the FastAPI `lifespan` (see `app/main.py`).
   Scripts are idempotent (`IF NOT EXISTS`), so re-running each deploy is safe.
   Disable with `AUTO_RUN_SQL=false`.

Order:

| File | Purpose |
|---|---|
| `01_extensions.sql` | `pgcrypto`, `pg_trgm` |
| `02_schema.sql` | All tables — canonical schema (mirrors `app/models/models.py`) |
| `03_indexes.sql` | Performance indexes (§42) + trigram search |
| `04_seed.sql` | Optional demo user/project/time-blocks (runs once) |

Alembic (`alembic/`) remains available for incremental migrations after the
initial deploy; the `.sql` files are the source of truth for fresh installs.

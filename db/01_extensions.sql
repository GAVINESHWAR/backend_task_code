-- 01_extensions.sql — auto-run first on deployment (idempotent).
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

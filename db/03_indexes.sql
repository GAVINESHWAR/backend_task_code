-- 03_indexes.sql — query performance (§42). Idempotent.
CREATE INDEX IF NOT EXISTS ix_tasks_user_status ON tasks (user_id, status) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS ix_tasks_user_due ON tasks (user_id, due_date) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS ix_tasks_user_priority ON tasks (user_id, priority) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS ix_tasks_project ON tasks (project_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS ix_tasks_updated ON tasks (updated_at DESC);
CREATE INDEX IF NOT EXISTS ix_tasks_parent ON tasks (parent_task_id) WHERE parent_task_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_tasks_title_trgm ON tasks USING gin (title gin_trgm_ops);

CREATE INDEX IF NOT EXISTS ix_events_user_start ON events (user_id, start_time);
CREATE INDEX IF NOT EXISTS ix_focus_user_started ON focus_sessions (user_id, started_at DESC);
CREATE INDEX IF NOT EXISTS ix_focus_task ON focus_sessions (task_id);
CREATE INDEX IF NOT EXISTS ix_workstates_task ON work_states (task_id);
CREATE INDEX IF NOT EXISTS ix_topics_path ON learning_topics (path_id);
CREATE INDEX IF NOT EXISTS ix_topics_next_review ON learning_topics (user_id, next_review_date);
CREATE INDEX IF NOT EXISTS ix_habitlogs_habit_date ON habit_logs (habit_id, log_date DESC);
CREATE INDEX IF NOT EXISTS ix_notes_user_updated ON notes (user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS ix_notes_title_trgm ON notes USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_inbox_user_status ON inbox_items (user_id, status);
CREATE INDEX IF NOT EXISTS ix_distractions_user_ts ON distractions (user_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS ix_activity_user_created ON activity_logs (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_daily_plans_user_date ON daily_plans (user_id, plan_date DESC);

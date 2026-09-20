-- 04_seed.sql — optional demo data. Idempotent via marker user.
-- A demo account is created only if it does not exist. Safe on every deploy.
DO $$
DECLARE
  demo_id UUID;
BEGIN
  SELECT id INTO demo_id FROM users WHERE email = 'demo@local.test';
  IF demo_id IS NULL THEN
    INSERT INTO users (email, password_hash, full_name)
    -- bcrypt hash of 'password123' (matches the prefilled demo login).
    VALUES ('demo@local.test', '$2b$12$wX.wJeWOlOTkfFvFir6Xmu4ko8E8s2Z25oBdqLEawwj/EHCo7iXdm', 'Demo User')
    RETURNING id INTO demo_id;

    INSERT INTO projects (user_id, name, description, category, status, priority)
    VALUES (demo_id, 'Ecommerce Application', 'Demo project from spec §12', 'Professional', 'Active', 'High');

    INSERT INTO time_blocks (user_id, label, weekday, start_time, end_time)
    VALUES
      (demo_id, 'Morning deep work', NULL, '06:00', '08:00'),
      (demo_id, 'Work day', NULL, '11:00', '20:00'),
      (demo_id, 'Evening', NULL, '21:00', '23:00');
  END IF;
END $$;

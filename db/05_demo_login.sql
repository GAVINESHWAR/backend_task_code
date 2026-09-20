-- 05_demo_login.sql — repair the demo account's password on databases where
-- 04_seed.sql already ran with the old placeholder hash. Idempotent: only
-- touches demo@local.test and only when the stored hash is NOT a valid
-- bcrypt hash of 'password123'. Safe on every deploy.
UPDATE users
SET password_hash = '$2b$12$wX.wJeWOlOTkfFvFir6Xmu4ko8E8s2Z25oBdqLEawwj/EHCo7iXdm',
    updated_at = now()
WHERE email = 'demo@local.test'
  AND password_hash <> '$2b$12$wX.wJeWOlOTkfFvFir6Xmu4ko8E8s2Z25oBdqLEawwj/EHCo7iXdm';

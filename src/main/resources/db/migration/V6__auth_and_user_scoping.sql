-- V6__auth_and_user_scoping.sql
-- Add user_id to sessions/routes for user-scoped data isolation.
-- Add password_hash + deepseek_api_key to user_profiles for auth.

-- 1. Sessions: add user_id
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS user_id VARCHAR(50);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);

-- 2. Routes: add user_id
ALTER TABLE routes ADD COLUMN IF NOT EXISTS user_id VARCHAR(50);
CREATE INDEX IF NOT EXISTS idx_routes_user_id ON routes(user_id);

-- 3. Favorites: add user_id column and index
ALTER TABLE favorites ADD COLUMN IF NOT EXISTS user_id VARCHAR(50);
CREATE INDEX IF NOT EXISTS idx_favorites_user_id ON favorites(user_id);

-- 4. User profiles: add auth columns
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS provider_name VARCHAR(50) DEFAULT 'deepseek';
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS deepseek_api_key VARCHAR(255);

-- 5. Fix JSONB→TEXT to avoid Hibernate type mismatch on insert
ALTER TABLE user_profiles ALTER COLUMN preference_tags TYPE TEXT;
ALTER TABLE user_profiles ALTER COLUMN avoid_tags TYPE TEXT;

-- 6. Update seed users with empty password (no login until registered via UI)
UPDATE user_profiles SET password_hash = NULL WHERE password_hash IS NULL;

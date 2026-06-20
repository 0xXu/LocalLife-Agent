-- V5__user_profiles.sql
-- User profile table for personalized route recommendations.
-- Stores mock user profiles + any custom registrations.
-- preference_tags and avoid_tags use JSONB for flexible key-value weights.

CREATE TABLE IF NOT EXISTS user_profiles (
    id              BIGSERIAL PRIMARY KEY,
    user_id         VARCHAR(50)  NOT NULL UNIQUE,
    name            VARCHAR(100) NOT NULL,
    profile_name    VARCHAR(100),
    preferred_city  VARCHAR(50)  DEFAULT '北京',
    avg_budget      DOUBLE PRECISION DEFAULT 0,
    favorite_categories TEXT,
    preference_tags JSONB,
    avoid_tags      JSONB,
    history_actions TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Seed 3 mock user profiles for demo
INSERT INTO user_profiles (user_id, name, profile_name, preferred_city, avg_budget, favorite_categories, preference_tags, avoid_tags, history_actions)
VALUES
(
    'user_001', '小林', '约会偏好型', '上海', 200,
    '["日料","咖啡","展览","西餐"]',
    '{"安静":0.90,"少排队":0.85,"拍照好看":0.80,"适合约会":0.78,"日料":0.72,"少走路":0.60}',
    '{"排队久":0.90,"太吵":0.80,"距离远":0.70}',
    '["收藏过安静咖啡馆","多次选择少走路路线","经常点击适合约会的餐厅","跳过排队超过30分钟的餐厅"]'
),
(
    'user_002', '阿航', '效率通勤型', '北京', 120,
    '["快餐","商场","咖啡","简餐"]',
    '{"少走路":0.92,"近地铁":0.88,"不用排队":0.82,"省时":0.80,"性价比":0.70}',
    '{"绕路":0.90,"等位久":0.85,"距离远":0.82}',
    '["多次点击少走路","收藏近地铁餐厅","经常选择2小时以内路线"]'
),
(
    'user_003', 'Mia', '探店内容型', '上海', 300,
    '["网红餐厅","甜品","买手店","咖啡"]',
    '{"出片":0.95,"新店":0.88,"热门":0.82,"高评分":0.80,"拍照好看":0.78}',
    '{"普通":0.85,"没特色":0.82,"环境一般":0.70}',
    '["收藏过多家网红甜品店","经常选择拍照出片路线","分享过探店路线卡片"]'
)
ON CONFLICT (user_id) DO NOTHING;

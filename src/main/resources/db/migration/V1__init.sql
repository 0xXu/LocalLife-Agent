CREATE TABLE IF NOT EXISTS app_healthcheck (
    id BIGSERIAL PRIMARY KEY,
    service_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO app_healthcheck (service_name) VALUES ('ai-route-planner') ON CONFLICT DO NOTHING;

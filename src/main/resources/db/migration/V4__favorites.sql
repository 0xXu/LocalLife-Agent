CREATE TABLE IF NOT EXISTS favorites (
    id BIGSERIAL PRIMARY KEY,
    route_json TEXT NOT NULL,
    route_name VARCHAR(200),
    scene VARCHAR(100),
    poi_count INTEGER DEFAULT 0,
    total_time VARCHAR(50),
    total_cost INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

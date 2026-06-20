CREATE TABLE routes (
    id VARCHAR(50) PRIMARY KEY,
    session_id VARCHAR(50) NOT NULL,
    name VARCHAR(200),
    description TEXT,
    segments_json TEXT NOT NULL,
    total_cost DOUBLE PRECISION DEFAULT 0,
    total_travel_time DOUBLE PRECISION DEFAULT 0,
    total_rating DOUBLE PRECISION DEFAULT 0,
    optimization_goal VARCHAR(50),
    score DOUBLE PRECISION DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_routes_session_id ON routes(session_id);

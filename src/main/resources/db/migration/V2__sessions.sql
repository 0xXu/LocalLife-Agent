CREATE TABLE sessions (
    id VARCHAR(50) PRIMARY KEY,
    intent_json TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE session_snapshots (
    id BIGSERIAL PRIMARY KEY,
    session_id VARCHAR(50) NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    route_json TEXT NOT NULL,
    intent_json TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_snapshots_session_id ON session_snapshots(session_id);
CREATE INDEX idx_snapshots_version ON session_snapshots(session_id, version);

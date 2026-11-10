-- STRIX auth events and IP intelligence schema

CREATE TABLE IF NOT EXISTS auth_events (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ NOT NULL,
    ip INET NOT NULL,
    username TEXT NOT NULL DEFAULT '',
    event_type TEXT NOT NULL,
    is_invalid_user BOOLEAN NOT NULL DEFAULT FALSE,
    port INTEGER,
    source_file TEXT NOT NULL DEFAULT '',
    CONSTRAINT auth_events_dedup UNIQUE (ts, ip, username, port, event_type)
);

CREATE INDEX IF NOT EXISTS idx_auth_events_ts ON auth_events (ts);
CREATE INDEX IF NOT EXISTS idx_auth_events_ip ON auth_events (ip);
CREATE INDEX IF NOT EXISTS idx_auth_events_event_type ON auth_events (event_type);

CREATE TABLE IF NOT EXISTS ip_intel (
    ip INET PRIMARY KEY,
    country TEXT,
    country_code TEXT,
    city TEXT,
    region TEXT,
    lat DOUBLE PRECISION,
    lon DOUBLE PRECISION,
    org TEXT,
    is_malicious BOOLEAN NOT NULL DEFAULT FALSE,
    failed_count INTEGER NOT NULL DEFAULT 0,
    first_seen TIMESTAMPTZ,
    last_seen TIMESTAMPTZ,
    is_bot BOOLEAN NOT NULL DEFAULT FALSE
);

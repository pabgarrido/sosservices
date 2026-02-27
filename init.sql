-- SOS Services — Database Initialization
-- Run as part of PostgreSQL startup

-- Enable PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;

-- Events table
CREATE TABLE IF NOT EXISTS geo_events (
    id VARCHAR PRIMARY KEY,
    type VARCHAR NOT NULL,
    category VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    description TEXT,
    location GEOMETRY(POINT, 4326) NOT NULL,
    radius_km FLOAT,
    severity VARCHAR NOT NULL DEFAULT 'low',
    source VARCHAR NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    last_updated TIMESTAMP DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    active BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_events_type ON geo_events(type);
CREATE INDEX IF NOT EXISTS idx_events_source ON geo_events(source);
CREATE INDEX IF NOT EXISTS idx_events_active ON geo_events(active);
CREATE INDEX IF NOT EXISTS idx_events_location ON geo_events USING GIST(location);
CREATE INDEX IF NOT EXISTS idx_events_severity ON geo_events(severity);
CREATE INDEX IF NOT EXISTS idx_events_start_time ON geo_events(start_time);

-- Hazard alerts table
CREATE TABLE IF NOT EXISTS hazard_alerts (
    id VARCHAR PRIMARY KEY,
    level VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    description TEXT NOT NULL,
    location GEOMETRY(POINT, 4326) NOT NULL,
    radius_km FLOAT NOT NULL,
    contributing_events JSONB DEFAULT '[]',
    recommended_action TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_alerts_level ON hazard_alerts(level);
CREATE INDEX IF NOT EXISTS idx_alerts_location ON hazard_alerts USING GIST(location);
CREATE INDEX IF NOT EXISTS idx_alerts_created ON hazard_alerts(created_at);

-- Spatial query helper: find events within radius
CREATE OR REPLACE FUNCTION events_within_radius(
    center_lat DOUBLE PRECISION,
    center_lng DOUBLE PRECISION,
    radius_meters DOUBLE PRECISION
)
RETURNS SETOF geo_events AS $$
BEGIN
    RETURN QUERY
    SELECT *
    FROM geo_events
    WHERE active = TRUE
    AND ST_DWithin(
        location::geography,
        ST_SetSRID(ST_MakePoint(center_lng, center_lat), 4326)::geography,
        radius_meters
    );
END;
$$ LANGUAGE plpgsql;

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS pois (
  id text PRIMARY KEY,
  name text NOT NULL,
  category text NOT NULL,
  location geography(Point, 4326) NOT NULL,
  distance_km numeric NOT NULL,
  open_hours jsonb NOT NULL,
  rating numeric NOT NULL,
  review_count integer NOT NULL,
  avg_price integer NOT NULL,
  tags text[] NOT NULL,
  wait_minutes integer NOT NULL,
  booking_supported boolean NOT NULL,
  availability jsonb NOT NULL,
  source text NOT NULL,
  reason text NOT NULL,
  risk_tags text[] NOT NULL,
  supported_scenarios text[] NOT NULL,
  audience text[] NOT NULL,
  district text NOT NULL,
  menu_summary text NOT NULL,
  review_summary text NOT NULL,
  capacity integer NOT NULL DEFAULT 0,
  min_child_age integer NOT NULL DEFAULT 0,
  max_party_size integer NOT NULL DEFAULT 1,
  embedding vector(1536)
);

CREATE TABLE IF NOT EXISTS coupons (
  id text PRIMARY KEY,
  poi_id text NOT NULL REFERENCES pois(id),
  title text NOT NULL,
  discount_type text NOT NULL,
  value numeric NOT NULL,
  valid_until timestamptz NOT NULL,
  rules text NOT NULL
);

CREATE TABLE IF NOT EXISTS menus (
  id text PRIMARY KEY,
  poi_id text NOT NULL REFERENCES pois(id),
  name text NOT NULL,
  price integer NOT NULL,
  tags text[] NOT NULL,
  allergens text[] NOT NULL,
  nutrition_note text NOT NULL
);

CREATE TABLE IF NOT EXISTS route_legs (
  id bigserial PRIMARY KEY,
  from_poi_id text NOT NULL,
  to_poi_id text NOT NULL,
  mode text NOT NULL,
  duration_minutes integer NOT NULL,
  distance_km numeric NOT NULL,
  polyline text NOT NULL,
  route_summary text NOT NULL,
  UNIQUE (from_poi_id, to_poi_id, mode)
);

CREATE TABLE IF NOT EXISTS failure_scenarios (
  id text PRIMARY KEY,
  type text NOT NULL,
  target_id text NOT NULL,
  trigger text NOT NULL,
  replacement_strategy text NOT NULL,
  user_message text NOT NULL
);

CREATE TABLE IF NOT EXISTS plans (
  id text PRIMARY KEY,
  thread_id text NOT NULL,
  status text NOT NULL,
  goal text NOT NULL,
  constraints jsonb NOT NULL,
  plan_response jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS checkpoints (
  thread_id text PRIMARY KEY,
  state jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS traces (
  id bigserial PRIMARY KEY,
  plan_id text NOT NULL,
  span_id text NOT NULL,
  agent text NOT NULL,
  tool text,
  message text NOT NULL,
  input_summary jsonb,
  output_summary jsonb,
  status text NOT NULL,
  started_at timestamptz NOT NULL DEFAULT now(),
  ended_at timestamptz
);

CREATE TABLE IF NOT EXISTS executions (
  id text PRIMARY KEY,
  plan_id text NOT NULL,
  tool text NOT NULL,
  status text NOT NULL,
  request jsonb NOT NULL,
  response jsonb,
  receipt jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS idempotency_keys (
  key text PRIMARY KEY,
  scope text NOT NULL,
  request_hash text NOT NULL,
  response jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL
);

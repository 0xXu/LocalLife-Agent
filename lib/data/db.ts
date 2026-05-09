import { readFile } from 'node:fs/promises';

export type LocalLifeScenario = 'family' | 'friends' | 'date' | 'rainy_indoor';

export type PoiCategory =
  | 'family_activity'
  | 'social_activity'
  | 'date_activity'
  | 'indoor_activity'
  | 'restaurant'
  | 'dessert_walk'
  | 'citywalk';

export type Availability = {
  default?: boolean;
  slots?: Array<{ time: string; available: boolean; remaining?: number }>;
  blackout_times?: string[];
};

export type Poi = {
  id: string;
  name: string;
  category: PoiCategory;
  lat: number;
  lng: number;
  distance_km: number;
  open_hours: Record<string, string[]>;
  rating: number;
  review_count: number;
  avg_price: number;
  tags: string[];
  wait_minutes: number;
  booking_supported: boolean;
  availability: Availability;
  source: string;
  reason: string;
  risk_tags: string[];
  supported_scenarios: LocalLifeScenario[];
  audience: string[];
  district: string;
  menu_summary: string;
  review_summary: string;
  capacity: number;
  min_child_age: number;
  max_party_size: number;
};

export type Coupon = {
  id: string;
  poi_id: string;
  title: string;
  discount_type: 'percent' | 'amount' | 'bundle' | 'percent_off' | 'amount_off' | 'package_price';
  value: number;
  valid_until: string;
  rules: string;
};

export type MenuItem = {
  id: string;
  poi_id: string;
  name: string;
  price: number;
  tags: string[];
  allergens: string[];
  nutrition_note: string;
};

export type RouteLeg = {
  from: string;
  to: string;
  mode: 'walk' | 'taxi' | 'transit' | 'subway' | 'bus';
  duration_minutes: number;
  distance_km: number;
  polyline: string;
  route_summary: string;
};

export type FailureScenario = {
  id: string;
  type: string;
  target_id: string;
  trigger: string;
  replacement_strategy: string;
  user_message: string;
};

export type AvailabilityResult = {
  place_id: string;
  available: boolean;
  wait_minutes: number;
  remaining_capacity: number;
  source: 'seed';
};

export async function readSeedFile<T>(fileName: string): Promise<T> {
  const url = new URL(`./seed/${fileName}`, import.meta.url);
  return JSON.parse(await readFile(url, 'utf8')) as T;
}

export function getDatabaseUrl(env: NodeJS.ProcessEnv = process.env) {
  return env.DATABASE_URL ?? env.POSTGRES_URL ?? '';
}

export async function createPostgresClient(databaseUrl = getDatabaseUrl()) {
  if (!databaseUrl) {
    return null;
  }

  const postgres = (await import('postgres')).default;
  return postgres(databaseUrl);
}

export async function createPgPool(databaseUrl = getDatabaseUrl()) {
  if (!databaseUrl) {
    return null;
  }

  const pg = (await import('pg')) as { Pool: new (config: { connectionString: string }) => unknown };
  return new pg.Pool({ connectionString: databaseUrl });
}

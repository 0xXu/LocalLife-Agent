export type RoutePoint = {
  id?: string;
  lat: number;
  lng: number;
};

export type RouteMode = 'walk_taxi' | 'taxi' | 'walk';

export type RouteProviderInput = {
  origin: RoutePoint;
  waypoints: RoutePoint[];
  mode: RouteMode;
};

export type RouteLeg = {
  from: string;
  to: string;
  mode: 'walk' | 'taxi' | 'transit';
  duration_minutes: number;
  distance_km: number;
  route_summary: string;
};

export type RouteProviderResult = {
  legs: RouteLeg[];
  total_travel_minutes: number;
  walking_distance_km: number;
  drive_time_minutes: number;
  polyline: { type: 'LineString'; coordinates: Array<[number, number]> };
  provider: 'local' | 'amap' | 'google';
};

export type RouteProvider = {
  optimize(input: RouteProviderInput): Promise<RouteProviderResult>;
};

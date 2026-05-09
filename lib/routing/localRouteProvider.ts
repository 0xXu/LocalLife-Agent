import type { RouteProvider, RouteProviderInput, RouteProviderResult } from './routeProvider';

export const localRouteProvider: RouteProvider = {
  async optimize(input: RouteProviderInput): Promise<RouteProviderResult> {
    const points = [input.origin, ...input.waypoints];
    const legs = points.slice(0, -1).map((from, index) => {
      const to = points[index + 1];
      const distance = haversineKm(from.lat, from.lng, to.lat, to.lng);
      const mode = legMode(input.mode, index);
      const speed = mode === 'walk' ? 4.5 : 22;
      const duration = Math.max(4, Math.round(distance / speed * 60));
      return {
        from: from.id ?? (index === 0 ? 'origin' : `point_${index}`),
        to: to.id ?? `point_${index + 1}`,
        mode,
        duration_minutes: duration,
        distance_km: Number(distance.toFixed(2)),
        route_summary: mode === 'walk' ? '步行路段短，适合半日计划。' : '打车路段用于降低换乘和等待风险。',
      };
    });

    return {
      legs,
      total_travel_minutes: legs.reduce((total, leg) => total + leg.duration_minutes, 0),
      walking_distance_km: Number(legs.filter((leg) => leg.mode === 'walk').reduce((total, leg) => total + leg.distance_km, 0).toFixed(2)),
      drive_time_minutes: legs.filter((leg) => leg.mode === 'taxi').reduce((total, leg) => total + leg.duration_minutes, 0),
      polyline: { type: 'LineString', coordinates: points.map((point) => [point.lng, point.lat]) },
      provider: 'local',
    };
  },
};

function legMode(mode: RouteProviderInput['mode'], index: number) {
  if (mode === 'walk') {
    return 'walk' as const;
  }
  if (mode === 'taxi') {
    return 'taxi' as const;
  }
  return index === 0 ? 'taxi' as const : 'walk' as const;
}

function haversineKm(lat1: number, lng1: number, lat2: number, lng2: number) {
  const radius = 6371;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return 2 * radius * Math.asin(Math.sqrt(a));
}

function toRad(value: number) {
  return value * Math.PI / 180;
}

import React from 'react';
import type { RouteProviderResult } from '../../lib/routing/routeProvider';

type RouteMapProps = {
  route?: RouteProviderResult | null;
  mapboxToken?: string;
};

export function RouteMap({ route, mapboxToken = process.env.NEXT_PUBLIC_MAPBOX_TOKEN ?? '' }: RouteMapProps) {
  const safeRoute = route ?? fallbackRoute;

  if (!mapboxToken) {
    return (
      <section className="route-map route-map-fallback" data-map-fallback="true" aria-label="地图与路线">
        <h2>地图与路线</h2>
        <svg viewBox="0 0 320 220" role="img" aria-label="路线预览">
          <polyline points={toSvgPoints(safeRoute.polyline.coordinates)} fill="none" stroke="#0563c9" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
          {safeRoute.polyline.coordinates.map((point, index) => {
            const [x, y] = coordinateToSvg(point, safeRoute.polyline.coordinates);
            return <circle key={`${point[0]}_${point[1]}_${index}`} cx={x} cy={y} r={index === 0 ? 7 : 6} fill={index === 0 ? '#0f8a65' : '#dd6c2f'} />;
          })}
        </svg>
        <dl>
          <div><dt>总路程时间</dt><dd>{safeRoute.total_travel_minutes} 分钟</dd></div>
          <div><dt>步行距离</dt><dd>{safeRoute.walking_distance_km} 公里</dd></div>
          <div><dt>路线来源</dt><dd>{safeRoute.provider}</dd></div>
        </dl>
      </section>
    );
  }

  return (
    <section className="route-map" data-mapbox="true" aria-label="地图与路线">
      <h2>地图与路线</h2>
      <div className="mapbox-placeholder">Mapbox route layer ready</div>
    </section>
  );
}

const fallbackRoute: RouteProviderResult = {
  legs: [],
  total_travel_minutes: 0,
  walking_distance_km: 0,
  drive_time_minutes: 0,
  polyline: { type: 'LineString', coordinates: [[140.8824, 38.2601], [140.881, 38.261], [140.884, 38.263]] },
  provider: 'local',
};

function toSvgPoints(coordinates: Array<[number, number]>) {
  return coordinates.map((point) => coordinateToSvg(point, coordinates).join(',')).join(' ');
}

function coordinateToSvg(point: [number, number], coordinates: Array<[number, number]>): [number, number] {
  const lngs = coordinates.map(([lng]) => lng);
  const lats = coordinates.map(([, lat]) => lat);
  const minLng = Math.min(...lngs);
  const maxLng = Math.max(...lngs);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const x = 28 + ((point[0] - minLng) / Math.max(maxLng - minLng, 0.0001)) * 264;
  const y = 192 - ((point[1] - minLat) / Math.max(maxLat - minLat, 0.0001)) * 164;
  return [Math.round(x), Math.round(y)];
}

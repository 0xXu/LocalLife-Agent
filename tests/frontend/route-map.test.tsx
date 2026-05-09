import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import { RouteMap } from '../../components/map/RouteMap';

test('route map renders deterministic fallback when map token is missing', () => {
  const html = renderToStaticMarkup(<RouteMap route={makeRouteFixture()} mapboxToken="" />);
  assert.match(html, /地图与路线/);
  assert.match(html, /data-map-fallback="true"/);
});

function makeRouteFixture() {
  return {
    legs: [{ from: 'home', to: 'a_021', mode: 'walk', duration_minutes: 8, distance_km: 0.6, route_summary: '步行到活动点' }],
    total_travel_minutes: 8,
    walking_distance_km: 0.6,
    drive_time_minutes: 0,
    polyline: { type: 'LineString', coordinates: [[140.8824, 38.2601], [140.881, 38.261]] },
    provider: 'local',
  };
}

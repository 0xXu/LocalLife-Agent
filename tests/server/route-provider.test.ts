import test from 'node:test';
import assert from 'node:assert/strict';

import { localRouteProvider } from '../../lib/routing/localRouteProvider';

test('local route provider returns legs, total minutes, walking distance, and map polyline', async () => {
  const result = await localRouteProvider.optimize({
    origin: { lat: 38.2601, lng: 140.8824 },
    waypoints: [
      { id: 'a_021', lat: 38.261, lng: 140.881 },
      { id: 'r_014', lat: 38.262, lng: 140.882 },
    ],
    mode: 'walk_taxi',
  });

  assert.ok(result.total_travel_minutes > 0);
  assert.ok(result.legs.length >= 1);
  assert.ok(result.polyline.coordinates.length >= 2);
});

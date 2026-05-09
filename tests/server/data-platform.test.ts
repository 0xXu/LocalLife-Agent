import test from 'node:test';
import assert from 'node:assert/strict';

import { loadSeedCoupons, searchCouponsByPoi } from '../../lib/data/repositories/couponRepository';
import { checkAvailability } from '../../lib/data/repositories/availabilityRepository';
import { loadSeedFailureScenarios } from '../../lib/data/repositories/failureScenarioRepository';
import { loadSeedMenus, searchMenuByPoi } from '../../lib/data/repositories/menuRepository';
import { getPoi, loadSeedPois, searchPois } from '../../lib/data/repositories/poiRepository';
import { getRouteLegs, loadSeedRoutes } from '../../lib/data/repositories/routeRepository';

test('seed catalog has 80 to 120 high-quality local POIs and required coverage', async () => {
  const pois = await loadSeedPois();
  assert.ok(pois.length >= 80 && pois.length <= 120);
  assert.ok(pois.filter((poi) => poi.category === 'restaurant').length >= 24);
  assert.ok(pois.filter((poi) => poi.category === 'family_activity').length >= 16);
  assert.ok(pois.filter((poi) => poi.category === 'social_activity').length >= 16);
  assert.ok(pois.filter((poi) => poi.category === 'date_activity').length >= 12);
  assert.ok(pois.filter((poi) => poi.category === 'indoor_activity').length >= 12);
  assert.ok(pois.filter((poi) => poi.category === 'dessert_walk' || poi.category === 'citywalk').length >= 12);
  assert.ok(pois.some((poi) => poi.supported_scenarios.includes('family')));
  assert.ok(pois.some((poi) => poi.supported_scenarios.includes('friends')));
  assert.ok(pois.some((poi) => poi.supported_scenarios.includes('date')));
  assert.ok(pois.some((poi) => poi.supported_scenarios.includes('rainy_indoor')));

  for (const poi of pois) {
    assert.ok(poi.id);
    assert.ok(poi.source);
    assert.ok(poi.review_summary.length >= 12);
    assert.ok(poi.menu_summary.length >= 8);
    assert.ok(poi.audience.length >= 1);
    assert.ok(poi.district.length >= 1);
  }
});

test('coupon and menu seeds meet commercial loop requirements', async () => {
  const coupons = await loadSeedCoupons();
  const menus = await loadSeedMenus();
  assert.ok(coupons.length >= 20);
  assert.ok(menus.some((item) => item.tags.includes('low_fat')));
  assert.ok(menus.some((item) => item.tags.includes('low_sugar')));
  assert.ok(coupons.every((coupon) => coupon.rules.includes('退款') || coupon.rules.includes('核销')));
  assert.ok((await loadSeedFailureScenarios()).length >= 5);
});

test('JSON repositories support search, lookup, menu, coupon, route, and availability reads', async () => {
  const restaurants = await searchPois({ category: 'restaurant', scenario: 'family', radiusKm: 5, tags: ['low_fat'] });
  assert.ok(restaurants.length > 0);
  assert.ok(restaurants.every((poi) => poi.category === 'restaurant'));
  assert.ok(restaurants.every((poi) => poi.distance_km <= 5));

  const allCoupons = await loadSeedCoupons();
  const couponPoiId = allCoupons.find((coupon) => restaurants.some((poi) => poi.id === coupon.poi_id))?.poi_id ?? allCoupons[0].poi_id;
  const poi = await getPoi(couponPoiId);
  assert.equal(poi.id, couponPoiId);

  const coupons = await searchCouponsByPoi(poi.id);
  const menu = await searchMenuByPoi(poi.id);
  assert.ok(coupons.length >= 1);
  assert.ok(menu.length >= 1);

  const routes = await loadSeedRoutes();
  const legs = await getRouteLegs([routes[0].from, routes[0].to]);
  assert.equal(legs.length, 1);
  assert.equal(legs[0].from, routes[0].from);

  const availability = await checkAvailability({ placeId: poi.id, time: '18:10', partySize: 3 });
  assert.equal(availability.place_id, poi.id);
  assert.equal(typeof availability.available, 'boolean');
  assert.equal(typeof availability.wait_minutes, 'number');
});

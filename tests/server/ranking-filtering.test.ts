import test from 'node:test';
import assert from 'node:assert/strict';

import { hardFilterCandidates } from '../../lib/planning/filtering';
import { buildVariants, scorePoi } from '../../lib/planning/ranking';

test('scorePoi applies detailed design weights exactly', () => {
  const score = scorePoi({
    distance_score: 1,
    rating_score: 1,
    constraint_fit_score: 1,
    availability_score: 1,
    route_efficiency_score: 1,
    budget_score: 1,
    novelty_or_vibe_score: 1,
  });
  assert.equal(score, 100);

  const weighted = scorePoi({
    distance_score: 0.5,
    rating_score: 0.6,
    constraint_fit_score: 0.7,
    availability_score: 0.8,
    route_efficiency_score: 0.9,
    budget_score: 1,
    novelty_or_vibe_score: 0.4,
  });
  assert.equal(weighted, Math.round((0.22 * 0.5 + 0.18 * 0.6 + 0.16 * 0.7 + 0.14 * 0.8 + 0.12 * 0.9 + 0.10 * 1 + 0.08 * 0.4) * 100));
});

test('hardFilter removes closed, too far, wrong age, capacity mismatch, and excessive wait candidates', () => {
  const kept = hardFilterCandidates(makeFilterFixture(), {
    date: '2026-05-09',
    time: '14:00',
    radiusKm: 5,
    childAges: [5],
    partySize: 3,
    maxWaitMinutes: 15,
  });

  assert.deepEqual(kept.map((poi) => poi.id), ['poi_good']);
  assert.deepEqual(kept.rejected.map((item) => item.reason), [
    'closed_at_requested_time',
    'outside_radius',
    'age_mismatch',
    'capacity_mismatch',
    'wait_exceeds_threshold',
  ]);
});

test('buildVariants produces different main, budget, comfort, and child-first plans', () => {
  const variants = buildVariants(makeRankedFixture(), makeFamilyConstraints());
  assert.deepEqual(variants.map((variant) => variant.kind), ['main', 'budget', 'comfort', 'child_first']);
  assert.notDeepEqual(variants[0].itinerary.map((step) => step.place_id), variants[1].itinerary.map((step) => step.place_id));
  assert.ok(variants[1].estimated_budget < variants[0].estimated_budget);
});

function makeFilterFixture() {
  const base = {
    name: '',
    category: 'family_activity',
    lat: 38.26,
    lng: 140.88,
    rating: 4.6,
    review_count: 100,
    avg_price: 1000,
    tags: ['child_friendly'],
    booking_supported: true,
    availability: { slots: [{ time: '14:00', available: true, remaining_capacity: 6 }] },
    source: 'fixture',
    reason: 'fixture reason',
    risk_tags: [],
    supported_scenarios: ['family'],
    audience: ['family'],
    district: 'Aoba',
    menu_summary: '低脂菜单',
    review_summary: '亲子评价稳定',
    capacity: 8,
    min_child_age: 0,
    max_party_size: 6,
  };

  return [
    { ...base, id: 'poi_good', name: 'Good', distance_km: 2, wait_minutes: 5, open_hours: { saturday: { start: '10:00', end: '20:00' } } },
    { ...base, id: 'poi_closed', name: 'Closed', distance_km: 2, wait_minutes: 5, open_hours: { saturday: { start: '16:00', end: '20:00' } } },
    { ...base, id: 'poi_far', name: 'Far', distance_km: 8, wait_minutes: 5, open_hours: { saturday: { start: '10:00', end: '20:00' } } },
    { ...base, id: 'poi_age', name: 'Age', distance_km: 2, wait_minutes: 5, min_child_age: 7, open_hours: { saturday: { start: '10:00', end: '20:00' } } },
    { ...base, id: 'poi_capacity', name: 'Capacity', distance_km: 2, wait_minutes: 5, max_party_size: 2, open_hours: { saturday: { start: '10:00', end: '20:00' } } },
    { ...base, id: 'poi_wait', name: 'Wait', distance_km: 2, wait_minutes: 40, open_hours: { saturday: { start: '10:00', end: '20:00' } } },
  ];
}

function makeRankedFixture() {
  return {
    activities: [
      ranked('activity_main', '科学馆探索', 'family_activity', 92, 1800),
      ranked('activity_budget', '公园自然观察', 'family_activity', 84, 500),
      ranked('activity_child', '儿童绘本工坊', 'family_activity', 88, 1200, ['child_friendly']),
    ],
    restaurants: [
      ranked('restaurant_main', '健康轻食餐厅', 'restaurant', 91, 3600),
      ranked('restaurant_budget', '家庭定食屋', 'restaurant', 83, 1800),
      ranked('restaurant_comfort', '安静包间餐厅', 'restaurant', 87, 4200, ['quiet']),
    ],
    walks: [
      ranked('walk_main', '河畔低糖散步', 'dessert_walk', 89, 900),
      ranked('walk_budget', '商店街轻散步', 'dessert_walk', 80, 300),
      ranked('walk_child', '儿童书店收尾', 'dessert_walk', 86, 600, ['child_friendly']),
    ],
  };
}

function ranked(id: string, name: string, category: string, score: number, avgPrice: number, tags: string[] = []) {
  return {
    id,
    name,
    category,
    score,
    avg_price: avgPrice,
    tags,
    reason: `${name}符合当前约束`,
    factors: {
      distance_score: 0.9,
      rating_score: 0.9,
      constraint_fit_score: 0.9,
      availability_score: 0.9,
      route_efficiency_score: 0.9,
      budget_score: Math.max(0.4, 1 - avgPrice / 6000),
      novelty_or_vibe_score: 0.8,
    },
  };
}

function makeFamilyConstraints() {
  return {
    scenario: 'family',
    origin: { type: 'current_location', label: 'home', lat: 38.2601, lng: 140.8824 },
    time_window: { date: '2026-05-09', start: '14:00', duration_hours: 4.5, flexible: true },
    people: { adults: 2, children: [{ age: 5 }], relationship: 'family' },
    preferences: { distance: 'nearby', diet: ['low_fat'], activity: ['child_friendly'], budget_level: 'medium' },
    constraints: { radius_km: 5, max_wait_minutes: 15, avoid: [] },
    required_actions: [],
  };
}

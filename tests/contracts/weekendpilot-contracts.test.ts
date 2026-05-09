import test from 'node:test';
import assert from 'node:assert/strict';
import {
  ParsedConstraintsSchema,
  PoiSchema,
  PlanResponseSchema,
  ReceiptSchema,
  RecoveryDiffSchema,
} from '../../lib/contracts/schemas';

test('ParsedConstraints accepts the detailed design family example', () => {
  const parsed = ParsedConstraintsSchema.parse({
    scenario: 'family',
    origin: { type: 'current_location', label: 'home', lat: 38.2601, lng: 140.8824 },
    time_window: { date: '2026-05-09', start: '14:00', duration_hours: 4.5, flexible: true },
    people: { adults: 2, children: [{ age: 5 }], relationship: 'family' },
    preferences: {
      distance: 'nearby',
      diet: ['low_fat', 'low_sugar'],
      activity: ['child_friendly', 'not_too_tiring'],
      budget_level: 'medium',
    },
    constraints: { radius_km: 5, max_wait_minutes: 15, avoid: ['heavy_oil', 'long_queue', 'smoking'] },
    required_actions: ['activity_reservation', 'restaurant_reservation', 'send_plan_message'],
  });

  assert.equal(parsed.people.children[0].age, 5);
});

test('ParsedConstraints uses rainy_indoor as the canonical rainy scenario id', () => {
  const parsed = ParsedConstraintsSchema.parse({
    scenario: 'rainy_indoor',
    origin: { type: 'current_location', label: 'home', lat: 38.2601, lng: 140.8824 },
    time_window: { date: '2026-05-09', start: '13:30', duration_hours: 4.5, flexible: true },
    people: { adults: 2, children: [], relationship: 'friends' },
    preferences: {
      distance: 'nearby',
      diet: [],
      activity: ['indoor', 'rain_safe'],
      budget_level: 'medium',
    },
    constraints: { radius_km: 5, max_wait_minutes: 15, avoid: ['outdoor'] },
    required_actions: ['activity_reservation', 'restaurant_reservation'],
  });

  assert.equal(parsed.scenario, 'rainy_indoor');
});

test('POI requires source, place id, availability, rating, review count, and risk fields', () => {
  const poi = PoiSchema.parse({
    id: 'r_014',
    name: 'Green Table',
    category: 'restaurant',
    lat: 38.2618,
    lng: 140.8791,
    distance_km: 2.4,
    open_hours: [{ day: 'sat', start: '11:00', end: '21:00' }],
    rating: 4.6,
    review_count: 1260,
    avg_price: 1800,
    tags: ['healthy', 'child_seat', 'low_fat', 'quiet'],
    wait_minutes: 8,
    booking_supported: true,
    availability: [{ time: '18:10', available: true, capacity: 4 }],
    supported_scenarios: ['family'],
    source: 'seed_verified',
    reason: '低脂套餐和儿童座椅都可用。',
    risk_tags: ['weekend_queue'],
    audience: ['family'],
    district: 'Aoba',
    menu_summary: '低脂套餐、儿童餐、低糖饮品',
    review_summary: '家庭用户评价稳定，等待时间较短。',
  });

  assert.equal(poi.source, 'seed_verified');
});

test('PlanResponse contains variants, tool calls, constraint fit, actions, and receipts surface', () => {
  const response = PlanResponseSchema.parse({
    constraints: {
      scenario: 'family',
      origin: { type: 'current_location', label: 'home', lat: 38.2601, lng: 140.8824 },
      time_window: { date: '2026-05-09', start: '14:00', duration_hours: 4.5, flexible: true },
      people: { adults: 2, children: [{ age: 5 }], relationship: 'family' },
      preferences: { distance: 'nearby', diet: ['low_fat'], activity: ['child_friendly'], budget_level: 'medium' },
      constraints: { radius_km: 5, max_wait_minutes: 15, avoid: ['long_queue'] },
      required_actions: ['activity_reservation'],
    },
    progress: [],
    trace: [],
    tool_calls: [{
      tool: 'check_availability',
      input_summary: { place_id: 'r_014', time: '18:00', party_size: 3 },
      output_summary: { available: true, slot: '18:10' },
      status: 'ok',
      duration_ms: 90,
      side_effect: false,
    }],
    pending_actions: [],
    plan: {
      id: 'plan_contract_001',
      status: 'pending_confirmation',
      title: '亲子科学馆 + 健康轻食半日计划',
      summary: '亲子活动、健康轻食、饭后散步和确认后执行回执。',
      constraint_fit: { distance: 0.95, child_friendly: 1, diet: 0.9, time: 0.92, budget: 0.86 },
      itinerary: [],
      overview: { theme: '下午 · 家庭 · 健康轻松', totalDuration: '4.5 小时', driveTime: '约 25 分钟', walkingDistance: '1.2 公里', estimatedCost: '约 7200 元', score: 91 },
      actions: [],
      variants: [],
    },
  });

  assert.equal(response.plan.constraint_fit.distance, 0.95);
});

test('Receipt and RecoveryDiff match execution and recovery contract', () => {
  const receipt = ReceiptSchema.parse({
    type: 'restaurant_reservation',
    tool: 'create_reservation',
    id: 'RES-20260509-3812',
    status: 'confirmed',
    detail: '已预订 Green Table 18:10 的 3 人桌。',
    payload: { place_id: 'r_014', party_size: 3 },
  });
  const diff = RecoveryDiffSchema.parse({
    changed: 'restaurant',
    reason: 'restaurant_unavailable',
    from: 'Green Table',
    to: 'Light Bowl',
    costDelta: '+约 40 元',
    travelDelta: '+步行 2 分钟',
    preserved: ['亲子科学馆', '河畔低糖甜品散步'],
  });

  assert.match(receipt.id, /^RES-/);
  assert.deepEqual(diff.preserved, ['亲子科学馆', '河畔低糖甜品散步']);
});

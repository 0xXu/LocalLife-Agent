import test from 'node:test';
import assert from 'node:assert/strict';
import {
  ClarificationResponseSchema,
  ParsedConstraintsSchema,
  PoiSchema,
  PlanResponseSchema,
  PlanRevisionResponseSchema,
  ReceiptSchema,
  RecoveryDiffSchema,
} from '../../lib/contracts/schemas';
import {
  ApproveActionsRequestSchema,
  ClarificationRequiredPayloadSchema,
  CreateRunRequestSchema,
  CreateRunResponseSchema,
  RejectRunRequestSchema,
  RunEventEnvelopeSchema,
  RunEventTypeSchema,
  RunStatusResponseSchema,
  RunStatusSchema,
} from '../../features/runs/schemas';

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

test('ParsedConstraints accepts open-domain scenario labels from the LLM', () => {
  const parsed = ParsedConstraintsSchema.parse({
    scenario: 'pet_friendly_walk',
    origin: { type: 'current_location', label: 'home', lat: 38.26, lng: 140.88 },
    time_window: { date: 'today', start: '14:00', duration_hours: 2, flexible: true },
    people: { adults: 1, children: [], relationship: 'solo' },
    preferences: {
      distance: 'nearby',
      diet: [],
      activity: ['pet', 'walkable'],
      budget_level: 'low',
      intent_label: '宠物散步',
    },
    constraints: { radius_km: 5, max_wait_minutes: 15, avoid: [] },
    required_actions: ['send_plan_message'],
  });

  assert.equal(parsed.scenario, 'pet_friendly_walk');
  assert.equal((parsed.preferences as any).intent_label, '宠物散步');
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
    supported_scenarios: ['pet_friendly_walk', 'family'],
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

test('PlanResponse accepts the open-domain Python backend response contract', () => {
  const response = PlanResponseSchema.parse({
    constraints: {
      scenario: 'pet_friendly_walk',
      origin: { type: 'current_location', label: 'home', lat: 38.2601, lng: 140.8824 },
      time_window: { date: 'today', start: '14:00', duration_hours: 3, flexible: true },
      people: { adults: 1, children: [], relationship: 'solo' },
      preferences: {
        distance: 'nearby',
        diet: [],
        activity: ['pet', 'outdoor', 'walkable'],
        budget_level: 'medium',
        intent_label: '宠物散步',
      },
      constraints: { radius_km: 8, max_wait_minutes: 15, avoid: ['long_queue'] },
      required_actions: ['send_plan_message', 'create_calendar_event'],
    },
    progress: [],
    trace: [],
    tool_calls: [],
    route: {
      legs: [],
      total_travel_minutes: 0,
      walking_distance_km: 0,
      drive_time_minutes: 12,
      polyline: { type: 'LineString', coordinates: [[140.8791, 38.2618], [140.8811, 38.2638]] },
      provider: 'local_seed_route_matrix',
    },
    pending_actions: [{
      id: 'send_plan_message_同行人',
      type: 'message',
      tool: 'send_plan_message',
      label: '发送计划',
      target: '同行人',
      detail: '发送时间轴、路线和预算摘要。',
      requires_confirmation: true,
      requiresConfirmation: true,
      payload: { recipient: '同行人' },
    }],
    plan: {
      id: 'plan_open_001',
      status: 'pending_confirmation',
      title: '宠物散步短计划',
      summary: '围绕“宠物散步”选择本地供给，按时间、距离、预算和可执行动作生成计划。',
      constraint_fit: { distance: 0.95, time: 1, budget: 0.92 },
      itinerary: [{
        start: '14:00',
        end: '15:50',
        type: 'activity',
        title: '宠物友好河岸公园1号店',
        place_id: 'poi_007',
        reason: '允许牵绳宠物进入。',
        cost: '约 325 元',
        travel: '到达活动点',
        score: 95,
        risk: '风险低。',
      }],
      overview: { theme: '下午 · pet friendly walk · 可执行', totalDuration: '3 小时', driveTime: '约 12 分钟', walkingDistance: '0.0 公里', estimatedCost: '约 325 元', score: 98 },
      actions: [],
      variants: [{
        id: 'variant_main',
        kind: 'main',
        title: '主方案',
        summary: '综合距离、可订性和偏好匹配。',
        score: 98,
        estimated_budget: 325,
        constraint_fit: { distance: 0.95, time: 1, budget: 0.92 },
        itinerary: [],
      }],
      receipts: [],
      badges: ['宠物散步', 'pet', 'outdoor', '轻量短计划'],
    },
  });

  assert.equal(response.route?.provider, 'local_seed_route_matrix');
  assert.equal(response.plan.itinerary[0].risk, '风险低。');
  assert.equal(response.pending_actions[0].requires_confirmation, true);
});

test('PlanResponse exposes candidate sets with score breakdowns', () => {
  const response = PlanResponseSchema.parse({
    constraints: {
      scenario: 'pet_friendly_walk',
      origin: { type: 'current_location', label: 'home', lat: 38.26, lng: 140.88 },
      time_window: { date: 'today', start: '14:00', duration_hours: 2, flexible: true },
      people: { adults: 1, children: [], relationship: 'solo' },
      preferences: { distance: 'nearby', diet: [], activity: ['pet'], budget_level: 'medium' },
      constraints: { radius_km: 8, max_wait_minutes: 15, avoid: [] },
      required_actions: ['send_plan_message'],
    },
    progress: [],
    trace: [],
    tool_calls: [],
    candidate_sets: {
      activities: [{
        place: {
          id: 'poi_007',
          name: '宠物友好河岸公园',
          provenance: { source: 'local_seed_catalog', freshness: 'seed_static', confidence: 0.9 },
        },
        total_score: 0.86,
        score_breakdown: { semantic: 0.27, distance: 0.18, quality: 0.19, wait: 0.1, budget: 0.12 },
        explanation: '偏好匹配高。',
      }],
    },
    rejected_candidates: {},
    user_profile: {
      user_id: 'user_1',
      explicit_preferences: [{ key: 'pace', value: 'slow', source: 'explicit', confidence: 1, scope: 'long_term', evidence: '用户主动选择慢节奏' }],
      learned_preferences: [],
      session_preferences: [],
    },
    itinerary: [],
    pending_actions: [],
    plan: {
      id: 'plan_1',
      status: 'pending_confirmation',
      title: '宠物散步短计划',
      summary: '本地生活计划',
      constraint_fit: { distance: 0.9, time: 1, budget: 0.92 },
      itinerary: [],
      overview: { theme: '下午', totalDuration: '2 小时', driveTime: '约 12 分钟', walkingDistance: '0 公里', estimatedCost: '约 120 元', score: 90 },
      actions: [],
      variants: [],
    },
  });

  assert.equal((response as any).candidate_sets.activities[0].place.provenance.source, 'local_seed_catalog');
  assert.equal(response.user_profile?.explicit_preferences[0].key, 'pace');
});

test('PlanResponse accepts persisted run workflow payloads with durable action ids', () => {
  const constraints = {
    scenario: 'family',
    origin: { type: 'district', label: 'home', lat: 31.2, lng: 121.5 },
    time_window: { date: '2026-05-14', start: '14:00', duration_hours: 4, flexible: true },
    people: { adults: 2, children: [{ age: 5 }], relationship: 'family' },
    preferences: { distance: 'nearby', diet: [], activity: [], budget_level: 'medium' },
    constraints: { radius_km: 5, max_wait_minutes: 15, avoid: [] },
    required_actions: ['send_plan_message'],
  };
  const plan = {
    id: 'plan_test_001',
    status: 'pending_approval',
    title: '亲子半日计划',
    summary: '轻松安排',
    constraint_fit: { distance: 1, time: 1, budget: 1 },
    itinerary: [],
    overview: {
      theme: '家庭',
      totalDuration: '4 小时',
      driveTime: '约 20 分钟',
      walkingDistance: '1 公里',
      estimatedCost: '¥300',
      score: 88,
    },
    actions: [{
      action_id: 'act_msg_001',
      type: 'send_plan_message',
      tool: 'messaging',
      label: '发送计划',
      detail: '发送给同行人',
      status: 'pending',
      payload: {},
      requires_confirmation: true,
    }],
    receipts: [],
    badges: ['家庭'],
  };
  const response = PlanResponseSchema.parse({
    plan_id: 'plan_test_001',
    revision: {
      revision_id: 'rev_test_001',
      phase: 'pending_approval',
      version: 1,
      goal: 'family lunch',
      constraints,
      plan,
    },
    plan,
    actions: plan.actions,
    pending_actions: plan.actions,
    receipts: [],
    constraints,
  });

  assert.equal(response.plan_id, 'plan_test_001');
  assert.equal(response.revision?.phase, 'pending_approval');
  assert.equal(response.actions[0].action_id, 'act_msg_001');
  assert.equal(response.pending_actions[0].status, 'pending');
});

test('Run schemas accept create-run response and normalized SSE event payloads', () => {
  const request = CreateRunRequestSchema.parse({
    goal: 'Plan a family afternoon',
  });
  const started = CreateRunResponseSchema.parse({
    run_id: 'run_test_001',
    plan_id: 'plan_test_001',
    status: 'queued',
    events_url: '/api/runs/run_test_001/events',
  });
  const event = RunEventEnvelopeSchema.parse({
    type: 'approval.required',
    run_id: 'run_test_001',
    plan_id: 'plan_test_001',
    seq: 4,
    timestamp: '2026-06-19T00:00:00Z',
    payload: {
      status: 'approval_required',
      actions: [{ action_id: 'act_msg_001', status: 'pending' }],
    },
  });

  assert.equal(request.user_id, 'local_demo_user');
  assert.equal(started.run_id, 'run_test_001');
  assert.equal(started.events_url, '/api/runs/run_test_001/events');
  assert.equal(event.type, 'approval.required');
  assert.equal((event.payload.actions as Array<Record<string, unknown>>)[0].action_id, 'act_msg_001');
});

test('Run REST contract uses product statuses and run-id action endpoints', () => {
  assert.equal(RunEventTypeSchema.parse('run.completed'), 'run.completed');
  assert.equal(RunEventTypeSchema.parse('clarification.required'), 'clarification.required');
  assert.equal(RunStatusSchema.parse('approval_required'), 'approval_required');
  assert.throws(() => RunStatusSchema.parse('pending_approval'));

  const status = RunStatusResponseSchema.parse({
    run_id: 'run_test_001',
    plan_id: 'plan_test_001',
    status: 'running',
    current_agent: 'OpenAIAgentsRuntime',
    created_at: '2026-06-19T00:00:00Z',
    updated_at: '2026-06-19T00:00:01Z',
  });
  const approve = ApproveActionsRequestSchema.parse({
    action_ids: ['act_msg_001', 'act_calendar_001'],
  });
  const reject = RejectRunRequestSchema.parse({});

  assert.equal(status.current_agent, 'OpenAIAgentsRuntime');
  assert.deepEqual(approve.action_ids, ['act_msg_001', 'act_calendar_001']);
  assert.equal(reject.reason, 'user_rejected');
});

test('Run REST contract parses one-question clarification payloads', () => {
  const payload = ClarificationRequiredPayloadSchema.parse({
    question: {
      id: 'time_window',
      label: '今天下午大概几点开始？',
      kind: 'time',
      required: true,
      options: [{ label: '今天下午 2 点', value: '今天下午 2 点' }],
      allow_custom: true,
    },
    missing_fields: ['time_window'],
  });

  assert.equal(payload.question.id, 'time_window');
  assert.deepEqual(payload.partial_constraints, {});
  assert.throws(() => ClarificationRequiredPayloadSchema.parse({ question: [payload.question] }));
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

test('Plan revision response includes diff and learned preferences', () => {
  const response = PlanRevisionResponseSchema.parse({
    revision: {
      revision_id: 'rev_001',
      feedback_text: '太赶了，餐厅不想去了',
      constraint_updates: { pace: 'slow', meal_required: false },
    },
    diff: {
      kept: ['宠物友好河岸公园'],
      removed: [{ id: 'poi_019', title: '绿荫轻食餐厅', reason: 'user_feedback' }],
      added: [{ id: 'poi_008', title: '自习咖啡馆' }],
      changed_constraints: { pace: ['medium', 'slow'] },
    },
    learned_preferences: [{
      key: 'pace',
      value: 'slow',
      source: 'feedback',
      confidence: 0.72,
      scope: 'long_term',
      evidence: '太赶了',
      user_editable: true,
      sensitive: false,
    }],
  });

  assert.equal(response.revision.revision_id, 'rev_001');
});

test('ClarificationResponse represents underspecified goals', () => {
  const parsed = ClarificationResponseSchema.parse({
    status: 'needs_clarification',
    plan_id: 'plan_clarify_001',
    missing_fields: ['time_window', 'activity_intent'],
    clarifying_questions: [
      { field: 'time_window', question: '你想安排今天、周六还是周日？大概几小时？' },
      { field: 'activity_intent', question: '你更想户外走走、室内放松、吃饭聚会，还是亲子活动？' },
    ],
    trace: [],
    tool_calls: [],
  });

  assert.equal(parsed.status, 'needs_clarification');
});

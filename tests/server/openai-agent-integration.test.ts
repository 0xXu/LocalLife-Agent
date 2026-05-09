import test from 'node:test';
import assert from 'node:assert/strict';

import { parseConstraintsNode } from '../../lib/agent/nodes/parseConstraints';
import { explainRankedPoi } from '../../lib/agent/nodes/rankCandidates';

test('parseConstraints uses Responses structured JSON when configured', async () => {
  const fake = {
    responses: {
      create: async () => ({
        output_text: JSON.stringify({
          scenario: 'date',
          origin: { type: 'current_location', label: 'home', lat: 38.2601, lng: 140.8824 },
          time_window: { date: '2026-05-09', start: '15:00', duration_hours: 4.5, flexible: true },
          people: { adults: 2, children: [], relationship: 'date' },
          preferences: { distance: 'nearby', diet: [], activity: ['quiet', 'romantic'], budget_level: 'medium' },
          constraints: { radius_km: 5, max_wait_minutes: 15, avoid: ['long_queue'] },
          required_actions: ['restaurant_reservation', 'send_plan_message'],
        }),
      }),
    },
  };

  const result = await parseConstraintsNode(
    { thread_id: 'thread_openai_001', status: 'INPUT', goal: '下午想和对象约会，安静一点', clarifying_questions: [], receipts: [], pending_side_effects: [] },
    { openai: fake, responsesEnabled: true },
  );

  assert.equal(result.constraints?.scenario, 'date');
  assert.equal(result.openai_metadata?.llm_fallback, false);
});

test('parseConstraints falls back deterministically when Responses is disabled', async () => {
  const result = await parseConstraintsNode(
    { thread_id: 'thread_openai_002', status: 'INPUT', goal: '今天下午朋友4个人出去玩，14点开始，玩4.5小时', clarifying_questions: [], receipts: [], pending_side_effects: [] },
    { responsesEnabled: false },
  );

  assert.equal(result.constraints?.scenario, 'friends');
  assert.equal(result.openai_metadata?.llm_fallback, true);
});

test('rank explanation is grounded in score factors and never invents POI facts', async () => {
  const explanation = await explainRankedPoi({
    name: '绿荫轻食餐厅',
    factors: {
      distance_score: 0.95,
      rating_score: 0.92,
      constraint_fit_score: 0.9,
      availability_score: 1,
      route_efficiency_score: 0.88,
      budget_score: 0.86,
      novelty_or_vibe_score: 0.72,
    },
    facts: ['儿童座椅可用', '18:10 可订', '距离上一站步行 8 分钟'],
  });

  assert.deepEqual(explanation.top_reasons, ['儿童座椅可用', '18:10 可订', '距离上一站步行 8 分钟']);
  assert.equal(explanation.top_reasons.some((reason) => reason.includes('停车免费')), false);
  assert.ok(explanation.tradeoffs.length >= 1);
});

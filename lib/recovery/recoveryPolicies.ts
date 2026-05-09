import { preservedTitles, replaceFirstByType } from './recoveryDiff';

export const recoveryReasons = [
  'restaurant_unavailable',
  'activity_full',
  'rain',
  'route_timeout',
  'budget_overrun',
  'constraint_conflict',
  'tool_timeout',
] as const;

export type RecoveryReason = (typeof recoveryReasons)[number];

export function isRecoveryReason(reason: string): reason is RecoveryReason {
  return recoveryReasons.includes(reason as RecoveryReason);
}

export function applyRecoveryPolicy(current: Record<string, any>, reason: RecoveryReason) {
  const previous = current.plan;
  const itinerary = [...(current.plan.itinerary ?? [])];
  const base = {
    ...current,
    previous,
    plan: {
      ...current.plan,
      id: `${current.plan.id}_${reason}`,
      status: 'recovered_pending_confirmation',
    },
    adjustment: {
      requested_by: 'agent',
      reason,
      changes: [reason],
      requires_confirmation: true,
      payload: {},
    },
  };

  if (reason === 'restaurant_unavailable') {
    const nextItinerary = replaceFirstByType(itinerary, 'restaurant', {
      id: 'step_restaurant_recovered',
      place_id: 'restaurant_recovered',
      title: '可订健康餐厅',
      reason: '原餐厅临时无位，替换为可订且满足饮食约束的餐厅。',
    });
    return withPlan(base, nextItinerary, {
      changed: 'restaurant',
      reason: '原餐厅返回该时段无位。',
      from: firstTitle(itinerary, 'restaurant'),
      to: '可订健康餐厅',
      costDelta: '+约 40 元',
      travelDelta: '+步行 2 分钟',
      preserved: preservedTitles(itinerary, 'restaurant'),
    });
  }

  if (reason === 'activity_full') {
    const nextItinerary = replaceFirstByType(itinerary, 'family_activity', {
      id: 'step_activity_recovered',
      place_id: 'activity_recovered',
      title: '儿童绘本工坊',
      reason: '原活动名额已满，替换为同区域儿童友好活动。',
    });
    return withPlan(base, nextItinerary, {
      changed: 'activity',
      reason: '活动名额已满。',
      from: firstTitle(itinerary, 'family_activity'),
      to: '儿童绘本工坊',
      preserved: itinerary.filter((step) => step.type !== 'family_activity').map((step) => step.title),
    });
  }

  if (reason === 'rain') {
    const nextItinerary = itinerary.map((step) => ({
      ...step,
      risk: (step.risk ?? []).filter((item: string) => item !== '户外下雨'),
      title: step.type === 'dessert_walk' ? '室内甜品与书店收尾' : step.title,
      type: step.type === 'dessert_walk' ? 'indoor_activity' : step.type,
      reason: step.type === 'dessert_walk' ? '下雨时切换到室内节点，保留低糖甜品需求。' : step.reason,
    }));
    return withPlan(base, nextItinerary, {
      changed: 'weather',
      reason: '天气转雨，户外节点切换为室内。',
      preserved: nextItinerary.map((step) => step.title),
    }, { badges: [...(current.plan.badges ?? []), '雨天方案'] });
  }

  if (reason === 'route_timeout') {
    const removed = itinerary.at(-1);
    const nextItinerary = itinerary.slice(0, -1);
    return withPlan(base, nextItinerary, {
      changed: 'route',
      reason: '路线服务超时，删除低优先级收尾节点。',
      removed: removed ? [{ id: removed.id, title: removed.title, reason: 'route_timeout_low_priority' }] : [],
      preserved: nextItinerary.map((step) => step.title),
    });
  }

  if (reason === 'budget_overrun') {
    const nextItinerary = itinerary.map((step) => ({ ...step, reason: `${step.reason ?? ''} 已优先匹配券或低价替代。`.trim() }));
    const previousBudget = Number(current.plan.overview.estimated_budget_value ?? 9000);
    return withPlan(base, nextItinerary, {
      changed: 'budget',
      reason: '预算超出，切换为低价组合并优先使用团购券。',
      costDelta: `-${Math.round(previousBudget * 0.22)} 円`,
      preserved: nextItinerary.map((step) => step.title),
    }, {
      overview: {
        ...current.plan.overview,
        estimated_budget_value: Math.round(previousBudget * 0.78),
        estimatedCost: `约 ${Math.round(previousBudget * 0.78)} 円`,
      },
    });
  }

  if (reason === 'constraint_conflict') {
    return {
      ...withPlan(base, itinerary, {
        changed: 'constraints',
        reason: '健康、距离和可订性约束存在冲突。',
        preserved: itinerary.map((step) => step.title),
      }),
      alternatives: [
        { kind: 'healthy', title: '健康优先', tradeoff: '放宽距离，保留低脂低糖。' },
        { kind: 'relaxed', title: '轻松优先', tradeoff: '保留近距离，放宽部分饮食标签。' },
      ],
    };
  }

  const recovered = withPlan(base, itinerary, {
    changed: 'tool',
    reason: '工具调用超时，已重试一次后切换 fallback。',
    preserved: itinerary.map((step) => step.title),
  });
  return {
    ...recovered,
    trace: [
      ...(current.trace ?? []),
      { agent: 'Executor', tool: 'create_reservation', status: 'retrying', message: '工具超时，正在重试一次。', input_summary: {}, output_summary: {}, duration_ms: 120 },
      { agent: 'Executor', tool: 'create_reservation', status: 'fallback', message: '重试后进入 fallback 恢复策略。', input_summary: {}, output_summary: {}, duration_ms: 80 },
    ],
  };
}

function withPlan(base: Record<string, any>, itinerary: Array<Record<string, any>>, diff: Record<string, any>, planPatch: Record<string, any> = {}) {
  const next = {
    ...base,
    diff,
    plan: {
      ...base.plan,
      ...planPatch,
      itinerary,
      diff,
    },
    itinerary,
    trace: [...(base.trace ?? []), { agent: 'RecoveryAgent', tool: 'compare_alternatives', status: 'ok', message: diff.reason, input_summary: {}, output_summary: { changed: diff.changed } }],
  };
  return next;
}

function firstTitle(itinerary: Array<Record<string, any>>, type: string) {
  return itinerary.find((step) => step.type === type || step.category === type)?.title;
}

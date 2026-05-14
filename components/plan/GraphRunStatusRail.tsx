'use client';

import React from 'react';
import type { PlanResponse } from '../../types/weekendpilot';

const phaseLabels: Record<string, string> = {
  ready: '已就绪',
  pending_approval: '待审批',
  executing: '执行中',
  executed: '已执行',
  validation_failed: '需处理',
};

export function GraphRunStatusRail({ result }: { result: PlanResponse }) {
  const phase = String(result.revision?.phase ?? result.plan.status);
  const revisionId = result.revision?.revision_id ?? 'unversioned';
  const actionCount = ((result.actions?.length ? result.actions : result.plan.actions) ?? []).length;
  const validationLabel = phase === 'validation_failed' ? '需处理' : '已通过';

  return (
    <section className="graph-status-rail" aria-label="Graph run status">
      <div><span>状态</span><strong>{phaseLabels[phase] ?? phase}</strong></div>
      <div><span>版本</span><strong>{revisionId}</strong></div>
      <div><span>动作</span><strong>{actionCount}</strong></div>
      <div><span>校验</span><strong>{validationLabel}</strong></div>
    </section>
  );
}

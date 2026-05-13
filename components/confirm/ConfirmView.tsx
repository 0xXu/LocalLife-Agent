'use client';

import React from 'react';
import type { PlanResponse } from '../../types/weekendpilot';
import { ActionToggle } from './ActionToggle';
import { ExecuteButton } from './ExecuteButton';

type ConfirmViewProps = {
  result: PlanResponse;
  selectedActions: Set<string>;
  onToggleAction: (key: string) => void;
  onSelectAll: () => void;
  onDeselectAll: () => void;
  onExecute: () => void;
  onBack: () => void;
  executing: boolean;
};

export function ConfirmView({
  result, selectedActions, onToggleAction, onSelectAll, onDeselectAll, onExecute, onBack, executing,
}: ConfirmViewProps) {
  const actions = result.plan.actions ?? [];
  const selectedCount = selectedActions.size;
  const totalCount = actions.length;

  return (
    <section className="confirm-view">
      <div className="confirm-header">
        <button className="confirm-back" type="button" onClick={onBack}>返回方案</button>
        <h2>确认执行项</h2>
        <p>以下操作将在你确认后自动执行。点击可切换。</p>
      </div>

      <div className="confirm-summary" aria-label="执行范围摘要">
        <span>即将执行 {selectedCount} / {totalCount} 项</span>
        <strong>仅执行已勾选的动作</strong>
        <p>未选择的预约、消息或日历动作会被跳过，后端会按 action id 做幂等执行。</p>
      </div>

      <div className="confirm-bulk-actions">
        <button type="button" onClick={onSelectAll}>全选</button>
        <button type="button" onClick={onDeselectAll}>全不选</button>
      </div>

      <div className="confirm-actions-list">
        {actions.map((action) => {
          const key = String(action.id ?? `${action.tool ?? action.type}_${action.target ?? action.label ?? action.place_id ?? 'default'}`);
          return (
            <ActionToggle key={key} action={action} selected={selectedActions.has(key)} onToggle={() => onToggleAction(key)} />
          );
        })}
      </div>

      {actions.length === 0 && (
        <div className="confirm-empty"><p>该方案没有需要执行的操作。</p></div>
      )}

      <ExecuteButton selectedCount={selectedActions.size} totalCount={actions.length} executing={executing} onClick={onExecute} />
    </section>
  );
}

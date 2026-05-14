'use client';

import React from 'react';
import { Ban, CheckCircle2, Circle, Loader2, PlayCircle } from 'lucide-react';

type ActionLedgerPanelProps = {
  actions: Array<Record<string, any>>;
  selectedActions: Set<string>;
  executing: boolean;
  phase?: string;
  onToggleAction: (key: string) => void;
  onSelectAll: () => void;
  onDeselectAll: () => void;
  onApprove: () => void;
  onReject: () => void;
};

const statusLabels: Record<string, string> = {
  pending: '待执行',
  executing: '执行中',
  succeeded: '已完成',
  failed: '失败',
  skipped: '已跳过',
};

const toolLabels: Record<string, string> = {
  messaging: '发送消息',
  calendar: '创建日历',
  reservation: '预约',
  commerce: '交易',
  send_plan_message: '发送计划',
  create_calendar_event: '创建日历',
  reserve_activity: '预约活动',
  create_reservation: '预订餐厅',
  restaurant_reservation: '餐厅订座',
  activity_reservation: '预约活动',
  claim_coupon: '领取团购券',
  create_order: '创建点单',
};

export function ActionLedgerPanel({
  actions,
  selectedActions,
  executing,
  phase,
  onToggleAction,
  onSelectAll,
  onDeselectAll,
  onApprove,
  onReject,
}: ActionLedgerPanelProps) {
  const pending = actions.filter((action) => String(action.status ?? 'pending') === 'pending');
  const selectedCount = selectedActions.size;
  const readyWithoutActions = phase === 'ready' && actions.length === 0;

  return (
    <aside className="action-ledger-panel" aria-label="执行账本">
      <div className="action-ledger-header">
        <div>
          <span>Action Ledger</span>
          <strong>执行账本</strong>
        </div>
        <code>{selectedCount} / {pending.length}</code>
      </div>

      <div className="action-ledger-toolbar">
        <button type="button" onClick={onSelectAll} disabled={!pending.length || executing}>全选待执行</button>
        <button type="button" onClick={onDeselectAll} disabled={!selectedCount || executing}>清空</button>
      </div>

      <div className="action-ledger-list">
        {actions.map((action) => {
          const id = String(action.action_id ?? action.id);
          const status = String(action.status ?? 'pending');
          const disabled = status !== 'pending' || executing;
          const selected = selectedActions.has(id);
          const StatusIcon = iconForStatus(status, selected);

          return (
            <button
              key={id}
              type="button"
              className={`ledger-action ${selected ? 'selected' : ''} ledger-action--${status}`}
              disabled={disabled}
              onClick={() => onToggleAction(id)}
              aria-pressed={selected}
            >
              <span className="ledger-action-status">
                <StatusIcon size={16} className={status === 'executing' ? 'spin' : ''} />
                {statusLabels[status] ?? status}
              </span>
              <strong>{action.label ?? toolLabels[String(action.tool)] ?? action.tool ?? action.type}</strong>
              <small>{action.detail ?? action.target ?? toolLabels[String(action.type)] ?? '确认后执行'}</small>
              <code>{id}</code>
            </button>
          );
        })}
      </div>

      {actions.length === 0 && (
        <div className="action-ledger-empty">{readyWithoutActions ? '无需审批，当前计划没有副作用动作。' : '当前计划没有待审批动作。'}</div>
      )}

      {!readyWithoutActions && (
        <div className="action-ledger-footer">
          <button className="secondary-button" type="button" onClick={onReject} disabled={executing}>取消计划</button>
          <button className="primary-button" type="button" onClick={onApprove} disabled={!selectedCount || executing}>
            {executing ? <><Loader2 size={16} className="spin" /> 执行中</> : <><PlayCircle size={16} /> 批准执行</>}
          </button>
        </div>
      )}
    </aside>
  );
}

function iconForStatus(status: string, selected: boolean) {
  if (status === 'succeeded') return CheckCircle2;
  if (status === 'failed') return Ban;
  if (status === 'executing') return Loader2;
  return selected ? CheckCircle2 : Circle;
}

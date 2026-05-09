'use client';

import { BottomExecutionBar } from './planner/BottomExecutionBar';
import { ConstraintCards } from './planner/ConstraintCards';
import { PlanCanvas } from './planner/PlanCanvas';
import { PromptComposer } from './planner/PromptComposer';
import { ReceiptStack } from './planner/ReceiptStack';
import { RecoveryDiff } from './planner/RecoveryDiff';

export function PlannerView({ goal, result, receipts, recoveredPlan, onExecute, onRecover }) {
  const plan = recoveredPlan ?? result.plan;
  const response = { ...result, plan };

  return (
    <section className="planner-view planner-workbench">
      <div className="conversation-pane">
        <div className="conversation-scroll">
          <PromptComposer goal={goal} />
          <ConstraintCards planId={plan.id} constraints={result.constraints} />
          <PlanCanvas response={response} />
          <RecoveryDiff diff={plan.diff} adjustment={plan.adjustment} />
          {onRecover ? (
            <button className="secondary-button full" type="button" onClick={onRecover}>换一家餐厅</button>
          ) : null}
        </div>
      </div>
      <BottomExecutionBar actions={plan.actions} onExecute={onExecute} />
      {receipts.length ? (
        <aside className="plan-side-panel receipt-side-panel">
          <section className="action-card">
            <div className="card-heading">
              <span>执行回执</span>
              <small>{receipts.length} 项</small>
            </div>
            <ReceiptStack receipts={receipts} />
          </section>
        </aside>
      ) : null}
    </section>
  );
}

'use client';

import React, { useState } from 'react';
import type { PlanResponse } from '../../types/weekendpilot';
import { ActionLedgerPanel } from './ActionLedgerPanel';
import { CandidateInsights } from './CandidateInsights';
import { ConstraintChips } from './ConstraintChips';
import { GraphRunStatusRail } from './GraphRunStatusRail';
import { ItineraryTimeline } from './ItineraryTimeline';
import { OverviewCard } from './OverviewCard';
import { VariantSelector } from './VariantSelector';
import { WorkbenchTabs, type WorkbenchTab } from './WorkbenchTabs';
import { RouteMap } from '../map/RouteMap';
import { TracePanel } from '../trace/TracePanel';

type PlanResultsViewProps = {
  result: PlanResponse;
  selectedActions: Set<string>;
  executing: boolean;
  onToggleAction: (key: string) => void;
  onSelectAll: () => void;
  onDeselectAll: () => void;
  onApprove: () => void;
  onReject: () => void;
  error: string | null;
};

export function PlanResultsView({
  result,
  selectedActions,
  executing,
  onToggleAction,
  onSelectAll,
  onDeselectAll,
  onApprove,
  onReject,
  error,
}: PlanResultsViewProps) {
  const [activeTab, setActiveTab] = useState<WorkbenchTab>('plan');
  const [activeVariant, setActiveVariant] = useState(0);
  const plan = result.plan;
  const actions = (result.actions?.length ? result.actions : plan.actions) ?? [];
  const phase = String(result.revision?.phase ?? plan.status);
  const variants = plan.variants?.length ? plan.variants : [plan];
  const activePlanVariant = variants[activeVariant] ?? variants[0] ?? plan;
  const displayItinerary = activePlanVariant?.itinerary?.length ? activePlanVariant.itinerary : plan.itinerary ?? [];
  const constraints = result.constraints ?? result.revision?.constraints ?? (plan as any).constraints ?? {};

  return (
    <section className="graph-workbench">
      <div className="graph-workbench-main">
        {error && <div className="plan-error-banner" role="alert">{error}</div>}

        <header className="plan-results-header">
          <div className="plan-results-title">
            <span className="plan-results-kicker">WeekendPilot Graph Run</span>
            <h1>{plan.title}</h1>
            {plan.summary && <p>{plan.summary}</p>}
          </div>
          <div className="plan-results-meta">
            <GraphRunStatusRail result={result} />
            {plan.badges?.length > 0 && (
              <div className="plan-badges" aria-label="方案标签">
                {plan.badges.map((badge) => <span key={badge}>{badge}</span>)}
              </div>
            )}
          </div>
        </header>

        <div className="workbench-toolbar">
          <WorkbenchTabs value={activeTab} onChange={setActiveTab} />
          <ConstraintChips constraints={constraints} editable={false} />
        </div>

        <div className="workbench-panel" hidden={activeTab !== 'plan'}>
          <OverviewCard
            overview={activePlanVariant?.overview ?? plan.overview ?? {}}
            constraintFit={activePlanVariant?.constraint_fit ?? plan.constraint_fit}
          />
          <VariantSelector
            variants={variants}
            activeIndex={activeVariant}
            onSelect={setActiveVariant}
          />
          <ItineraryTimeline itinerary={displayItinerary} />
          {result.route && (
            <section className="plan-map-section">
              <h2 className="section-title">路线预览</h2>
              <RouteMap route={result.route as any} />
            </section>
          )}
        </div>

        <div className="workbench-panel" hidden={activeTab !== 'evidence'}>
          <CandidateInsights
            candidateSets={(result as any).candidate_sets}
            validationIssues={(result as any).validation_issues ?? []}
          />
        </div>

        <div className="workbench-panel" hidden={activeTab !== 'trace'}>
          <TracePanel trace={result.trace ?? []} toolCalls={result.tool_calls ?? []} />
        </div>
      </div>

      <ActionLedgerPanel
        actions={actions as any}
        selectedActions={selectedActions}
        executing={executing}
        phase={phase}
        onToggleAction={onToggleAction}
        onSelectAll={onSelectAll}
        onDeselectAll={onDeselectAll}
        onApprove={onApprove}
        onReject={onReject}
      />
    </section>
  );
}

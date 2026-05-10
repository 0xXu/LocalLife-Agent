'use client';

import React, { useState } from 'react';
import type { PlanResponse } from '../../types/weekendpilot';
import { OverviewCard } from './OverviewCard';
import { ConstraintChips } from './ConstraintChips';
import { ItineraryTimeline } from './ItineraryTimeline';
import { VariantSelector } from './VariantSelector';
import { RecoveryBanner } from '../recovery/RecoveryBanner';
import { RouteMap } from '../map/RouteMap';
import { TracePanel } from '../trace/TracePanel';

type PlanResultsViewProps = {
  result: PlanResponse;
  recoveredPlan: PlanResponse['plan'] | null;
  onConfirm: () => void;
  onRecover: (reason: string) => void;
  onLoadAlternatives: () => void;
  error: string | null;
};

export function PlanResultsView({
  result, recoveredPlan, onConfirm, onRecover, onLoadAlternatives, error,
}: PlanResultsViewProps) {
  const [activeVariant, setActiveVariant] = useState(0);
  const [showTrace, setShowTrace] = useState(false);
  const [loadingAlternatives, setLoadingAlternatives] = useState(false);

  const plan = recoveredPlan ?? result.plan;
  const displayItinerary = activeVariant === 0
    ? (plan.itinerary ?? [])
    : (result.variants?.[activeVariant]?.itinerary ?? plan.itinerary ?? []);

  const handleLoadAlternatives = async () => {
    setLoadingAlternatives(true);
    try {
      await onLoadAlternatives();
    } finally {
      setLoadingAlternatives(false);
    }
  };

  return (
    <section className="plan-results">
      {error && <div className="plan-error-banner" role="alert">{error}</div>}
      {result.diff && <RecoveryBanner diff={result.diff} adjustment={result.adjustment} />}
      <ConstraintChips constraints={result.constraints} />
      <OverviewCard overview={plan.overview ?? {}} />
      <VariantSelector
        variants={result.variants?.length ? result.variants : [plan]}
        activeIndex={activeVariant}
        onSelect={setActiveVariant}
        onLoadMore={handleLoadAlternatives}
        loading={loadingAlternatives}
      />
      <ItineraryTimeline itinerary={displayItinerary} />
      {result.route && (
        <section className="plan-map-section">
          <h2 className="section-title">路线预览</h2>
          <RouteMap route={result.route as any} />
        </section>
      )}
      <button className="trace-toggle" type="button" onClick={() => setShowTrace(!showTrace)}>
        {showTrace ? '隐藏' : '查看'} Agent 执行详情
      </button>
      {showTrace && <TracePanel trace={result.trace ?? []} toolCalls={result.tool_calls ?? []} />}
      <div className="plan-results-actions">
        <button className="primary-button plan-confirm-btn" type="button" onClick={onConfirm}>
          确认方案，查看执行项
        </button>
        <button className="secondary-button" type="button" onClick={() => onRecover('restaurant_unavailable')}>
          模拟故障恢复
        </button>
      </div>
    </section>
  );
}

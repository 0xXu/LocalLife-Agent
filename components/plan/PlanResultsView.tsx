'use client';

import React, { useState } from 'react';
import type { PlanResponse } from '../../types/weekendpilot';
import type { LoadingAction } from '../../types/views';
import { OverviewCard } from './OverviewCard';
import { ConstraintChips } from './ConstraintChips';
import { ItineraryTimeline } from './ItineraryTimeline';
import { VariantSelector } from './VariantSelector';
import { RecoveryBanner } from '../recovery/RecoveryBanner';
import { RouteMap } from '../map/RouteMap';
import { TracePanel } from '../trace/TracePanel';
import { MessageSquare, RefreshCw, Edit3, Loader2, Sparkles } from 'lucide-react';

type PlanResultsViewProps = {
  result: PlanResponse;
  recoveredPlan: PlanResponse['plan'] | null;
  onConfirm: () => void;
  onRecover: (reason: string) => void;
  onLoadAlternatives: () => void;
  onPatchConstraints: (updates: Record<string, any>) => void;
  onRegenerateWithFeedback: (feedback: string) => void;
  onReplaceNode: (nodeType: string, nodeId: string) => void;
  error: string | null;
  loadingAction?: LoadingAction;
  loadingMessage?: string;
};

export function PlanResultsView({
  result, recoveredPlan, onConfirm, onRecover, onLoadAlternatives,
  onPatchConstraints, onRegenerateWithFeedback, onReplaceNode, error,
  loadingAction, loadingMessage,
}: PlanResultsViewProps) {
  const [activeVariant, setActiveVariant] = useState(0);
  const [showTrace, setShowTrace] = useState(false);
  const [loadingAlternatives, setLoadingAlternatives] = useState(false);
  const [feedback, setFeedback] = useState('');
  const [showFeedback, setShowFeedback] = useState(false);
  const [isEditingConstraints, setIsEditingConstraints] = useState(false);

  const plan = recoveredPlan ?? result.plan;
  const variants = result.variants?.length
    ? result.variants
    : plan.variants?.length
      ? plan.variants
      : [plan];
  const activePlanVariant = variants[activeVariant] ?? variants[0] ?? plan;
  const displayItinerary = activePlanVariant?.itinerary ?? plan.itinerary ?? [];

  const isLoading = loadingAction !== null;

  const handleLoadAlternatives = async () => {
    setLoadingAlternatives(true);
    try {
      await onLoadAlternatives();
    } finally {
      setLoadingAlternatives(false);
    }
  };

  const handleFeedbackSubmit = () => {
    if (feedback.trim()) {
      onRegenerateWithFeedback(feedback.trim());
      setFeedback('');
      setShowFeedback(false);
    }
  };

  const handleConstraintsChange = (updates: Record<string, any>) => {
    onPatchConstraints(updates);
    setIsEditingConstraints(false);
  };

  return (
    <section className="plan-results">
      {/* 全局加载动画 */}
      {isLoading && (
        <div className="loading-overlay">
          <div className="loading-card">
            <div className="loading-icon-wrapper">
              <Loader2 size={24} className="spin" />
            </div>
            <div className="loading-content">
              <strong>{loadingMessage}</strong>
              <span>AI 正在为您调整方案，请稍候...</span>
            </div>
            <div className="loading-progress">
              <div className="loading-progress-bar" />
            </div>
          </div>
        </div>
      )}

      {error && <div className="plan-error-banner" role="alert">{error}</div>}
      {result.diff && <RecoveryBanner diff={result.diff} adjustment={result.adjustment} />}

      <header className="plan-results-header">
        <div>
          <h1>{plan.title}</h1>
          {plan.summary && <p>{plan.summary}</p>}
        </div>
        {plan.badges?.length > 0 && (
          <div className="plan-badges" aria-label="方案标签">
            {plan.badges.map((badge) => <span key={badge}>{badge}</span>)}
          </div>
        )}
      </header>

      {/* 约束卡片 - 可编辑 */}
      <div className={`constraint-section ${loadingAction === 'constraints' ? 'section-loading' : ''}`}>
        <div className="constraint-header">
          <h3>当前约束</h3>
          <button
            className="constraint-edit-btn"
            onClick={() => setIsEditingConstraints(!isEditingConstraints)}
            disabled={isLoading}
          >
            <Edit3 size={14} />
            {isEditingConstraints ? '完成' : '编辑'}
          </button>
        </div>
        <ConstraintChips
          constraints={result.constraints}
          onConstraintsChange={handleConstraintsChange}
          editable={isEditingConstraints && !isLoading}
        />
      </div>

      <OverviewCard
        overview={activePlanVariant?.overview ?? plan.overview ?? {}}
        constraintFit={activePlanVariant?.constraint_fit ?? plan.constraint_fit}
      />

      {/* 备选方案 - 更明显的入口 */}
      <div className={loadingAction === 'alternatives' ? 'section-loading' : ''}>
        <VariantSelector
          variants={variants}
          activeIndex={activeVariant}
          onSelect={setActiveVariant}
          onLoadMore={handleLoadAlternatives}
          loading={loadingAlternatives || loadingAction === 'alternatives'}
        />
      </div>

      {/* 行程时间轴 - 带节点替换 */}
      <div className={loadingAction === 'replace' ? 'section-loading' : ''}>
        <ItineraryTimeline
          itinerary={displayItinerary}
          onReplaceNode={onReplaceNode}
        />
      </div>

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

      {/* 自然语言反馈 */}
      <div className={`feedback-section ${loadingAction === 'feedback' ? 'section-loading' : ''}`}>
        <button
          className="feedback-toggle"
          onClick={() => setShowFeedback(!showFeedback)}
          disabled={isLoading}
        >
          <MessageSquare size={16} />
          对方案不满意？说说你的想法
        </button>
        {showFeedback && (
          <div className="feedback-input-wrapper">
            <textarea
              className="feedback-input"
              placeholder="例如：太赶了，能轻松点吗？/ 换一家安静的餐厅 / 预算控制在500以内"
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              rows={3}
              disabled={isLoading}
            />
            <button
              className="primary-button feedback-submit"
              onClick={handleFeedbackSubmit}
              disabled={!feedback.trim() || isLoading}
            >
              {loadingAction === 'feedback' ? (
                <Loader2 size={16} className="spin" />
              ) : (
                <Sparkles size={16} />
              )}
              {loadingAction === 'feedback' ? '正在调整...' : '根据反馈重新生成'}
            </button>
          </div>
        )}
      </div>

      <div className="plan-results-actions">
        <button
          className="primary-button plan-confirm-btn"
          type="button"
          onClick={onConfirm}
          disabled={isLoading}
        >
          确认方案，查看执行项
        </button>
        <button
          className="secondary-button"
          type="button"
          onClick={() => onRecover('restaurant_unavailable')}
          disabled={isLoading}
        >
          模拟故障恢复
        </button>
      </div>
    </section>
  );
}

'use client';

import React from 'react';
import { ProgressStep } from './ProgressStep';

type PlanningProgressProps = {
  goal: string;
  progress: string[];
  currentStep: number;
  streamingText: string;
};

const pipelineSteps = [
  '理解出行需求',
  '补全场景上下文',
  '筛选本地供给',
  '多目标排序',
  '生成时间轴和路线',
  '校验可订性和约束',
];

function getStepStatus(currentStep: number, index: number): 'pending' | 'running' | 'done' {
  if (index < currentStep) return 'done';
  if (index === currentStep) return 'running';
  return 'pending';
}

export function PlanningProgress({ goal, progress, currentStep, streamingText }: PlanningProgressProps) {
  const displayStep = Math.min(pipelineSteps.length, Math.max(1, currentStep + 1));
  const progressWidth = Math.min(100, (displayStep / pipelineSteps.length) * 100);
  const liveText = formatLiveText(streamingText);
  const steps = pipelineSteps.map((label, index) => ({
    label,
    status: currentStep < 0
      ? (index === 0 ? 'running' : 'pending')
      : getStepStatus(currentStep, index),
    detail: progress[index] && progress[index] !== label ? progress[index] : undefined,
  }));

  return (
    <section className="planning-progress">
      <div className="planning-progress-header">
        <div className="planning-progress-goal">
          <span>正在规划 · {displayStep} / {pipelineSteps.length}</span>
          <p>{goal}</p>
        </div>
      </div>

      <div className="planning-progress-bar">
        <div
          className="planning-progress-fill"
          style={{ width: `${progressWidth}%` }}
        />
      </div>

      {liveText && (
        <div className="planning-live-card" role="status" aria-live="polite">
          <div className="planning-thinking-dots" aria-hidden="true">
            <span />
            <span />
            <span />
          </div>
          <p>{liveText}</p>
        </div>
      )}

      <div className="planning-progress-steps">
        {steps.map((step, index) => (
          <ProgressStep
            key={step.label}
            label={step.label}
            detail={step.detail}
            status={step.status}
            index={index}
          />
        ))}
      </div>

    </section>
  );
}

function formatLiveText(streamingText: string) {
  const trimmed = streamingText.trim();
  if (!trimmed) return '';
  if ((trimmed.startsWith('{') || trimmed.startsWith('[')) && /scenario|preferences|constraints|candidate/i.test(trimmed)) {
    return '正在解析开放域约束、用户画像与候选检索条件...';
  }
  return trimmed.length > 180 ? `${trimmed.slice(0, 177)}...` : trimmed;
}

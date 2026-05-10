'use client';

import React from 'react';
import { ProgressStep } from './ProgressStep';

type PlanningProgressProps = {
  goal: string;
  progress: string[];
};

const pipelineSteps = [
  '理解出行需求',
  '补全场景上下文',
  '筛选本地供给',
  '多目标排序',
  '生成时间轴和路线',
  '校验可订性和约束',
];

function getStepStatus(progress: string[], index: number): 'pending' | 'running' | 'done' {
  if (index < progress.length - 1) return 'done';
  if (index === progress.length - 1) return 'running';
  return 'pending';
}

export function PlanningProgress({ goal, progress }: PlanningProgressProps) {
  const steps = pipelineSteps.map((label, index) => ({
    label,
    status: progress.length === 0
      ? (index === 0 ? 'running' : 'pending')
      : getStepStatus(progress, index),
    detail: progress[index] ?? undefined,
  }));

  return (
    <section className="planning-progress">
      <div className="planning-progress-header">
        <div className="planning-progress-goal">
          <span>正在规划</span>
          <p>{goal}</p>
        </div>
      </div>

      <div className="planning-progress-bar">
        <div
          className="planning-progress-fill"
          style={{ width: `${Math.min(100, (progress.length / pipelineSteps.length) * 100)}%` }}
        />
      </div>

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

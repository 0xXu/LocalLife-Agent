'use client';

import React from 'react';
import { Check, Loader2, AlertCircle, Circle } from 'lucide-react';

type StepStatus = 'pending' | 'running' | 'done' | 'error';

type ProgressStepProps = {
  label: string;
  detail?: string;
  status: StepStatus;
  index: number;
};

const statusIcons: Record<StepStatus, typeof Circle> = {
  pending: Circle,
  running: Loader2,
  done: Check,
  error: AlertCircle,
};

const statusClasses: Record<StepStatus, string> = {
  pending: 'progress-step--pending',
  running: 'progress-step--running',
  done: 'progress-step--done',
  error: 'progress-step--error',
};

export function ProgressStep({ label, detail, status, index }: ProgressStepProps) {
  const Icon = statusIcons[status];
  return (
    <div
      className={`progress-step ${statusClasses[status]}`}
      style={{ animationDelay: `${index * 100}ms` }}
    >
      <div className="progress-step-icon">
        <Icon size={18} className={status === 'running' ? 'spin' : ''} />
      </div>
      <div className="progress-step-text">
        <strong>{label}</strong>
        {detail && <span>{detail}</span>}
      </div>
    </div>
  );
}

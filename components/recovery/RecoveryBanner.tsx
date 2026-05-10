'use client';

import React from 'react';
import { ArrowRight, RefreshCw } from 'lucide-react';

type RecoveryBannerProps = {
  diff: {
    changed?: string;
    reason?: string;
    from?: string;
    to?: string;
    costDelta?: string;
    travelDelta?: string;
    preserved?: string[];
  };
  adjustment?: {
    headline?: string;
    message?: string;
  };
};

export function RecoveryBanner({ diff, adjustment }: RecoveryBannerProps) {
  return (
    <div className="recovery-banner">
      <div className="recovery-banner-icon"><RefreshCw size={18} /></div>
      <div className="recovery-banner-body">
        <strong>{adjustment?.headline ?? '方案已调整'}</strong>
        <p>{adjustment?.message ?? diff.reason ?? '检测到问题，已自动替换。'}</p>
        {diff.from && diff.to && (
          <div className="recovery-diff">
            <span>{diff.from}</span>
            <ArrowRight size={14} />
            <span>{diff.to}</span>
          </div>
        )}
        {(diff.costDelta || diff.travelDelta) && (
          <div className="recovery-deltas">
            {diff.costDelta && <span>预算: {diff.costDelta}</span>}
            {diff.travelDelta && <span>路程: {diff.travelDelta}</span>}
          </div>
        )}
      </div>
    </div>
  );
}


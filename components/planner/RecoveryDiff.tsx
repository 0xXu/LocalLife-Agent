import React from 'react';

type RecoveryDiffProps = {
  diff?: Record<string, any>;
  adjustment?: Record<string, any>;
};

export function RecoveryDiff({ diff, adjustment }: RecoveryDiffProps) {
  if (!diff) {
    return null;
  }

  return (
    <section className="recovery-card">
      <h2>{adjustment?.headline ?? '已生成恢复方案'}</h2>
      <p>{adjustment?.message ?? diff.reason}</p>
      <div className="diff-grid">
        <div><span>原方案</span><strong>{diff.from}</strong></div>
        <div><span>新方案</span><strong>{diff.to}</strong></div>
        <div><span>预算变化</span><strong>{diff.costDelta}</strong></div>
        <div><span>路线变化</span><strong>{diff.travelDelta}</strong></div>
      </div>
    </section>
  );
}

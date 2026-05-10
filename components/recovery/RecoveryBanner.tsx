'use client';
import React from 'react';
export function RecoveryBanner({ diff, adjustment }: { diff?: any; adjustment?: any }) {
  if (!diff) return null;
  return <div className="recovery-banner"><p>{adjustment?.headline ?? '方案已调整'}</p></div>;
}

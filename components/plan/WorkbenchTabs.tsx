'use client';

import React from 'react';

export type WorkbenchTab = 'plan' | 'evidence' | 'trace';

const tabs: Array<[WorkbenchTab, string]> = [
  ['plan', '计划'],
  ['evidence', '证据'],
  ['trace', 'Graph'],
];

export function WorkbenchTabs({ value, onChange }: { value: WorkbenchTab; onChange: (value: WorkbenchTab) => void }) {
  return (
    <div className="workbench-tabs" role="tablist" aria-label="工作台视图">
      {tabs.map(([key, label]) => (
        <button
          key={key}
          type="button"
          role="tab"
          aria-selected={value === key}
          className={value === key ? 'active' : ''}
          onClick={() => onChange(key)}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

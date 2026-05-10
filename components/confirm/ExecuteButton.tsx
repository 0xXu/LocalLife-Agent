'use client';

import React from 'react';
import { Loader2, Zap } from 'lucide-react';

type ExecuteButtonProps = {
  selectedCount: number;
  totalCount: number;
  executing: boolean;
  onClick: () => void;
};

export function ExecuteButton({ selectedCount, totalCount, executing, onClick }: ExecuteButtonProps) {
  return (
    <div className="execute-button-wrapper">
      <div className="execute-button-info">
        <span>已选择 <strong>{selectedCount}</strong> / {totalCount} 项操作</span>
      </div>
      <button
        className="execute-button"
        type="button"
        onClick={onClick}
        disabled={selectedCount === 0 || executing}
      >
        {executing ? (
          <><Loader2 size={20} className="spin" /> 执行中...</>
        ) : (
          <><Zap size={20} /> 一键执行</>
        )}
      </button>
    </div>
  );
}

'use client';

import React from 'react';
import { Calendar } from 'lucide-react';
import { EmptyState } from '../ui/EmptyState';

export interface EmptyPlansProps {
  onNavigateHome: () => void;
}

export function EmptyPlans({ onNavigateHome }: EmptyPlansProps) {
  return (
    <EmptyState
      icon={<Calendar size={28} />}
      title="还没有保存的计划"
      description="去首页创建你的第一个周末计划吧"
      action={{ label: '创建计划', onClick: onNavigateHome }}
    />
  );
}

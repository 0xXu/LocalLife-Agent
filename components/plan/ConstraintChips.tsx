'use client';

import React from 'react';
import { CalendarClock, CircleDollarSign, MapPinned, Utensils, Users } from 'lucide-react';

type ConstraintChipsProps = {
  constraints: Record<string, any>;
};

export function ConstraintChips({ constraints }: ConstraintChipsProps) {
  const party = constraints.party ?? `${constraints.people?.adults ?? '?'} 人`;
  const radius = constraints.radiusKm ?? constraints.constraints?.radius_km ?? 5;
  const budget = constraints.preferences?.budget_level ?? 'medium';
  const start = constraints.time_window?.start ?? '??:??';
  const diet = constraints.preferences?.diet?.[0] ?? null;

  const budgetLabels: Record<string, string> = { low: '省钱', medium: '适中', high: '不限' };
  const dietLabels: Record<string, string> = { low_fat: '低脂', low_sugar: '低糖', vegetarian: '素食', no_gluten: '无麸质' };

  return (
    <div className="constraint-chips">
      <span className="constraint-chip"><Users size={14} /> {party}</span>
      <span className="constraint-chip"><MapPinned size={14} /> {radius}km</span>
      <span className="constraint-chip"><CircleDollarSign size={14} /> {budgetLabels[budget] ?? budget}</span>
      <span className="constraint-chip"><CalendarClock size={14} /> {start}</span>
      {diet && <span className="constraint-chip"><Utensils size={14} /> {dietLabels[diet] ?? diet}</span>}
    </div>
  );
}

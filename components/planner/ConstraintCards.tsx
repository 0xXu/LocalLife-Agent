import React from 'react';
import { CalendarClock, CircleDollarSign, MapPinned, Utensils, Users } from 'lucide-react';

import { patchConstraints } from '../../features/planner/apiClient';

type ConstraintCardsProps = {
  planId: string;
  constraints: Record<string, any>;
};

export function ConstraintCards({ planId, constraints }: ConstraintCardsProps) {
  const party = constraints.party ?? `${constraints.people?.adults ?? 0} 位成人`;
  const radiusKm = constraints.radiusKm ?? constraints.constraints?.radius_km ?? 5;
  const budgetLevel = constraints.preferences?.budget_level ?? 'medium';
  const start = constraints.time_window?.start ?? '14:00';
  const diet = constraints.preferences?.diet ?? [];

  return (
    <section className="constraint-card constraint-controls">
      <div className="card-heading">
        <span>已理解你的需求</span>
        <small>可编辑</small>
      </div>
      <div className="constraint-grid">
        <Metric icon={Users} label="人群" value={party} />
        <label className="constraint-metric" data-constraint="radius_km">
          <span><MapPinned size={16} /> 半径</span>
          <select defaultValue={String(radiusKm)} onChange={(event) => update(planId, { constraints: { radius_km: Number(event.target.value) } })}>
            <option value="3">3 公里</option>
            <option value="5">5 公里</option>
            <option value="10">10 公里</option>
          </select>
        </label>
        <label className="constraint-metric" data-constraint="budget_level">
          <span><CircleDollarSign size={16} /> 预算</span>
          <select defaultValue={budgetLevel} onChange={(event) => update(planId, { preferences: { budget_level: event.target.value } })}>
            <option value="low">低</option>
            <option value="medium">中</option>
            <option value="high">高</option>
          </select>
        </label>
        <label className="constraint-metric" data-constraint="start">
          <span><CalendarClock size={16} /> 开始</span>
          <input type="time" defaultValue={start} onChange={(event) => update(planId, { time_window: { start: event.target.value } })} />
        </label>
        <label className="constraint-metric" data-constraint="diet">
          <span><Utensils size={16} /> 饮食</span>
          <select defaultValue={diet[0] ?? 'low_fat'} onChange={(event) => update(planId, { preferences: { diet: [event.target.value] } })}>
            <option value="low_fat">低脂</option>
            <option value="low_sugar">低糖</option>
            <option value="vegetarian">素食</option>
            <option value="no_gluten">无麸质</option>
          </select>
        </label>
        <label className="constraint-metric" data-constraint="transport">
          <span><MapPinned size={16} /> 交通</span>
          <select defaultValue="walk_taxi" onChange={(event) => update(planId, { transport: event.target.value })}>
            <option value="walk_taxi">步行 + 打车</option>
            <option value="taxi">打车</option>
            <option value="walk">步行</option>
          </select>
        </label>
      </div>
    </section>
  );
}

function Metric({ icon: Icon, label, value }: { icon: typeof Users; label: string; value: string }) {
  return (
    <div className="constraint-metric">
      <span><Icon size={16} /> {label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function update(planId: string, updates: Record<string, unknown>) {
  if (!planId) {
    return;
  }
  void patchConstraints(planId, updates);
}

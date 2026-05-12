'use client';

import React, { useState } from 'react';
import { CalendarClock, CircleDollarSign, MapPinned, Utensils, Users, Edit3, Check, X } from 'lucide-react';
import { BUDGET_LABELS, DIET_LABELS } from '../../lib/constants/nodeTypes';

type ConstraintChipsProps = {
  constraints: Record<string, any>;
  onConstraintsChange?: (updates: Record<string, any>) => void;
  editable?: boolean;
};

export function ConstraintChips({ constraints, onConstraintsChange, editable = false }: ConstraintChipsProps) {
  const [editingField, setEditingField] = useState<string | null>(null);
  const [editValue, setEditValue] = useState<string>('');

  const party = constraints.party ?? `${constraints.people?.adults ?? '?'} 人`;
  const radius = constraints.radiusKm ?? constraints.constraints?.radius_km ?? 5;
  const budget = constraints.preferences?.budget_level ?? 'medium';
  const start = constraints.time_window?.start ?? '??:??';
  const diet = constraints.preferences?.diet?.[0] ?? null;

  const handleEdit = (field: string, currentValue: string) => {
    setEditingField(field);
    setEditValue(currentValue);
  };

  const handleSave = () => {
    if (!editingField || !onConstraintsChange) return;

    const updates: Record<string, any> = {};
    switch (editingField) {
      case 'radius':
        updates.radius_km = parseFloat(editValue);
        break;
      case 'budget':
        updates.budget_level = editValue;
        break;
      case 'start':
        updates.start = editValue;
        break;
    }

    onConstraintsChange(updates);
    setEditingField(null);
  };

  const handleCancel = () => {
    setEditingField(null);
  };

  const renderEditableChip = (
    field: string,
    icon: React.ReactNode,
    label: string,
    value: string
  ) => {
    const isEditing = editingField === field;

    if (isEditing) {
      return (
        <span className="constraint-chip constraint-chip--editing">
          {icon}
          {field === 'budget' ? (
            <select value={editValue} onChange={(e) => setEditValue(e.target.value)}>
              <option value="low">省钱</option>
              <option value="medium">适中</option>
              <option value="high">不限</option>
            </select>
          ) : (
            <input
              type={field === 'radius' ? 'number' : 'text'}
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              autoFocus
            />
          )}
          <button onClick={handleSave} className="constraint-chip-btn"><Check size={12} /></button>
          <button onClick={handleCancel} className="constraint-chip-btn"><X size={12} /></button>
        </span>
      );
    }

    return (
      <span className={`constraint-chip${editable ? ' constraint-chip--editable' : ''}`}>
        {icon} {label}
        {editable && (
          <button onClick={() => handleEdit(field, value)} className="constraint-chip-btn">
            <Edit3 size={10} />
          </button>
        )}
      </span>
    );
  };

  return (
    <div className="constraint-chips">
      <span className="constraint-chip"><Users size={14} /> {party}</span>
      {renderEditableChip(
        'radius',
        <MapPinned size={14} />,
        `${radius}km`,
        String(radius)
      )}
      {renderEditableChip(
        'budget',
        <CircleDollarSign size={14} />,
        BUDGET_LABELS[budget] ?? budget,
        budget
      )}
      {renderEditableChip(
        'start',
        <CalendarClock size={14} />,
        start,
        start
      )}
      {diet && <span className="constraint-chip"><Utensils size={14} /> {DIET_LABELS[diet] ?? diet}</span>}
    </div>
  );
}

'use client';

import React from 'react';
import { CloudRain, Heart, Users, Utensils } from 'lucide-react';
import { scenarioPrompts } from '../../features/planner/uiFixtures';

type QuickActionsProps = {
  onSelect: (goal: string) => void;
  disabled?: boolean;
};

const actions = [
  { id: 'family', label: '带娃出行', icon: Users, prompt: scenarioPrompts.family, color: 'blue' },
  { id: 'friends', label: '朋友聚会', icon: Utensils, prompt: scenarioPrompts.friends, color: 'violet' },
  { id: 'date', label: '浪漫约会', icon: Heart, prompt: scenarioPrompts.date, color: 'green' },
  { id: 'rainy', label: '雨天方案', icon: CloudRain, prompt: scenarioPrompts.rainy, color: 'coral' },
];

export function QuickActions({ onSelect, disabled }: QuickActionsProps) {
  return (
    <div className="quick-actions" role="group" aria-label="快捷场景">
      {actions.map((action, index) => {
        const Icon = action.icon;
        return (
          <button
            key={action.id}
            className={`quick-action quick-action--${action.color}`}
            type="button"
            disabled={disabled}
            onClick={() => onSelect(action.prompt)}
            style={{ animationDelay: `${index * 80}ms` }}
          >
            <Icon size={18} />
            <span>{action.label}</span>
          </button>
        );
      })}
    </div>
  );
}

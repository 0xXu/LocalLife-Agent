'use client';

import React from 'react';
import { Utensils } from 'lucide-react';
import { Toggle } from '../ui/Toggle';
import styles from './SettingsView.module.css';

export interface DietSectionProps {
  fitnessFriendly: boolean;
  vegetarian: boolean;
  glutenFree: boolean;
  onToggle: (key: 'fitness_friendly' | 'vegetarian' | 'gluten_free') => void;
}

export function DietSection({ fitnessFriendly, vegetarian, glutenFree, onToggle }: DietSectionProps) {
  return (
    <div className={styles.section}>
      <h2 className={styles.sectionTitle}><Utensils size={18} /> 饮食偏好</h2>
      <Toggle checked={fitnessFriendly} onChange={() => onToggle('fitness_friendly')}
        label="减脂友好" description="优先推荐低热量、高蛋白的餐厅选项" testId="preference-fitness" />
      <Toggle checked={vegetarian} onChange={() => onToggle('vegetarian')}
        label="素食" testId="preference-vegetarian" />
      <Toggle checked={glutenFree} onChange={() => onToggle('gluten_free')}
        label="无麸质" testId="preference-gluten-free" />
    </div>
  );
}

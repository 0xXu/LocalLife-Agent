'use client';

import React from 'react';
import { MapPin } from 'lucide-react';
import styles from './SettingsView.module.css';

export interface LocationSectionProps {
  radiusKm: number;
  onChange: (radius: number) => void;
}

export function LocationSection({ radiusKm, onChange }: LocationSectionProps) {
  return (
    <div className={styles.section}>
      <h2 className={styles.sectionTitle}><MapPin size={18} /> 位置偏好</h2>
      <div className={styles.sliderContainer}>
        <div className={styles.sliderHeader}>
          <span className={styles.preferenceLabel}>活动半径</span>
          <span className={styles.sliderValue}>{radiusKm} 公里</span>
        </div>
        <input type="range" className={styles.slider} min={1} max={10}
          value={radiusKm} onChange={(e) => onChange(Number(e.target.value))}
          aria-label="活动半径" data-testid="radius-slider" />
        <div className={styles.sliderLabels}>
          <span>1 公里</span><span>10 公里</span>
        </div>
      </div>
    </div>
  );
}

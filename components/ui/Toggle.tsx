'use client';

import React from 'react';
import styles from './Toggle.module.css';

export interface ToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  label?: string;
  description?: string;
  testId?: string;
}

export function Toggle({ checked, onChange, disabled, label, description, testId }: ToggleProps) {
  return (
    <div className={styles.row}>
      {(label || description) && (
        <div className={styles.text}>
          {label && <strong className={styles.label}>{label}</strong>}
          {description && <span className={styles.description}>{description}</span>}
        </div>
      )}
      <button type="button" className={`${styles.track} ${checked ? styles.on : ''}`}
        aria-pressed={checked} disabled={disabled}
        onClick={() => onChange(!checked)} data-testid={testId}>
        <span className={styles.thumb} />
      </button>
    </div>
  );
}

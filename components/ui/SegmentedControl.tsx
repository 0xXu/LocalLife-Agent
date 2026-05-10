'use client';

import React from 'react';
import styles from './SegmentedControl.module.css';

export interface SegmentedOption<T extends string> {
  value: T;
  label: string;
  icon?: React.ReactNode;
}

export interface SegmentedControlProps<T extends string> {
  options: SegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
  className?: string;
}

export function SegmentedControl<T extends string>({
  options, value, onChange, className,
}: SegmentedControlProps<T>) {
  return (
    <div className={`${styles.control} ${className ?? ''}`} role="tablist">
      {options.map((opt) => (
        <button key={opt.value} type="button" role="tab"
          aria-selected={opt.value === value}
          className={`${styles.option} ${opt.value === value ? styles.active : ''}`}
          onClick={() => onChange(opt.value)}>
          {opt.icon}
          {opt.label}
        </button>
      ))}
    </div>
  );
}

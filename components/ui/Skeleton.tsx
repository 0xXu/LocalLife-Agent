import React from 'react';
import styles from './Skeleton.module.css';

export interface SkeletonProps {
  variant?: 'text' | 'circular' | 'rectangular';
  width?: string | number;
  height?: string | number;
  className?: string;
}

export function Skeleton({ variant = 'text', width, height, className }: SkeletonProps) {
  return (
    <div
      className={`${styles.skeleton} ${styles[variant]} ${className ?? ''}`}
      style={{ width, height }}
    />
  );
}

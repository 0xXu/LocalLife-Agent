'use client';

import React from 'react';
import styles from './Button.module.css';

export interface ButtonProps {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  icon?: React.ReactNode;
  loading?: boolean;
  disabled?: boolean;
  children: React.ReactNode;
  onClick?: () => void;
  className?: string;
  type?: 'button' | 'submit';
  'data-testid'?: string;
}

export function Button({
  variant = 'primary',
  size = 'md',
  icon,
  loading,
  disabled,
  children,
  onClick,
  className,
  type = 'button',
  'data-testid': testId,
}: ButtonProps) {
  return (
    <button
      type={type}
      className={`${styles.button} ${styles[size]} ${styles[variant]} ${className ?? ''}`}
      disabled={disabled || loading}
      onClick={onClick}
      data-testid={testId}
    >
      {loading ? <span className={styles.spinner} /> : icon}
      {children}
    </button>
  );
}

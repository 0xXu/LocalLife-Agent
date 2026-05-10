'use client';

import React from 'react';
import styles from './Card.module.css';

export interface CardProps {
  variant?: 'default' | 'elevated' | 'outlined';
  padding?: 'sm' | 'md' | 'lg';
  interactive?: boolean;
  selected?: boolean;
  children: React.ReactNode;
  onClick?: () => void;
  className?: string;
  style?: React.CSSProperties;
  'data-testid'?: string;
}

export function Card({
  variant = 'default',
  padding = 'md',
  interactive,
  selected,
  children,
  onClick,
  className,
  style,
  'data-testid': testId,
}: CardProps) {
  const cls = [
    styles.card,
    styles[`padding${padding.charAt(0).toUpperCase() + padding.slice(1)}`],
    variant !== 'default' ? styles[variant] : '',
    interactive ? styles.interactive : '',
    selected ? styles.selected : '',
    className ?? '',
  ].filter(Boolean).join(' ');

  return (
    <div className={cls} style={style} onClick={onClick}
      role={interactive ? 'button' : undefined}
      tabIndex={interactive ? 0 : undefined}
      data-testid={testId}>
      {children}
    </div>
  );
}

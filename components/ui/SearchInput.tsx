'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Search, X } from 'lucide-react';
import styles from './SearchInput.module.css';

export interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  debounceMs?: number;
  autoFocus?: boolean;
  className?: string;
  containerTestId?: string;
  inputTestId?: string;
}

export function SearchInput({
  value, onChange, placeholder = '搜索...', debounceMs = 300, autoFocus, className, containerTestId, inputTestId,
}: SearchInputProps) {
  const [local, setLocal] = useState(value);
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => { setLocal(value); }, [value]);

  const debouncedChange = useCallback(
    (next: string) => {
      setLocal(next);
      clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => onChange(next), debounceMs);
    },
    [onChange, debounceMs],
  );

  useEffect(() => () => clearTimeout(timerRef.current), []);

  return (
    <div className={`${styles.wrapper} ${className ?? ''}`} data-testid={containerTestId}>
      <Search size={16} className={styles.icon} />
      <input type="search" className={styles.input} value={local}
        onChange={(e) => debouncedChange(e.target.value)}
        placeholder={placeholder} autoFocus={autoFocus} data-testid={inputTestId} />
      {local && (
        <button type="button" className={styles.clear}
          onClick={() => { setLocal(''); onChange(''); }} aria-label="清除搜索">
          <X size={14} />
        </button>
      )}
    </div>
  );
}

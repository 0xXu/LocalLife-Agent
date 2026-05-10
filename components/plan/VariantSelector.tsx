'use client';

import React from 'react';
import { Loader2 } from 'lucide-react';

type VariantSelectorProps = {
  variants: Array<Record<string, any>>;
  activeIndex: number;
  onSelect: (index: number) => void;
  onLoadMore?: () => void;
  loading?: boolean;
};

const kindLabels: Record<string, string> = {
  main: '推荐', budget: '省钱', comfort: '舒适', child_first: '亲子', experience_first: '体验',
};

export function VariantSelector({ variants, activeIndex, onSelect, onLoadMore, loading }: VariantSelectorProps) {
  if (!variants.length) return null;
  return (
    <section className="variant-selector">
      <div className="variant-scroll">
        {variants.map((variant, index) => (
          <button
            key={variant.id ?? variant.kind ?? index}
            className={`variant-chip${index === activeIndex ? ' active' : ''}`}
            type="button"
            onClick={() => onSelect(index)}
          >
            <strong>{kindLabels[variant.kind] ?? variant.title ?? `方案${index + 1}`}</strong>
            {variant.overview?.score && <span>{variant.overview.score}分</span>}
          </button>
        ))}
        {onLoadMore && variants.length <= 1 && (
          <button
            className="variant-chip variant-chip--more"
            type="button"
            onClick={onLoadMore}
            disabled={loading}
          >
            {loading ? <Loader2 size={14} className="spin" /> : '更多方案'}
          </button>
        )}
      </div>
    </section>
  );
}

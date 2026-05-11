'use client';

import React from 'react';
import { Loader2, Sparkles } from 'lucide-react';
import { VARIANT_KIND_LABELS, VARIANT_KIND_DESCRIPTIONS } from '../../lib/constants/nodeTypes';

type VariantSelectorProps = {
  variants: Array<Record<string, any>>;
  activeIndex: number;
  onSelect: (index: number) => void;
  onLoadMore?: () => void;
  loading?: boolean;
};

export function VariantSelector({ variants, activeIndex, onSelect, onLoadMore, loading }: VariantSelectorProps) {
  if (!variants.length) return null;

  return (
    <section className="variant-selector">
      <div className="variant-header">
        <h3><Sparkles size={16} /> 方案选择</h3>
        <span className="variant-hint">点击切换不同方案</span>
      </div>
      <div className="variant-scroll">
        {variants.map((variant, index) => (
          <button
            key={variant.id ?? variant.kind ?? index}
            className={`variant-chip${index === activeIndex ? ' active' : ''}`}
            type="button"
            onClick={() => onSelect(index)}
          >
            <strong>{VARIANT_KIND_LABELS[variant.kind] ?? variant.title ?? `方案${index + 1}`}</strong>
            {variant.summary && <span className="variant-desc">{variant.summary}</span>}
            {variant.overview?.score && <span className="variant-score">{variant.overview.score}分</span>}
            {variant.estimated_budget && <span className="variant-budget">约 ¥{variant.estimated_budget}</span>}
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

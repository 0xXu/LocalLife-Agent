import React from 'react';

type VariantTabsProps = {
  variants: Array<Record<string, any>>;
};

const labels: Record<string, string> = {
  main: '主方案',
  budget: '预算优先',
  comfort: '舒适优先',
  child_first: '儿童优先',
};

export function VariantTabs({ variants }: VariantTabsProps) {
  if (!variants.length) {
    return null;
  }

  return (
    <section className="variant-tabs" aria-label="方案变体">
      <div className="variant-tab-list" role="tablist">
        {variants.map((variant, index) => (
          <button key={variant.id ?? variant.kind} className={index === 0 ? 'active' : ''} type="button" role="tab">
            {labels[variant.kind] ?? variant.title}
          </button>
        ))}
      </div>
      <div className="variant-panels">
        {variants.map((variant) => (
          <article key={variant.id ?? variant.kind} className="variant-panel">
            <header>
              <h3>{labels[variant.kind] ?? variant.title}</h3>
              <span>{variant.overview?.score ?? 0} 分</span>
            </header>
            <p>{variant.summary ?? variant.overview?.estimatedCost}</p>
            <ol>
              {(variant.itinerary ?? []).map((step: Record<string, any>) => (
                <li key={step.id ?? step.place_id}>{step.title}</li>
              ))}
            </ol>
          </article>
        ))}
      </div>
    </section>
  );
}

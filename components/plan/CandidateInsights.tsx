'use client';

import React from 'react';
import { BadgeCheck, CircleDollarSign, MapPin, ShieldCheck, Sparkles, Timer } from 'lucide-react';

type CandidateInsightsProps = {
  candidateSets?: Record<string, Array<Record<string, any>>>;
  validationIssues?: Array<Record<string, any>>;
};

const labels: Record<string, string> = {
  activities: '活动候选',
  restaurants: '餐饮候选',
  walks: '散步候选',
};

const scoreLabels: Record<string, string> = {
  semantic: '偏好',
  distance: '距离',
  quality: '质量',
  wait: '等待',
  budget: '预算',
  provenance: '来源',
  risk: '风险',
};

const scoreIcons: Record<string, typeof Sparkles> = {
  semantic: Sparkles,
  distance: MapPin,
  quality: BadgeCheck,
  wait: Timer,
  budget: CircleDollarSign,
  provenance: ShieldCheck,
};

export function CandidateInsights({ candidateSets = {}, validationIssues = [] }: CandidateInsightsProps) {
  const groups = Object.entries(candidateSets).filter(([, items]) => items?.length);
  if (!groups.length) return null;

  return (
    <section className="candidate-insights">
      <header className="candidate-insights-header">
        <div>
          <span>候选解释</span>
          <h2>为什么选这些点位</h2>
        </div>
        <small>{validationIssues.length ? `${validationIssues.length} 个待检查项` : '校验通过'}</small>
      </header>

      <div className="candidate-groups">
        {groups.map(([key, items], groupIndex) => {
          const top = items[0];
          const place = top?.place ?? {};
          return (
            <article key={key} className="candidate-card" style={{ animationDelay: `${groupIndex * 80}ms` }}>
              <div className="candidate-card-top">
                <span>{labels[key] ?? key}</span>
                <strong>{Math.round(Number(top?.total_score ?? 0) * 100)}%</strong>
              </div>
              <h3>{place.name}</h3>
              <p>{top?.explanation ?? place.reason}</p>
              <div className="candidate-meta">
                <span>{place.distance_km ?? '-'} km</span>
                <span>等待 {place.wait_minutes ?? 0} 分钟</span>
                <span>{place.provenance?.source ?? place.source ?? 'unknown'}</span>
              </div>
              <div className="candidate-score-list">
                {Object.entries(top?.score_breakdown ?? {}).map(([scoreKey, raw]) => {
                  const value = Number(raw);
                  const Icon = scoreIcons[scoreKey] ?? ShieldCheck;
                  const width = Math.max(4, Math.min(100, Math.abs(value) * 320));
                  return (
                    <div key={scoreKey} className={value < 0 ? 'negative' : ''}>
                      <span><Icon size={13} /> {scoreLabels[scoreKey] ?? scoreKey}</span>
                      <b><i style={{ width: `${width}%` }} /></b>
                      <em>{value.toFixed(2)}</em>
                    </div>
                  );
                })}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

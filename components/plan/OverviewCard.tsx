'use client';

import React from 'react';
import { Clock, DollarSign, Footprints, Gauge, Car } from 'lucide-react';

type OverviewCardProps = {
  overview: {
    theme?: string;
    totalDuration?: string;
    driveTime?: string;
    walkingDistance?: string;
    estimatedCost?: string;
    score?: number;
  };
  constraintFit?: Record<string, number>;
};

const fitLabels: Record<string, string> = {
  distance: '距离',
  time: '时间',
  budget: '预算',
  child_friendly: '亲子',
  diet: '饮食',
};

export function OverviewCard({ overview, constraintFit }: OverviewCardProps) {
  const metrics = [
    { icon: Clock, label: '总时长', value: overview.totalDuration },
    { icon: Car, label: '车程', value: overview.driveTime },
    { icon: Footprints, label: '步行', value: overview.walkingDistance },
    { icon: DollarSign, label: '预算', value: overview.estimatedCost },
    { icon: Gauge, label: '评分', value: overview.score ? `${overview.score}分` : undefined },
  ].filter((m) => m.value);
  const fitMetrics = Object.entries(constraintFit ?? {}).filter(([, value]) => typeof value === 'number');

  return (
    <div className="overview-card">
      {overview.theme && <div className="overview-theme">{overview.theme}</div>}
      <div className="overview-metrics">
        {metrics.map((metric, index) => {
          const Icon = metric.icon;
          return (
            <div key={metric.label} className="overview-metric" style={{ animationDelay: `${index * 60}ms` }}>
              <Icon size={16} />
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
            </div>
          );
        })}
      </div>
      {fitMetrics.length > 0 && (
        <div className="overview-fit" aria-label="约束匹配">
          <span className="overview-fit-title">约束匹配</span>
          {fitMetrics.map(([key, value]) => (
            <span key={key} className="overview-fit-chip">
              {fitLabels[key] ?? key}
              <strong>{Math.round(value * 100)}%</strong>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

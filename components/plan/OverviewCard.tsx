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
};

export function OverviewCard({ overview }: OverviewCardProps) {
  const metrics = [
    { icon: Clock, label: '总时长', value: overview.totalDuration },
    { icon: Car, label: '车程', value: overview.driveTime },
    { icon: Footprints, label: '步行', value: overview.walkingDistance },
    { icon: DollarSign, label: '预算', value: overview.estimatedCost },
    { icon: Gauge, label: '评分', value: overview.score ? `${overview.score}分` : undefined },
  ].filter((m) => m.value);

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
    </div>
  );
}

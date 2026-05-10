'use client';

import React from 'react';
import { Car, DollarSign, Footprints, MapPin, Utensils, FlaskConical, TreePine, Timer } from 'lucide-react';

type ItineraryCardProps = {
  step: {
    start?: string;
    end?: string;
    type?: string;
    title: string;
    reason?: string;
    cost?: string;
    travel?: string;
    travel_minutes?: number;
    mode?: string;
    risk?: string[];
  };
  index: number;
  isLast: boolean;
};

const typeIcons: Record<string, React.ComponentType<any>> = {
  transport: Car, activity: FlaskConical, restaurant: Utensils, dessert_walk: TreePine,
};

const typeLabels: Record<string, string> = {
  transport: '交通', activity: '活动', restaurant: '餐厅', dessert_walk: '散步',
};

export function ItineraryCard({ step, index, isLast }: ItineraryCardProps) {
  const Icon = (step.type ? typeIcons[step.type] : undefined) ?? MapPin;
  const typeLabel = (step.type ? typeLabels[step.type] : undefined) ?? step.type ?? '';

  return (
    <div className="itinerary-card" style={{ animationDelay: `${index * 120}ms` }}>
      <div className="itinerary-card-timeline">
        <div className="itinerary-dot"><Icon size={16} /></div>
        {!isLast && <div className="itinerary-line" />}
      </div>
      <div className="itinerary-card-body">
        <div className="itinerary-card-header">
          <div>
            <span className="itinerary-type">{typeLabel}</span>
            <h3>{step.title}</h3>
          </div>
          {(step.start || step.end) && (
            <div className="itinerary-time">
              {step.start && <span>{step.start}</span>}
              {step.end && step.start && <span> - {step.end}</span>}
            </div>
          )}
        </div>
        {step.reason && <p className="itinerary-reason">{step.reason}</p>}
        <div className="itinerary-meta">
          {step.cost && <span><DollarSign size={14} /> {step.cost}</span>}
          {step.travel && <span><Car size={14} /> {step.travel}</span>}
          {step.travel_minutes && !step.travel && <span><Timer size={14} /> {step.travel_minutes}分钟</span>}
          {step.mode && <span><Footprints size={14} /> {step.mode}</span>}
        </div>
        {step.risk && step.risk.length > 0 && (
          <div className="itinerary-risks">
            {step.risk.map((r) => <span key={r} className="itinerary-risk">{r}</span>)}
          </div>
        )}
      </div>
    </div>
  );
}

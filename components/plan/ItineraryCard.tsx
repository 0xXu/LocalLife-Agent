'use client';

import React, { useState } from 'react';
import { Car, DollarSign, Footprints, MapPin, Utensils, FlaskConical, TreePine, Timer, RefreshCw, Loader2 } from 'lucide-react';
import { NODE_TYPE_LABELS } from '../../lib/constants/nodeTypes';

type ItineraryCardProps = {
  step: {
    start?: string;
    end?: string;
    type?: string;
    title: string;
    place_id?: string;
    reason?: string;
    cost?: string;
    travel?: string;
    travel_minutes?: number;
    mode?: string;
    risk?: string | string[];
  };
  index: number;
  isLast: boolean;
  onReplace?: () => void;
};

const typeIcons: Record<string, React.ComponentType<any>> = {
  transport: Car, activity: FlaskConical, restaurant: Utensils, dessert_walk: TreePine,
};

export function ItineraryCard({ step, index, isLast, onReplace }: ItineraryCardProps) {
  const [isReplacing, setIsReplacing] = useState(false);
  const Icon = (step.type ? typeIcons[step.type] : undefined) ?? MapPin;
  const typeLabel = (step.type ? NODE_TYPE_LABELS[step.type] : undefined) ?? step.type ?? '';

  const handleReplace = async () => {
    if (!onReplace) return;
    setIsReplacing(true);
    try {
      await onReplace();
    } finally {
      setIsReplacing(false);
    }
  };

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
          <div className="itinerary-card-actions">
            {(step.start || step.end) && (
              <div className="itinerary-time">
                {step.start && <span>{step.start}</span>}
                {step.end && step.start && <span> - {step.end}</span>}
              </div>
            )}
            {onReplace && step.type !== 'transport' && (
              <button
                className="itinerary-replace-btn"
                onClick={handleReplace}
                disabled={isReplacing}
                title="换一个"
              >
                {isReplacing ? <Loader2 size={14} className="spin" /> : <RefreshCw size={14} />}
                <span>换一个</span>
              </button>
            )}
          </div>
        </div>
        {step.reason && <p className="itinerary-reason">{step.reason}</p>}
        <div className="itinerary-meta">
          {step.cost && <span><DollarSign size={14} /> {step.cost}</span>}
          {step.travel && <span><Car size={14} /> {step.travel}</span>}
          {step.travel_minutes && !step.travel && <span><Timer size={14} /> {step.travel_minutes}分钟</span>}
          {step.mode && <span><Footprints size={14} /> {step.mode}</span>}
        </div>
        {step.risk && (Array.isArray(step.risk) ? step.risk.length > 0 : true) && (
          <div className="itinerary-risks">
            {(Array.isArray(step.risk) ? step.risk : [step.risk]).map((r) => <span key={r} className="itinerary-risk">{r}</span>)}
          </div>
        )}
      </div>
    </div>
  );
}

'use client';

import React from 'react';
import { ItineraryCard } from './ItineraryCard';

type ItineraryTimelineProps = {
  itinerary: Array<Record<string, any> & { title?: string }>;
  onReplaceNode?: (nodeType: string, nodeId: string) => void;
};

export function ItineraryTimeline({ itinerary, onReplaceNode }: ItineraryTimelineProps) {
  if (!itinerary.length) return null;
  return (
    <section className="itinerary-timeline">
      <h2 className="section-title">行程安排</h2>
      <div className="itinerary-list">
        {itinerary.map((step, index) => (
          <ItineraryCard
            key={step.id ?? step.place_id ?? index}
            step={step as any}
            index={index}
            isLast={index === itinerary.length - 1}
            onReplace={onReplaceNode ? () => onReplaceNode(step.type, step.place_id) : undefined}
          />
        ))}
      </div>
    </section>
  );
}

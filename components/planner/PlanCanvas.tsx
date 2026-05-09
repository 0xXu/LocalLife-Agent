import React from 'react';
import { Car, FlaskConical, MapPinned, ReceiptText, Utensils } from 'lucide-react';

import { RoutePreview } from '../RoutePreview';
import { TracePanel } from '../trace/TracePanel';
import { RejectedReasons } from './RejectedReasons';
import { VariantTabs } from './VariantTabs';

type PlanCanvasProps = {
  response: Record<string, any>;
};

export function PlanCanvas({ response }: PlanCanvasProps) {
  const plan = response.plan;
  const rejected = response.trace?.flatMap((span: Record<string, any>) => span.output_summary?.rejected ?? span.output_summary?.rejected_reasons ?? []) ?? [];

  return (
    <section className="plan-canvas">
      <div className="plan-main-column">
        <TracePanel trace={response.trace ?? []} toolCalls={response.tool_calls ?? []} />

        <section className="itinerary-section">
          <h2>主方案</h2>
          <div className="timeline-list">
            {(plan.itinerary ?? []).map((step: Record<string, any>, index: number) => (
              <article key={step.id ?? step.place_id ?? index} className={`itinerary-card ${index === 0 ? 'featured' : ''}`}>
                <div className="timeline-dot">
                  {step.type === 'restaurant' ? <Utensils size={17} /> : <FlaskConical size={17} />}
                </div>
                <div className="itinerary-content">
                  <div className="itinerary-topline">
                    <h3>{step.title}</h3>
                    <span>{step.start} - {step.end}</span>
                  </div>
                  <p>{step.reason}</p>
                  <footer>
                    <span><ReceiptText size={15} /> {step.cost ?? plan.overview?.estimatedCost}</span>
                    <span><Car size={15} /> {step.travel ?? plan.overview?.driveTime}</span>
                  </footer>
                </div>
              </article>
            ))}
          </div>
        </section>

        <VariantTabs variants={plan.variants ?? []} />
        <RejectedReasons rejected={rejected} />
      </div>

      <aside className="map-panel">
        <h2><MapPinned size={18} /> 地图与路线</h2>
        <RoutePreview route={response.route} />
      </aside>
      <div className="route-summary-mobile">地图与路线：{plan.overview?.driveTime}，步行 {plan.overview?.walkingDistance}</div>
    </section>
  );
}

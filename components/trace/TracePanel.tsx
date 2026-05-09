import React from 'react';
import { CheckCircle2, CircleAlert, Clock3, RotateCcw } from 'lucide-react';

import { normalizeTraceEvents } from '../../lib/observability/tracing';
import { ToolCallDetails } from './ToolCallDetails';

type TracePanelProps = {
  trace: Array<Record<string, any>>;
  toolCalls?: Array<Record<string, any>>;
};

export function TracePanel({ trace, toolCalls = [] }: TracePanelProps) {
  const events = normalizeTraceEvents({ trace, tool_calls: toolCalls });

  return (
    <section className="trace-panel">
      <h2>Agent 执行轨迹</h2>
      <ol className="trace-event-list">
        {events.map((event) => {
          const Icon = statusIcon(event.status);
          return (
            <li key={event.id} className={`trace-event ${event.status}`}>
              <div className="trace-event-header">
                <Icon size={16} />
                <strong>{event.message}</strong>
                <span>{event.status}</span>
              </div>
              <div className="trace-event-meta">
                <span>{event.agent}</span>
                {event.tool ? <span>{event.tool}</span> : null}
                {event.duration_ms !== undefined ? <span>{event.duration_ms}ms</span> : null}
                {event.side_effect ? <span className="side-effect-badge">side-effect</span> : null}
                {event.side_effect_id ? <span>{event.side_effect_id}</span> : null}
              </div>
              <ToolCallDetails event={event} />
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function statusIcon(status: string) {
  if (status === 'ok' || status === 'succeeded') {
    return CheckCircle2;
  }
  if (status === 'retrying' || status === 'fallback') {
    return RotateCcw;
  }
  if (status === 'error' || status === 'failed') {
    return CircleAlert;
  }
  return Clock3;
}

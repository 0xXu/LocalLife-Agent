import React from 'react';

import type { NormalizedTraceEvent } from '../../lib/observability/tracing';

type ToolCallDetailsProps = {
  event: NormalizedTraceEvent;
};

export function ToolCallDetails({ event }: ToolCallDetailsProps) {
  return (
    <details className="tool-call-details" open>
      <summary>{event.tool ?? event.agent}</summary>
      <div className="tool-json-grid">
        <JsonBlock label="input" value={event.input_json} />
        <JsonBlock label="output" value={event.output_json} />
        {event.error_json ? <JsonBlock label="error" value={event.error_json} /> : null}
      </div>
    </details>
  );
}

function JsonBlock({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <code dangerouslySetInnerHTML={{ __html: safeJsonHtml(value) }} />
    </div>
  );
}

function safeJsonHtml(value: string) {
  return value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
}

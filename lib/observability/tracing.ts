export type RawTraceInput = {
  trace?: Array<Record<string, any>>;
  tool_calls?: Array<Record<string, any>>;
};

export type NormalizedTraceEvent = {
  id: string;
  kind: 'trace' | 'tool_call';
  backend_kind?: string;
  message: string;
  agent: string;
  tool?: string;
  status: string;
  duration_ms?: number;
  input_summary: Record<string, any>;
  output_summary: Record<string, any>;
  error?: unknown;
  input_json: string;
  output_json: string;
  error_json?: string;
  side_effect: boolean;
  side_effect_id?: string;
};

export function normalizeTraceEvents(input: RawTraceInput): NormalizedTraceEvent[] {
  const traces = (input.trace ?? []).map((event, index) => normalizeEvent(event, 'trace', index));
  const toolCalls = (input.tool_calls ?? []).map((event, index) => normalizeEvent(event, 'tool_call', index));
  return [...traces, ...toolCalls];
}

function normalizeEvent(event: Record<string, any>, kind: NormalizedTraceEvent['kind'], index: number): NormalizedTraceEvent {
  const tool = event.tool ? String(event.tool) : undefined;
  const agent = String(event.agent ?? (kind === 'tool_call' ? 'Tool Executor' : 'Agent'));
  const message = String(event.message ?? event.summary ?? event.name ?? tool ?? agent);
  const sideEffectId = event.side_effect_id ?? event.idempotency_key ?? event.idempotencyKey;
  const inputSummary = event.input_summary ?? event.input ?? {};
  const outputSummary = event.output_summary ?? event.output ?? {};

  return {
    id: String(event.id ?? `${kind}_${tool ?? agent}_${index}`),
    kind,
    backend_kind: typeof event.kind === 'string' && kind === 'trace' ? event.kind : undefined,
    message,
    agent,
    tool,
    status: String(event.status ?? 'pending'),
    duration_ms: typeof event.duration_ms === 'number' ? event.duration_ms : undefined,
    input_summary: inputSummary,
    output_summary: outputSummary,
    error: event.error,
    input_json: stableJson(inputSummary),
    output_json: stableJson(outputSummary),
    error_json: event.error === undefined ? undefined : stableJson(event.error),
    side_effect: Boolean(event.side_effect ?? sideEffectId),
    side_effect_id: sideEffectId ? String(sideEffectId) : undefined,
  };
}

function stableJson(value: unknown) {
  return JSON.stringify(value ?? {});
}

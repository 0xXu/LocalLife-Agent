import { normalizeTraceEvents, type NormalizedTraceEvent, type RawTraceInput } from '../../observability/tracing';

export type TraceRecord = {
  plan_id: string;
  span_id: string;
  kind: NormalizedTraceEvent['kind'];
  agent: string;
  tool?: string;
  message: string;
  input_summary: Record<string, any>;
  output_summary: Record<string, any>;
  error?: unknown;
  status: string;
  duration_ms?: number;
  side_effect: boolean;
  side_effect_id?: string;
  created_at?: string;
};

export type ExecutionRecord = {
  id: string;
  plan_id: string;
  tool: string;
  status: string;
  request: Record<string, any>;
  response: Record<string, any>;
  receipt: Record<string, any>;
  created_at?: string;
};

export type TraceRepository = {
  append(planId: string, event: Record<string, any>): Promise<TraceRecord>;
  appendMany(planId: string, input: RawTraceInput): Promise<TraceRecord[]>;
  list(planId: string): Promise<TraceRecord[]>;
  listExecutions(planId: string): Promise<ExecutionRecord[]>;
};

export function createTestTraceRepository(): TraceRepository {
  const traces: TraceRecord[] = [];
  const executions: ExecutionRecord[] = [];

  return {
    async append(planId, event) {
      const normalized = normalizeTraceEvents({ tool_calls: [event] })[0];
      const record = toTraceRecord(planId, normalized);
      traces.push(record);
      if (record.side_effect && record.output_summary.id) {
        executions.push(toExecutionRecord(record));
      }
      return clone(record);
    },
    async appendMany(planId, input) {
      const records = normalizeTraceEvents(input).map((event) => toTraceRecord(planId, event));
      traces.push(...records);
      executions.push(...records.filter((record) => record.side_effect && record.output_summary.id).map(toExecutionRecord));
      return clone(records);
    },
    async list(planId) {
      return clone(traces.filter((record) => record.plan_id === planId));
    },
    async listExecutions(planId) {
      return clone(executions.filter((record) => record.plan_id === planId));
    },
  };
}

function toTraceRecord(planId: string, event: NormalizedTraceEvent): TraceRecord {
  return {
    plan_id: planId,
    span_id: event.id,
    kind: event.kind,
    agent: event.agent,
    tool: event.tool,
    message: event.message,
    input_summary: event.input_summary,
    output_summary: event.output_summary,
    error: event.error,
    status: event.status,
    duration_ms: event.duration_ms,
    side_effect: event.side_effect,
    side_effect_id: event.side_effect_id,
    created_at: new Date().toISOString(),
  };
}

function toExecutionRecord(record: TraceRecord): ExecutionRecord {
  const receipt = record.output_summary.id ? { id: record.output_summary.id, ...record.output_summary } : record.output_summary;
  return {
    id: String(receipt.id ?? `${record.plan_id}_${record.span_id}`),
    plan_id: record.plan_id,
    tool: record.tool ?? 'unknown_tool',
    status: record.status,
    request: record.input_summary,
    response: record.output_summary,
    receipt,
    created_at: record.created_at,
  };
}

function clone<T>(value: T): T {
  return value === undefined ? value : JSON.parse(JSON.stringify(value));
}

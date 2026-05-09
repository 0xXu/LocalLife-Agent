import type { ToolCall } from '../../types/weekendpilot';

export type WeekendPilotTelemetry = {
  enabled: boolean;
  serviceName: string;
};

export type WeekendPilotSpan = {
  name: string;
  attributes: Record<string, unknown>;
  enabled: boolean;
  setAttribute: (key: string, value: unknown) => void;
  end: () => void;
};

type TelemetryEnv = Record<string, string | undefined>;

export function startWeekendPilotTelemetry(env: TelemetryEnv = process.env): WeekendPilotTelemetry {
  const enabled = env.WEEKENDPILOT_OTEL_ENABLED === 'true' || Boolean(env.OTEL_EXPORTER_OTLP_ENDPOINT);
  return {
    enabled,
    serviceName: env.OTEL_SERVICE_NAME ?? 'weekendpilot-planner',
  };
}

export function createSpan(name: string, attributes: Record<string, unknown> = {}, env: TelemetryEnv = process.env): WeekendPilotSpan {
  const telemetry = startWeekendPilotTelemetry(env);
  const spanAttributes = { ...attributes };
  return {
    name,
    attributes: spanAttributes,
    enabled: telemetry.enabled,
    setAttribute(key: string, value: unknown) {
      spanAttributes[key] = value;
    },
    end() {
      spanAttributes.ended = true;
    },
  };
}

export function recordToolCall(spanName: string, payload: ToolCall, env: TelemetryEnv = process.env) {
  const span = createSpan(spanName, {
    tool: payload.tool,
    status: payload.status,
    side_effect: payload.side_effect,
  }, env);
  span.setAttribute('duration_ms', payload.duration_ms ?? 0);
  span.end();
  return span;
}

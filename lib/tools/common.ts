import type { Receipt } from '../../types/weekendpilot';

export type JsonSchema = Record<string, unknown>;

export type ToolSchema = {
  name: string;
  input_schema: JsonSchema;
  output_schema: JsonSchema;
  side_effect: boolean;
  requires_confirmation: boolean;
};

export type ToolAdapter = {
  schema: ToolSchema;
  execute(input: Record<string, any>, context?: Record<string, any>): Promise<Record<string, any> | Receipt>;
};

export function readOnlyTool(name: string, execute: ToolAdapter['execute'] = async (input) => ({ ok: true, input_summary: input })) {
  return {
    schema: baseSchema(name, false),
    execute,
  };
}

export function sideEffectTool(name: string, prefix: string, payload: (input: Record<string, any>) => Record<string, any>): ToolAdapter {
  return {
    schema: baseSchema(name, true),
    async execute(input, context = {}) {
      ensureConfirmed(context);
      return {
        type: String(input.type ?? name),
        tool: name,
        id: `${prefix}-${stableSuffix(context.idempotencyKey, name)}`,
        status: 'confirmed',
        detail: String(input.detail ?? `${name} completed`),
        payload: payload(input),
      };
    },
  };
}

function baseSchema(name: string, sideEffect: boolean): ToolSchema {
  return {
    name,
    input_schema: { type: 'object', additionalProperties: true },
    output_schema: { type: 'object', additionalProperties: true },
    side_effect: sideEffect,
    requires_confirmation: sideEffect,
  };
}

function ensureConfirmed(context: Record<string, any>) {
  if (context.confirmed !== true) {
    throw new Error('confirmation_required');
  }
  if (!context.idempotencyKey) {
    throw new Error('idempotency_key_required');
  }
  if (!context.humanConfirmationSnapshot) {
    throw new Error('human_confirmation_snapshot_required');
  }
}

function stableSuffix(idempotencyKey: unknown, tool: string) {
  const raw = `${String(idempotencyKey)}:${tool}`;
  let hash = 0;
  for (const char of raw) {
    hash = (hash * 31 + char.charCodeAt(0)) % 10000;
  }
  return String(hash).padStart(4, '0');
}

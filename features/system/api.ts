import { apiRequest } from '../../lib/api/client';

export interface LlmStatus {
  provider: string;
  protocol: string;
  base_url: string;
  model: string;
  api_key: string;
  configured: boolean;
  remote_enabled: boolean;
  response_format: string;
  disable_thinking: boolean;
}

export async function getLlmStatus() {
  return apiRequest<LlmStatus>('/api/llm/status');
}

export async function getToolSchemas() {
  return apiRequest<{ tools: Array<Record<string, unknown>> }>('/api/tool-schemas');
}

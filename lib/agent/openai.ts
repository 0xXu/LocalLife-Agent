import OpenAI from 'openai';

export type ResponsesLikeClient = {
  responses: {
    create(input: Record<string, unknown>): Promise<{ output_text?: string } | Record<string, unknown>>;
  };
};

export type OpenAIPlannerConfig = {
  apiKey: string;
  model: string;
  baseURL?: string;
  responsesEnabled: boolean;
};

export function loadOpenAIPlannerConfig(env: NodeJS.ProcessEnv = process.env): OpenAIPlannerConfig {
  return {
    apiKey: env.OPENAI_API_KEY ?? '',
    model: env.OPENAI_MODEL ?? 'gpt-4.1-mini',
    baseURL: env.OPENAI_BASE_URL || undefined,
    responsesEnabled: env.OPENAI_RESPONSES_ENABLED === 'true',
  };
}

export function createOpenAIClient(config = loadOpenAIPlannerConfig()): ResponsesLikeClient | null {
  if (!config.responsesEnabled || !config.apiKey) {
    return null;
  }

  return new OpenAI({
    apiKey: config.apiKey,
    baseURL: config.baseURL,
  }) as unknown as ResponsesLikeClient;
}

export function responseOutputText(response: Record<string, unknown>): string {
  if (typeof response.output_text === 'string') {
    return response.output_text;
  }

  const output = response.output;
  if (Array.isArray(output)) {
    const text = output
      .flatMap((item) => {
        if (!item || typeof item !== 'object') {
          return [];
        }
        const content = (item as { content?: unknown }).content;
        if (!Array.isArray(content)) {
          return [];
        }
        return content
          .map((contentItem) => {
            if (!contentItem || typeof contentItem !== 'object') {
              return '';
            }
            const record = contentItem as { text?: unknown };
            return typeof record.text === 'string' ? record.text : '';
          })
          .filter(Boolean);
      })
      .join('\n');
    if (text) {
      return text;
    }
  }

  throw new Error('responses_output_text_missing');
}

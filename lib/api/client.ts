type ApiRequestOptions = {
  method?: 'GET' | 'POST' | 'PATCH';
  body?: Record<string, unknown>;
};

const DEFAULT_API_URL = 'http://127.0.0.1:8787';

export function resolveApiUrl(path: string) {
  if (/^https?:\/\//i.test(path)) {
    return path;
  }

  const baseUrl = (process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_URL).replace(/\/+$/, '');
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${baseUrl}${normalizedPath}`;
}

export async function apiRequest<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const response = await fetch(resolveApiUrl(path), {
    method: options.method ?? 'GET',
    headers: options.body ? { 'content-type': 'application/json' } : undefined,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const data = await readJson(response);

  if (!response.ok) {
    throw new Error(formatApiError(data, response));
  }

  return data as T;
}

async function readJson(response: Response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function formatApiError(data: unknown, response: Response) {
  if (isRecord(data)) {
    const error = data.error;
    if (isRecord(error)) {
      const code = typeof error.code === 'string' ? error.code : response.status;
      const message = typeof error.message === 'string' ? error.message : response.statusText;
      return `${code}: ${message}`;
    }
    if (typeof error === 'string') {
      return `${error}: ${error}`;
    }
  }

  return `${response.status}: ${response.statusText}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export async function api<T>(path: string, token?: string | null, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  let response: Response;
  try {
    response = await fetch('/api/v1' + path, {...options, headers, credentials: 'same-origin'});
  } catch {
    throw new ApiError('Cannot reach FastAPI. Check that the backend is running on port 8000.', 0);
  }
  if (!response.ok) {
    let message = `Request failed (HTTP ${response.status})`;
    try {
      const body = await response.json();
      if (typeof body.detail === 'string') message = body.detail;
      else if (Array.isArray(body.detail)) message = body.detail.map((item: {msg?:string}) => item.msg ?? 'Invalid input').join('; ');
    } catch { /* Keep status message. */ }
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const json = (body: object): RequestInit => ({method:'POST',body:JSON.stringify(body)});
export const isoToday = () => new Date().toLocaleDateString('en-CA');
export function idem(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : `batchtrace-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
export function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong. Please try again.';
}

import { Injectable } from '@angular/core';

const API = '/addon/api';

/** A non-2xx answer of the add-on: the status and what its body said (reason, wait, messages). */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail?: string,
    readonly wait?: number,
    readonly errors?: string[],
    readonly backup?: string,
  ) {
    super(detail ?? String(status));
  }
}

@Injectable({ providedIn: 'root' })
export class Api {
  get<T>(path: string): Promise<T> {
    return this.send<T>('GET', path);
  }
  post<T>(path: string, body: unknown): Promise<T> {
    return this.send<T>('POST', path, body);
  }
  put<T>(path: string, body: unknown): Promise<T> {
    return this.send<T>('PUT', path, body);
  }

  private async send<T>(method: string, path: string, body?: unknown): Promise<T> {
    const write = method !== 'GET';
    const resp = await fetch(API + path, {
      method,
      credentials: 'same-origin',
      ...(write
        ? {
            headers: { 'Content-Type': 'application/json', 'X-Addon': '1' },
            body: JSON.stringify(body),
          }
        : {}),
    });
    if (!resp.ok) {
      const b = (await resp.json().catch(() => ({}))) as Record<string, never>;
      throw new ApiError(resp.status, b['detail'], b['retry_after'], b['errors'], b['backup']);
    }
    return (await resp.json()) as T;
  }
}

import { Injectable, inject, signal } from '@angular/core';

const BASE = /^\/addon\/([a-z0-9-]+\/)?$/;

/** The public base of the served bundle (`/addon/<key>/main.js` -> `/addon/<key>/`); `/addon/` anywhere else. */
export function baseFromUrl(url: string): string {
  try {
    const p = new URL('.', url).pathname;
    return BASE.test(p) ? p : '/addon/';
  } catch {
    return '/addon/';
  }
}

/** Where the site exposes this add-on: set from the bundle url, overridden by the element's `base` attribute. */
@Injectable({ providedIn: 'root' })
export class ApiBase {
  readonly base = signal(baseFromUrl(import.meta.url));
  /** An invalid value is ignored, so a URL is never built from unchecked input. */
  set(value: string | null | undefined): void {
    if (value && BASE.test(value)) this.base.set(value);
  }
}

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
  private readonly apiBase = inject(ApiBase);
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
    const resp = await fetch(this.apiBase.base() + 'api' + path, {
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

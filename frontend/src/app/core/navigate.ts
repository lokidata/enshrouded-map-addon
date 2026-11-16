import { InjectionToken } from '@angular/core';

/** Where a download goes: the browser leaves the page for the signed URL. Replaced in tests. */
export const NAVIGATE = new InjectionToken<(url: string) => void>('navigate', {
  providedIn: 'root',
  factory: () => (url: string) => window.location.assign(url),
});

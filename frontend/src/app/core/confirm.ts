import { Injectable, signal } from '@angular/core';

export interface ConfirmOptions {
  title: string;
  label: string; // the sentence next to the checkbox the user must tick
}
interface Pending extends ConfirmOptions {
  done: (ok: boolean) => void;
}

/** One confirmation at a time: ask() resolves true only when the box is ticked and OK pressed. */
@Injectable({ providedIn: 'root' })
export class Confirm {
  readonly request = signal<Pending | null>(null);

  ask(opts: ConfirmOptions): Promise<boolean> {
    return new Promise((resolve) => {
      this.request.set({
        ...opts,
        done: (ok) => {
          this.request.set(null);
          resolve(ok);
        },
      });
    });
  }
}

import { Component, OnInit, computed, input, signal } from '@angular/core';

/** A collapsible plate. The open state is remembered per key; storage may be missing. */
@Component({
  selector: 'app-section',
  template: `
    <details class="sec" [open]="isOpen()" (toggle)="onToggle($event)">
      <summary>{{ heading() }}</summary>
      <div class="sec-body"><ng-content /></div>
    </details>
  `,
})
export class Section implements OnInit {
  readonly heading = input.required<string>();
  readonly storageKey = input.required<string>();
  readonly open = input(false);
  private readonly saved = signal<boolean | null>(null);
  protected readonly isOpen = computed(() => this.saved() ?? this.open());

  ngOnInit(): void {
    this.saved.set(this.read());
  }

  protected onToggle(e: Event): void {
    const now = (e.target as HTMLDetailsElement).open;
    this.saved.set(now);
    try {
      localStorage.setItem(this.key(), now ? '1' : '0');
    } catch {
      /* storage unavailable: the default applies next time */
    }
  }

  private key(): string {
    return 'addon-section-' + this.storageKey();
  }

  private read(): boolean | null {
    try {
      const v = localStorage.getItem(this.key());
      return v === null ? null : v === '1';
    } catch {
      return null;
    }
  }
}

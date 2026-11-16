import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Section } from './section';

@Component({
  imports: [Section],
  template: `<app-section heading="Un" storageKey="k1" [open]="true">a</app-section>
    <app-section heading="Deux" storageKey="k2">b</app-section>`,
})
class Host {}

function render() {
  const f = TestBed.createComponent(Host);
  f.detectChanges();
  return [...(f.nativeElement as HTMLElement).querySelectorAll('details')];
}

describe('Section', () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => vi.restoreAllMocks());

  it('opens the first and closes the second by default', () => {
    const [a, b] = render();
    expect([a.open, b.open]).toEqual([true, false]);
  });

  it('restores the remembered state', () => {
    localStorage.setItem('addon-section-k1', '0');
    localStorage.setItem('addon-section-k2', '1');
    const [a, b] = render();
    expect([a.open, b.open]).toEqual([false, true]);
  });

  it('keeps the defaults when storage throws', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('denied');
    });
    const [a, b] = render();
    expect([a.open, b.open]).toEqual([true, false]);
  });

  it('remembers a toggle', () => {
    const [, b] = render();
    b.open = true;
    b.dispatchEvent(new Event('toggle'));
    expect(localStorage.getItem('addon-section-k2')).toBe('1');
  });
});

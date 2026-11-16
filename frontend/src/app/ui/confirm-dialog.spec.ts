import { TestBed } from '@angular/core/testing';
import { Confirm } from '../core/confirm';
import { ConfirmDialog } from './confirm-dialog';

beforeAll(() => {
  // jsdom has no modal dialogs
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.setAttribute('open', '');
  };
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    this.removeAttribute('open');
  };
});

function setup() {
  const fx = TestBed.createComponent(ConfirmDialog);
  fx.detectChanges();
  const el = fx.nativeElement as HTMLElement;
  return { fx, el, confirm: TestBed.inject(Confirm) };
}
const ok = (el: HTMLElement) => el.querySelector('button.ok') as HTMLButtonElement;

describe('ConfirmDialog', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('keeps OK disabled until the box is ticked, then resolves true', async () => {
    const { fx, el, confirm } = setup();
    const answer = confirm.ask({ title: 'Arrêter ?', label: 'Prévenus' });
    fx.detectChanges();
    expect(el.textContent).toContain('Arrêter ?');
    expect(ok(el).disabled).toBe(true);
    const box = el.querySelector('input') as HTMLInputElement;
    box.checked = true;
    box.dispatchEvent(new Event('change'));
    fx.detectChanges();
    expect(ok(el).disabled).toBe(false);
    ok(el).click();
    expect(await answer).toBe(true);
  });

  it('cancel resolves false', async () => {
    const { fx, el, confirm } = setup();
    const answer = confirm.ask({ title: 'T', label: 'L' });
    fx.detectChanges();
    (el.querySelector('button.cancel') as HTMLButtonElement).click();
    expect(await answer).toBe(false);
  });

  it('Escape (close event) resolves false', async () => {
    const { fx, el, confirm } = setup();
    const answer = confirm.ask({ title: 'T', label: 'L' });
    fx.detectChanges();
    el.querySelector('dialog')!.dispatchEvent(new Event('close'));
    expect(await answer).toBe(false);
  });

  it('a second question starts with the box unticked', async () => {
    const { fx, el, confirm } = setup();
    void confirm.ask({ title: 'A', label: 'L' });
    fx.detectChanges();
    const box = el.querySelector('input') as HTMLInputElement;
    box.checked = true;
    box.dispatchEvent(new Event('change'));
    fx.detectChanges();
    ok(el).click();
    void confirm.ask({ title: 'B', label: 'L' });
    fx.detectChanges();
    expect(ok(el).disabled).toBe(true);
  });
});

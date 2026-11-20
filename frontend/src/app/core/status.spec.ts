import { TestBed } from '@angular/core/testing';
import { Api, ApiError } from './api';
import { Status } from './status';

const info = {
  name: 'S',
  state: 'running',
  cpu: 1.5,
  memory_bytes: 1,
  disk_bytes: 2,
  uptime_ms: 3,
};

function make(get: () => Promise<unknown>) {
  TestBed.configureTestingModule({ providers: [{ provide: Api, useValue: { get } }] });
  return TestBed.inject(Status);
}

describe('Status', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    TestBed.resetTestingModule();
  });

  it('starts unknown, then follows the server', async () => {
    const s = make(() => Promise.resolve(info));
    expect(s.state()).toBe('unknown');
    await s.refresh();
    expect(s.state()).toBe('running');
    expect(s.info()).toEqual(info);
    expect(s.error()).toBe('');
  });

  it('a failed read puts the state back to unknown and says why', async () => {
    let ok = true;
    const s = make(() =>
      ok ? Promise.resolve(info) : Promise.reject(new ApiError(502, 'pelican_unavailable')),
    );
    await s.refresh();
    ok = false;
    await s.refresh();
    expect(s.state()).toBe('unknown');
    expect(s.error()).toBe('Le panneau du serveur est injoignable.');
  });

  it('two refreshes at once make one request', async () => {
    const get = vi.fn(() => Promise.resolve(info));
    const s = make(get);
    await Promise.all([s.refresh(), s.refresh()]);
    expect(get).toHaveBeenCalledTimes(1);
  });

  it('the poll does nothing while the tab is hidden', async () => {
    const get = vi.fn(() => Promise.resolve(info));
    const s = make(get);
    vi.spyOn(document, 'hidden', 'get').mockReturnValue(true);
    await s.tick();
    expect(get).not.toHaveBeenCalled();
    vi.spyOn(document, 'hidden', 'get').mockReturnValue(false);
    await s.tick();
    expect(get).toHaveBeenCalledTimes(1);
  });

  it('setActive(false) stops the poll, setActive(true) reads again at once', async () => {
    vi.useFakeTimers();
    const get = vi.fn(() => Promise.resolve(info));
    const s = make(get);
    s.setActive(true);
    await vi.advanceTimersByTimeAsync(0);
    expect(get).toHaveBeenCalledTimes(1);
    s.setActive(false);
    await vi.advanceTimersByTimeAsync(60000);
    expect(get).toHaveBeenCalledTimes(1);
    s.setActive(true);
    await vi.advanceTimersByTimeAsync(0);
    expect(get).toHaveBeenCalledTimes(2);
    s.setActive(false);
    vi.useRealTimers();
  });
});

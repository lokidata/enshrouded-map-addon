import { TestBed } from '@angular/core/testing';
import { Api, ApiError } from './api';

function reply(status: number, body: unknown = {}) {
  const fn = vi
    .fn()
    .mockImplementation(() => Promise.resolve(new Response(JSON.stringify(body), { status })));
  vi.stubGlobal('fetch', fn);
  return fn;
}

describe('Api', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('reads relative to /addon/api with the session cookie', async () => {
    const fn = reply(200, { a: 1 });
    expect(await TestBed.inject(Api).get('/me')).toEqual({ a: 1 });
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe('/addon/api/me');
    expect(init.credentials).toBe('same-origin');
  });

  it('sends the CSRF header and JSON on writes only', async () => {
    const fn = reply(200);
    await TestBed.inject(Api).post('/power', { signal: 'stop', confirm: true });
    const init = fn.mock.calls[0][1];
    expect(init.method).toBe('POST');
    expect(init.headers['X-Addon']).toBe('1');
    expect(init.headers['Content-Type']).toBe('application/json');
    expect(init.body).toBe('{"signal":"stop","confirm":true}');
    await TestBed.inject(Api).get('/me');
    expect(fn.mock.calls[1][1].headers?.['X-Addon']).toBeUndefined();
  });

  it('puts with the same guard', async () => {
    const fn = reply(200);
    await TestBed.inject(Api).put('/access/1%3Ax', { level: null });
    expect(fn.mock.calls[0][1].method).toBe('PUT');
    expect(fn.mock.calls[0][1].headers['X-Addon']).toBe('1');
  });

  it('turns a refusal into an ApiError keeping detail, wait, errors and backup', async () => {
    reply(429, { detail: 'rate_limited', retry_after: 12 });
    const err = await TestBed.inject(Api)
      .get('/x')
      .catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 429, detail: 'rate_limited', wait: 12 });
    reply(422, { detail: 'invalid', errors: ['a'], backup: 'f.bak-1' });
    expect(
      await TestBed.inject(Api)
        .put('/x', {})
        .catch((e: unknown) => e),
    ).toMatchObject({
      status: 422,
      errors: ['a'],
      backup: 'f.bak-1',
    });
  });

  it('survives an error body that is not JSON', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<html>', { status: 502 })));
    expect(
      await TestBed.inject(Api)
        .get('/x')
        .catch((e: unknown) => e),
    ).toMatchObject({
      status: 502,
    });
  });
});

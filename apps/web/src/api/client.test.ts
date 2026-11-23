import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, getAccessToken, setAccessToken } from './client'

/* The client is the only place the frontend talks to the API, so its error
   handling is unit-tested against a stubbed fetch. */

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
  } as Response
}

describe('api client', () => {
  beforeEach(() => {
    setAccessToken(null)
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('starts with no token', () => {
    expect(getAccessToken()).toBeNull()
  })

  it('stores a token in memory only', () => {
    // The client keeps the token in a module variable. If it ever tried to
    // persist the token it would touch localStorage/sessionStorage/cookies,
    // none of which exist in this Node test environment - so a throw here is
    // the regression signal that the token started being persisted.
    expect(() => setAccessToken('abc123')).not.toThrow()
    expect(getAccessToken()).toBe('abc123')
  })

  it('sends the Authorization header when a token is present', async () => {
    setAccessToken('abc123')
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, { id: 1, roles: [] }))
    vi.stubGlobal('fetch', fetchMock)

    const { fetchMe } = await import('./client')
    await fetchMe()

    const [, init] = fetchMock.mock.calls[0]
    expect((init.headers as Headers).get('Authorization')).toBe('Bearer abc123')
  })

  it('omits the Authorization header when signed out', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, { id: 1, roles: [] }))
    vi.stubGlobal('fetch', fetchMock)

    const { fetchMe } = await import('./client')
    await fetchMe()

    const [, init] = fetchMock.mock.calls[0]
    expect((init.headers as Headers).has('Authorization')).toBe(false)
  })

  it('surfaces the backend error message', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse(429, { error: { code: 'rate_limited', message: 'Too many codes.' } }),
      ),
    )

    const { requestOtp } = await import('./client')
    await expect(requestOtp('9876543210')).rejects.toMatchObject({
      status: 429,
      code: 'rate_limited',
      message: 'Too many codes.',
    })
  })

  it('reports a network failure as a distinct error', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockRejectedValue(new TypeError('Failed to fetch')),
    )

    const { requestOtp } = await import('./client')
    await expect(requestOtp('9876543210')).rejects.toMatchObject({
      status: 0,
      code: 'network_error',
    })
  })

  it('falls back to a safe message when the body is not JSON', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        text: async () => '<html>Internal Server Error</html>',
      } as Response),
    )

    const { requestOtp } = await import('./client')
    const error = await requestOtp('9876543210').catch((caught) => caught)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).message).toBe('The request could not be completed.')
  })

  it('never leaks an HTML error page into the message', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        text: async () => '<html><body>secret traceback</body></html>',
      } as Response),
    )

    const { requestOtp } = await import('./client')
    const error = (await requestOtp('9876543210').catch((caught) => caught)) as ApiError
    expect(error.message).not.toContain('traceback')
  })
})
/**
 * Tests for the API client's token handling and 401-refresh-retry flow — the piece of
 * frontend logic that silently breaks every authenticated screen when it regresses.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api, clearTokens, getAccessToken, setTokens } from "../lib/api";

/** Minimal localStorage stand-in; vitest runs in the node environment here. */
class MemoryStorage {
  private store = new Map<string, string>();
  getItem(key: string) {
    return this.store.get(key) ?? null;
  }
  setItem(key: string, value: string) {
    this.store.set(key, value);
  }
  removeItem(key: string) {
    this.store.delete(key);
  }
  clear() {
    this.store.clear();
  }
}

const ACCESS_KEY = "nenu_access_token";
const REFRESH_KEY = "nenu_refresh_token";

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? "OK" : "Error",
    json: async () => body,
  } as unknown as Response;
}

describe("token storage", () => {
  beforeEach(() => {
    (globalThis as { localStorage?: unknown }).localStorage = new MemoryStorage();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("round-trips the access token", () => {
    setTokens("access-1", "refresh-1");

    expect(getAccessToken()).toBe("access-1");
    expect((globalThis.localStorage as unknown as MemoryStorage).getItem(REFRESH_KEY)).toBe("refresh-1");
  });

  it("clears both tokens on logout", () => {
    setTokens("access-1", "refresh-1");

    clearTokens();

    expect(getAccessToken()).toBeNull();
    expect((globalThis.localStorage as unknown as MemoryStorage).getItem(REFRESH_KEY)).toBeNull();
  });
});

describe("request handling", () => {
  beforeEach(() => {
    (globalThis as { localStorage?: unknown }).localStorage = new MemoryStorage();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("attaches the bearer token when one is stored", async () => {
    setTokens("access-1", "refresh-1");
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    await api.get<{ ok: boolean }>("/agents");

    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers.Authorization).toBe("Bearer access-1");
  });

  it("refreshes once on 401 and retries with the new token", async () => {
    setTokens("stale", "refresh-1");

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ detail: "expired" }, 401))
      .mockResolvedValueOnce(
        jsonResponse({ access_token: "fresh", refresh_token: "refresh-2" }),
      )
      .mockResolvedValueOnce(jsonResponse([{ id: "a1" }]));
    vi.stubGlobal("fetch", fetchMock);

    const result = await api.get<{ id: string }[]>("/agents");

    expect(result).toEqual([{ id: "a1" }]);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(getAccessToken()).toBe("fresh");

    const retryInit = fetchMock.mock.calls[2][1];
    expect(retryInit.headers.Authorization).toBe("Bearer fresh");
  });

  it("clears tokens and surfaces the error when refresh fails", async () => {
    setTokens("stale", "refresh-1");

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ detail: "expired" }, 401))
      .mockResolvedValueOnce(jsonResponse({ detail: "invalid refresh" }, 401))
      .mockResolvedValueOnce(jsonResponse({ detail: "expired" }, 401));
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.get("/agents")).rejects.toThrow();
    expect(getAccessToken()).toBeNull();
  });

  it("raises ApiError with the server detail message", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ detail: "Lead not found" }, 404));
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.get("/leads/missing")).rejects.toThrow("Lead not found");
  });

  it("does not send a body when none is supplied", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({}, 200));
    vi.stubGlobal("fetch", fetchMock);

    await api.post("/calls/abc/analyze");

    expect(fetchMock.mock.calls[0][1].body).toBeUndefined();
  });
});
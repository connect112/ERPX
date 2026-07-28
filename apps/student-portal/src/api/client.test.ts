/**
 * Unit tests for the central Axios client's auth-header attachment and
 * 401 -> refresh -> retry interceptor logic (src/api/client.ts).
 *
 * This file is byte-identical to apps/web/src/api/client.ts (confirmed
 * during the production-readiness audit), so this test suite mirrors
 * apps/web/src/api/client.test.ts's proven coverage rather than
 * reinventing it — student-portal is nonetheless a separately built and
 * shipped app with its own bundle, so it needs its own real test run, not
 * just a reference to apps/web's.
 *
 * Only the HTTP layer is mocked (via axios-mock-adapter, attached to the
 * real `apiClient`/`axios` instances' adapters) — the interceptors
 * themselves and the real Zustand auth store both run unmocked, so these
 * tests exercise the actual production code path, not a stand-in for it.
 */

import axios from "axios";
import MockAdapter from "axios-mock-adapter";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "./client";
import { useAuthStore } from "@/store/auth-store";

let mock: MockAdapter;
// client.ts's refresh call deliberately goes through the bare `axios`
// import, not `apiClient` (so a request already flagged `_retry` can't
// recursively re-enter apiClient's own interceptors) — mocked separately
// here for exactly that reason, mirroring the real request path rather
// than papering over it with a single shared mock.
let globalAxiosMock: MockAdapter;

beforeEach(() => {
  mock = new MockAdapter(apiClient);
  globalAxiosMock = new MockAdapter(axios);
  useAuthStore.setState({
    accessToken: null,
    refreshToken: null,
    user: null,
    isAuthenticated: false,
  });
});

afterEach(() => {
  mock.restore();
  globalAxiosMock.restore();
  vi.restoreAllMocks();
});

describe("request interceptor", () => {
  it("attaches the Authorization header when an access token is present", async () => {
    useAuthStore.setState({ accessToken: "token-abc", isAuthenticated: true });
    mock.onGet("/ping").reply((config) => {
      expect(config.headers?.Authorization).toBe("Bearer token-abc");
      return [200, { ok: true }];
    });

    const response = await apiClient.get("/ping");
    expect(response.data).toEqual({ ok: true });
  });

  it("does not attach an Authorization header when there is no access token", async () => {
    mock.onGet("/ping").reply((config) => {
      expect(config.headers?.Authorization).toBeUndefined();
      return [200, { ok: true }];
    });

    await apiClient.get("/ping");
  });
});

describe("response interceptor — non-401 errors", () => {
  it("passes through a 500 error unchanged, without attempting a refresh", async () => {
    const refreshSpy = vi.fn();
    globalAxiosMock.onPost(new RegExp("/auth/refresh$")).reply(() => {
      refreshSpy();
      return [200, { access_token: "new", refresh_token: "new-r" }];
    });
    mock.onGet("/broken").reply(500, { detail: "server error" });

    await expect(apiClient.get("/broken")).rejects.toMatchObject({
      response: { status: 500 },
    });
    expect(refreshSpy).not.toHaveBeenCalled();
  });
});

describe("response interceptor — 401 with no refresh token", () => {
  it("logs out and rejects without calling the refresh endpoint", async () => {
    useAuthStore.setState({ accessToken: "expired", refreshToken: null, isAuthenticated: true });
    const refreshSpy = vi.fn();
    globalAxiosMock.onPost(new RegExp("/auth/refresh$")).reply(() => {
      refreshSpy();
      return [200, {}];
    });
    mock.onGet("/secure").reply(401);

    await expect(apiClient.get("/secure")).rejects.toMatchObject({
      response: { status: 401 },
    });
    expect(refreshSpy).not.toHaveBeenCalled();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(useAuthStore.getState().accessToken).toBeNull();
  });
});

describe("response interceptor — 401 with a refresh token", () => {
  it("refreshes, retries the original request with the new token, and resolves", async () => {
    useAuthStore.setState({
      accessToken: "expired-token",
      refreshToken: "valid-refresh-token",
      isAuthenticated: true,
    });

    let secureCallCount = 0;
    mock.onGet("/secure").reply((config) => {
      secureCallCount += 1;
      if (config.headers?.Authorization === "Bearer expired-token") {
        return [401];
      }
      expect(config.headers?.Authorization).toBe("Bearer fresh-access-token");
      return [200, { data: "protected" }];
    });
    globalAxiosMock.onPost(new RegExp("/auth/refresh$")).reply((config) => {
      expect(JSON.parse(config.data)).toEqual({ refresh_token: "valid-refresh-token" });
      return [200, { access_token: "fresh-access-token", refresh_token: "fresh-refresh-token" }];
    });

    const response = await apiClient.get("/secure");

    expect(response.data).toEqual({ data: "protected" });
    expect(secureCallCount).toBe(2); // original (401) + retry (200)
    expect(useAuthStore.getState().accessToken).toBe("fresh-access-token");
    expect(useAuthStore.getState().refreshToken).toBe("fresh-refresh-token");
  });

  it("logs out and rejects if the refresh call itself fails", async () => {
    useAuthStore.setState({
      accessToken: "expired-token",
      refreshToken: "revoked-refresh-token",
      isAuthenticated: true,
    });
    mock.onGet("/secure").reply(401);
    globalAxiosMock.onPost(new RegExp("/auth/refresh$")).reply(401, { detail: "refresh token revoked" });

    await expect(apiClient.get("/secure")).rejects.toBeTruthy();

    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(useAuthStore.getState().accessToken).toBeNull();
    expect(useAuthStore.getState().refreshToken).toBeNull();
  });

  it("does not attempt a second refresh for a request that already retried once", async () => {
    // Simulates the case where even the retried request still comes back
    // 401 (e.g. the "fresh" token is itself rejected) — must fail cleanly
    // rather than looping.
    useAuthStore.setState({
      accessToken: "expired-token",
      refreshToken: "valid-refresh-token",
      isAuthenticated: true,
    });

    let refreshCallCount = 0;
    mock.onGet("/secure").reply(401);
    globalAxiosMock.onPost(new RegExp("/auth/refresh$")).reply(() => {
      refreshCallCount += 1;
      return [200, { access_token: "still-rejected-token", refresh_token: "r2" }];
    });

    await expect(apiClient.get("/secure")).rejects.toMatchObject({
      response: { status: 401 },
    });
    expect(refreshCallCount).toBe(1);
  });

  it("queues concurrent 401s behind a single in-flight refresh and retries all of them", async () => {
    useAuthStore.setState({
      accessToken: "expired-token",
      refreshToken: "valid-refresh-token",
      isAuthenticated: true,
    });

    let refreshCallCount = 0;
    globalAxiosMock.onPost(new RegExp("/auth/refresh$")).reply(() => {
      refreshCallCount += 1;
      return [200, { access_token: "fresh-token", refresh_token: "fresh-refresh" }];
    });
    mock.onGet("/a").reply((config) =>
      config.headers?.Authorization === "Bearer fresh-token" ? [200, { name: "a" }] : [401]
    );
    mock.onGet("/b").reply((config) =>
      config.headers?.Authorization === "Bearer fresh-token" ? [200, { name: "b" }] : [401]
    );
    mock.onGet("/c").reply((config) =>
      config.headers?.Authorization === "Bearer fresh-token" ? [200, { name: "c" }] : [401]
    );

    const [a, b, c] = await Promise.all([
      apiClient.get("/a"),
      apiClient.get("/b"),
      apiClient.get("/c"),
    ]);

    expect([a.data.name, b.data.name, c.data.name].sort()).toEqual(["a", "b", "c"]);
    // The whole point of the request queue: 3 concurrent 401s must trigger
    // exactly one refresh call, not three.
    expect(refreshCallCount).toBe(1);
  });
});

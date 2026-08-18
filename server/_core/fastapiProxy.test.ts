import { afterEach, describe, expect, it, vi } from "vitest";

import { resolveFastApiProxyBase } from "./fastapiProxy";

describe("development FastAPI proxy target", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("uses the local FastAPI API default when no override is configured", () => {
    vi.stubEnv("VITE_FORMA_API_PROXY", "");

    expect(resolveFastApiProxyBase().toString()).toBe("http://127.0.0.1:8000/");
  });

  it("accepts an explicit HTTP(S) proxy target and rejects unsupported protocols", () => {
    expect(resolveFastApiProxyBase("https://api.example.test").toString()).toBe(
      "https://api.example.test/",
    );
    expect(() => resolveFastApiProxyBase("file:///tmp/forma")).toThrow(
      "VITE_FORMA_API_PROXY must use http or https.",
    );
  });
});

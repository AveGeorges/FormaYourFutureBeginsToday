import type { Express, Request } from "express";

const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "content-length",
  "host",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

export function resolveFastApiProxyBase(rawTarget = process.env.VITE_FORMA_API_PROXY): URL {
  const target = new URL(rawTarget || "http://127.0.0.1:8000");
  if (target.protocol !== "http:" && target.protocol !== "https:") {
    throw new Error("VITE_FORMA_API_PROXY must use http or https.");
  }
  return target;
}

function requestHeaders(request: Request): Headers {
  const headers = new Headers();
  for (const [name, value] of Object.entries(request.headers)) {
    if (HOP_BY_HOP_HEADERS.has(name.toLowerCase()) || value === undefined) continue;
    headers.set(name, Array.isArray(value) ? value.join(", ") : value);
  }
  return headers;
}

/**
 * The managed development shell is Express + Vite while production serves the
 * React build behind Nginx. Proxying here keeps `/api/v1` same-origin during
 * local development and prevents the SPA fallback from returning HTML to API
 * callers. It is never used by the self-hosted production topology.
 */
export function registerFastApiDevelopmentProxy(app: Express): void {
  const baseUrl = resolveFastApiProxyBase();

  app.use("/api/v1", async (request, response, next) => {
    try {
      const target = new URL(request.originalUrl, baseUrl);
      const method = request.method.toUpperCase();
      const outbound = await fetch(target, {
        method,
        headers: requestHeaders(request),
        body: method === "GET" || method === "HEAD" ? undefined : JSON.stringify(request.body ?? {}),
      });

      response.status(outbound.status);
      outbound.headers.forEach((value, name) => {
        if (!HOP_BY_HOP_HEADERS.has(name.toLowerCase())) response.setHeader(name, value);
      });
      response.send(Buffer.from(await outbound.arrayBuffer()));
    } catch (error) {
      next(error);
    }
  });
}

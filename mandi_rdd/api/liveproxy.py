"""Live-data proxy ASGI wrapper for MandiIQ.

Architecture
------------
- Northflank (p01--mandiiq--zbvjrztgjqgw.code.run) hosts the FULL live
  DuckDB (1.3M+ price rows, refreshed hourly) and every ML engine, but its
  istio-envoy edge proxy strips Access-Control-* headers, so browsers cannot
  read it cross-origin.
- Vercel's FastAPI ships CORSMiddleware (allow_origins=["*"], verified) so it
  IS CORS-correct, but the function bundle excludes the big DB
  (vercel.json excludeFiles) and heavy ML deps, so alone it only serves a
  small stale snapshot.

This middleware wraps a FastAPI app. Browser requests hit Vercel (CORS-
correct), Vercel forwards them server-to-server to Northflank (no CORS
constraint server-side — CORS only matters to browsers), and streams the live
response back with proper CORS headers. If the upstream is unreachable it
falls back to the wrapped app (bundled snapshot) so nothing breaks.

It is applied ONLY when the app runs on Vercel (env flag ``SERVE_LIVE_PROXY``
=== "1", which Vercel's runtime sets). Northflank runs the same app without
that flag, so it never proxies to itself (no loop).
"""

import os
import sys
import json
import urllib.request
from pathlib import Path

# Live-data upstream: the hourly-refreshed full DuckDB host.
PROXY_TARGET = os.environ.get(
    "NORTHFLANK_URL", "https://p01--mandiiq--zbvjrztgjqgw.code.run"
).rstrip("/")

CORS_ALLOW_METHODS = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
CORS_ALLOW_HEADERS = (
    "Accept, Accept-Encoding, Authorization, Content-Type, Origin, "
    "X-Requested-With, X-CSRF-Token, x-api-key"
)


def _cors_headers(scope):
    """Echo the request Origin (or * if none) — mirrors CORSMiddleware."""
    origin = ""
    for k, v in scope.get("headers", []):
        if k.lower() == b"origin":
            origin = v.decode("latin-1", "replace")
            break
    acao = origin if origin else "*"
    return [
        (b"access-control-allow-origin", acao.encode("latin-1", "replace")),
        (b"access-control-allow-methods", CORS_ALLOW_METHODS.encode("ascii")),
        (b"access-control-allow-headers", CORS_ALLOW_HEADERS.encode("ascii")),
        (b"access-control-allow-credentials", b"true"),
        (b"vary", b"Origin"),
    ]


def _forward(method, url, headers, body):
    """Blocking urllib forward — fine in a serverless function (one request
    per instance at a time). Returns (status, headers, payload)."""
    req = urllib.request.Request(
        url,
        data=body if method not in ("GET", "HEAD") else None,
        method=method,
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=50) as resp:
        payload = resp.read()
        status = resp.status
        out_headers = []
        ct = resp.headers.get("Content-Type")
        if ct:
            out_headers.append((b"content-type", ct.encode("latin-1", "replace")))
        return status, out_headers, payload


def live_proxy_enabled():
    """Proxy only when running inside Vercel's runtime."""
    return os.environ.get("VERCEL", "") == "1" or os.environ.get(
        "SERVE_LIVE_PROXY", ""
    ) == "1"


class LiveProxy:
    """ASGI middleware: forward to the live-data host; fall back to local app."""

    __slots__ = ("app",)

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        method = scope.get("method", "GET")
        path = scope.get("path", "/")

        # Diagnostics: report whether the proxy is active + upstream reachable.
        if path == "/_proxy/status":
            payload = {"proxy": True, "target": PROXY_TARGET}
            try:
                req = urllib.request.Request(PROXY_TARGET + "/health", timeout=15)
                with urllib.request.urlopen(req) as r:
                    payload["upstream_reachable"] = True
                    payload["upstream_status"] = r.status
            except Exception as e:  # noqa: BLE001
                payload["upstream_reachable"] = False
                payload["upstream_error"] = str(e)
            body = json.dumps(payload).encode()
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ] + _cors_headers(scope),
            })
            await send({"type": "http.response.body", "body": body})
            return

        # Preflight — answer locally with CORS headers (no upstream hop).
        if method == "OPTIONS":
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-length", b"0")] + _cors_headers(scope),
            })
            await send({"type": "http.response.body", "body": b""})
            return

        qs = scope.get("query_string", b"").decode("latin-1", "replace")
        url = PROXY_TARGET + path + (("?" + qs) if qs else "")

        # Build forwarding headers (drop hop-by-hop / host / length).
        skip = {"host", "content-length", "connection", "accept-encoding"}
        fwd = {}
        for k, v in scope.get("headers", []):
            name = k.decode("latin-1", "replace").lower()
            if name in skip or name.startswith(":"):
                continue
            fwd[name] = v.decode("latin-1", "replace")
        fwd["accept-encoding"] = "identity"
        fwd["user-agent"] = "MandiIQ-Vercel-LiveProxy/1.0"

        # Read body once for methods that carry one.
        body = None
        if method in ("POST", "PUT", "PATCH"):
            chunks = []
            more = True
            while more:
                message = await receive()
                chunks.append(message.get("body", b""))
                more = message.get("more_body", False)
            body = b"".join(chunks)

        try:
            status, headers, payload = _forward(method, url, fwd, body)
            await send({
                "type": "http.response.start",
                "status": status,
                "headers": headers + _cors_headers(scope),
            })
            await send({"type": "http.response.body", "body": payload})
            return
        except Exception as e:  # noqa: BLE001 — upstream down / timeout → fallback
            print(f"[liveproxy] upstream {PROXY_TARGET} failed ({e}); using local app")
            if body is not None and scope["method"] in ("POST", "PUT", "PATCH"):
                sent = [False]

                async def replay():
                    if not sent[0]:
                        sent[0] = True
                        return {"type": "http.request", "body": body, "more_body": False}
                    return {"type": "http.disconnect"}

                receive = replay
            return await self.app(scope, receive, send)


def maybe_wrap(app):
    """Wrap ``app`` with LiveProxy only when running inside Vercel."""
    if live_proxy_enabled():
        return LiveProxy(app)
    return app
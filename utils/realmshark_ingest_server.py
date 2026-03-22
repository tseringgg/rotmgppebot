from __future__ import annotations

import os
from typing import Any, Dict

from aiohttp import web

from utils.realmshark_ingest import IngestValidationError, ingest_loot_event


_DEBUG = os.getenv("REALMSHARK_DEBUG", "false").strip().lower() in {"1", "true", "yes", "on"}


def _debug_log(message: str) -> None:
    if _DEBUG:
        print(f"[REALMSHARK_DEBUG] {message}")


def _as_bool(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _build_app() -> web.Application:
    app = web.Application()

    async def health(_request: web.Request) -> web.Response:
        return web.json_response({"ok": True, "service": "realmshark-ingest"})

    async def ingest(request: web.Request) -> web.Response:
        try:
            payload: Dict[str, Any] = await request.json()
        except Exception:
            _debug_log("Rejected ingest request due to invalid JSON body")
            return web.json_response(
                {"ok": False, "error": "invalid_json", "message": "Body must be valid JSON."},
                status=400,
            )

        try:
            _debug_log("Processing ingest request")
            result = await ingest_loot_event(payload)
            _debug_log(f"Ingest success: {result.get('reason', 'logged')} item={result.get('item', '')}")
            return web.json_response({"ok": True, "result": result})
        except IngestValidationError as e:
            _debug_log(f"Ingest validation error: {e.error_code} message={e.message}")
            return web.json_response(
                {"ok": False, "error": e.error_code, "message": e.message},
                status=e.status_code,
            )
        except Exception as e:
            _debug_log(f"Ingest internal error: {e}")
            return web.json_response(
                {"ok": False, "error": "internal_error", "message": str(e)},
                status=500,
            )

    app.router.add_get("/realmshark/health", health)
    app.router.add_post("/realmshark/ingest", ingest)
    return app


async def start_realmshark_ingest_server() -> web.AppRunner | None:
    if not _as_bool(os.getenv("REALMSHARK_INGEST_ENABLED"), default=True):
        print("RealmShark ingest server disabled (REALMSHARK_INGEST_ENABLED=false).")
        return None

    host = os.getenv("REALMSHARK_INGEST_HOST", "0.0.0.0")
    # Railway injects PORT dynamically for public services.
    port_raw = os.getenv("PORT") or os.getenv("REALMSHARK_INGEST_PORT", "8787")
    try:
        port = int(port_raw)
    except ValueError:
        port = 8787

    app = _build_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=host, port=port)
    await site.start()

    print(f"RealmShark ingest server listening on http://{host}:{port}/realmshark/ingest")
    return runner

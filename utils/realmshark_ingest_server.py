from __future__ import annotations

import os
from typing import Any, Awaitable, Callable, Dict

from aiohttp import web

from utils.realmshark_ingest import IngestValidationError, ingest_loot_event


_DEBUG = os.getenv("REALMSHARK_DEBUG", "false").strip().lower() in {"1", "true", "yes", "on"}


def _debug_log(message: str) -> None:
    if _DEBUG:
        print(f"[REALMSHARK_DEBUG] {message}")


def _info_log(message: str) -> None:
    print(f"[REALMSHARK] {message}")


def _token_preview(token: str) -> str:
    if len(token) <= 10:
        return token
    return f"{token[:6]}...{token[-4:]}"


def _summarize_payload(payload: Dict[str, Any]) -> str:
    guild_id = payload.get("guild_id")
    event_type = payload.get("event_type", "loot")
    item_name = payload.get("item_name", "")
    token = _token_preview(str(payload.get("link_token", "")))
    source = payload.get("source", "")
    return (
        f"guild_id={guild_id} event_type={event_type} item_name={item_name} "
        f"token={token} source={source}"
    )


def _as_bool(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


Notifier = Callable[
    [
        int,
        str,
        int | None,
        int | None,
        str | None,
        bool,
        int | None,
        bool,
    ],
    Awaitable[None],
]


def _build_app(notifier: Notifier | None = None) -> web.Application:
    app = web.Application()

    async def health(_request: web.Request) -> web.Response:
        _debug_log("Health check received")
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

        _debug_log(
            "Ingest request received "
            f"from={request.remote} method={request.method} path={request.path} "
            + _summarize_payload(payload)
        )

        try:
            _debug_log("Processing ingest request")
            result = await ingest_loot_event(payload, notifier=notifier)
            _info_log(
                "Ingest success "
                f"reason={result.get('reason', 'logged')} mode={result.get('mode', '')} "
                f"guild_id={result.get('guild_id', payload.get('guild_id'))} "
                f"user_id={result.get('user_id', '')} item={result.get('item', '')}"
            )
            _debug_log(f"Ingest success: {result.get('reason', 'logged')} item={result.get('item', '')}")
            return web.json_response({"ok": True, "result": result})
        except IngestValidationError as e:
            _info_log(
                "Ingest validation failure "
                f"status={e.status_code} error={e.error_code} message={e.message}"
            )
            _debug_log(f"Ingest validation error: {e.error_code} message={e.message}")
            return web.json_response(
                {"ok": False, "error": e.error_code, "message": e.message},
                status=e.status_code,
            )
        except Exception as e:
            _info_log(f"Ingest internal error: {e}")
            _debug_log(f"Ingest internal error: {e}")
            return web.json_response(
                {"ok": False, "error": "internal_error", "message": str(e)},
                status=500,
            )

    app.router.add_get("/realmshark/health", health)
    app.router.add_post("/realmshark/ingest", ingest)
    return app


async def start_realmshark_ingest_server(notifier: Notifier | None = None) -> web.AppRunner | None:
    if not _as_bool(os.getenv("REALMSHARK_INGEST_ENABLED"), default=True):
        print("RealmShark ingest server disabled (REALMSHARK_INGEST_ENABLED=false).")
        return None

    host = os.getenv("REALMSHARK_INGEST_HOST", "0.0.0.0")
    # Railway injects PORT dynamically for public services.
    port_raw = os.getenv("PORT") or os.getenv("REALMSHARK_INGEST_PORT", "8080")
    try:
        port = int(port_raw)
    except ValueError:
        port = 8080

    app = _build_app(notifier=notifier)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=host, port=port)
    await site.start()

    _info_log(f"RealmShark ingest server listening on http://{host}:{port}/realmshark/ingest")
    _debug_log(f"Notifier attached={notifier is not None}")
    return runner

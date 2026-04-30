"""Per-guild slash-command cost and cache-impact tracking."""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from typing import Any

import discord

from utils.contest_join_embed import get_cache_size as get_contest_cache_size
from utils.player_manager import get_lock_count as get_player_manager_lock_count
from utils.player_records import DATA_DIR, get_lock, get_lock_count as get_player_records_lock_count
from utils.settings.channel_settings import get_cache_sizes as get_channel_setting_cache_sizes
from utils.sniffer_helpers.realmshark_notifier import get_channel_cache_size as get_realmshark_channel_cache_size
from utils.team_manager import get_lock_count as get_team_manager_lock_count


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    raw = os.getenv(name)
    if raw is None:
        return max(minimum, default)

    try:
        parsed = float(raw)
    except ValueError:
        return max(minimum, default)

    return max(minimum, parsed)


_COST_LOG_ENABLED = _env_flag("PPE_COST_LOG_ENABLED", default=True)
_COST_RATE_PER_GB_MINUTE = _env_float("PPE_COST_RATE_PER_GB_MINUTE", default=0.000231, minimum=0.0)
_COST_LOG_DIR = os.path.join(DATA_DIR, "bot_cost_logs")
_ACTIVE_COMMAND_TTL_SECONDS = _env_float("PPE_COST_ACTIVE_TTL_SECONDS", default=3600.0, minimum=60.0)

_ACTIVE_COMMANDS: dict[int, dict[str, Any]] = {}
_ACTIVE_LOCK = asyncio.Lock()


async def is_cost_logging_enabled_for_guild(guild_id: int) -> bool:
    """Check if cost logging is enabled globally AND for this specific guild."""
    if not _COST_LOG_ENABLED:
        return False
    
    # Guild-specific check: only import when needed to avoid circular deps
    try:
        from utils.guild_config import load_guild_config_by_id
        config = await load_guild_config_by_id(guild_id)
        return bool(config.get("cost_logging_enabled", True))
    except Exception:
        # If guild config can't be loaded, fall back to global setting
        return _COST_LOG_ENABLED


def get_cost_rate_per_gb_minute() -> float:
    return _COST_RATE_PER_GB_MINUTE


def get_guild_cost_log_path(guild_id: int) -> str:
    return os.path.join(_COST_LOG_DIR, f"{int(guild_id)}_command_cost.jsonl")


def _touch_file(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8"):
        pass


def _normalize_command_name(command_name: str | None) -> str:
    normalized = str(command_name or "unknown").strip() or "unknown"
    if not normalized.startswith("/"):
        normalized = "/" + normalized
    return normalized


async def ensure_guild_cost_log_file(guild_id: int) -> str:
    path = get_guild_cost_log_path(guild_id)
    async with get_lock(int(guild_id)):
        await asyncio.to_thread(_touch_file, path)
    return path


async def clear_guild_tracking_state(guild_id: int) -> None:
    guild_key = int(guild_id)
    async with _ACTIVE_LOCK:
        stale_ids = [
            interaction_id
            for interaction_id, payload in _ACTIVE_COMMANDS.items()
            if int(payload.get("guild_id", -1)) == guild_key
        ]
        for interaction_id in stale_ids:
            _ACTIVE_COMMANDS.pop(interaction_id, None)


def _read_process_rss_mb() -> float:
    """Best-effort Linux RSS read without adding psutil dependency."""
    try:
        with open("/proc/self/status", "r", encoding="utf-8") as handle:
            for line in handle:
                if not line.startswith("VmRSS:"):
                    continue
                parts = line.split()
                if len(parts) < 2:
                    break
                return int(parts[1]) / 1024.0
    except Exception:
        pass

    return 0.0


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_command_name(interaction: discord.Interaction) -> str:
    command = getattr(interaction, "command", None)
    if command is not None:
        qualified_name = getattr(command, "qualified_name", None)
        if isinstance(qualified_name, str) and qualified_name.strip():
            return "/" + qualified_name.strip()

        name = getattr(command, "name", None)
        if isinstance(name, str) and name.strip():
            return "/" + name.strip()

    data = interaction.data if isinstance(interaction.data, dict) else {}
    base_name = str(data.get("name", "unknown")).strip() or "unknown"
    segments = [base_name]

    options = data.get("options")
    while isinstance(options, list) and options:
        first = options[0] if isinstance(options[0], dict) else None
        if not first:
            break

        option_type = int(first.get("type", 0) or 0)
        # 1 = subcommand, 2 = subcommand group
        if option_type not in {1, 2}:
            break

        option_name = str(first.get("name", "")).strip()
        if option_name:
            segments.append(option_name)

        options = first.get("options")

    return "/" + " ".join(segments)


def _capture_runtime_snapshot() -> dict[str, Any]:
    channel_setting_cache_sizes = get_channel_setting_cache_sizes()
    cache_entries = {
        "channel_enabled": int(channel_setting_cache_sizes.get("channel_enabled", 0)),
        "mode_enabled": int(channel_setting_cache_sizes.get("mode_enabled", 0)),
        "contest_settings": int(get_contest_cache_size()),
        "realmshark_channel": int(get_realmshark_channel_cache_size()),
    }
    lock_entries = {
        "player_records": int(get_player_records_lock_count()),
        "player_manager": int(get_player_manager_lock_count()),
        "team_manager": int(get_team_manager_lock_count()),
    }

    return {
        "rss_mb": float(_read_process_rss_mb()),
        "cache_entries": cache_entries,
        "lock_entries": lock_entries,
    }


def capture_runtime_snapshot() -> dict[str, Any]:
    return _capture_runtime_snapshot()


def _cache_total(snapshot: dict[str, Any]) -> int:
    cache_entries = snapshot.get("cache_entries", {}) if isinstance(snapshot, dict) else {}
    if not isinstance(cache_entries, dict):
        return 0
    return sum(int(value) for value in cache_entries.values())


def _lock_total(snapshot: dict[str, Any]) -> int:
    lock_entries = snapshot.get("lock_entries", {}) if isinstance(snapshot, dict) else {}
    if not isinstance(lock_entries, dict):
        return 0
    return sum(int(value) for value in lock_entries.values())


def _estimate_cost_usd(*, avg_rss_mb: float, duration_seconds: float) -> tuple[float, float]:
    gb_minutes = (max(0.0, avg_rss_mb) / 1024.0) * (max(0.0, duration_seconds) / 60.0)
    cost_usd = gb_minutes * _COST_RATE_PER_GB_MINUTE
    return gb_minutes, cost_usd


def _purge_stale_active(now_monotonic: float) -> None:
    stale_ids = [
        interaction_id
        for interaction_id, payload in _ACTIVE_COMMANDS.items()
        if (now_monotonic - float(payload.get("started_monotonic", now_monotonic))) > _ACTIVE_COMMAND_TTL_SECONDS
    ]
    for interaction_id in stale_ids:
        _ACTIVE_COMMANDS.pop(interaction_id, None)


def _append_jsonl(path: str, payload: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True, separators=(",", ":")) + "\n")


def _build_cost_payload(
    *,
    interaction_id: int,
    guild_id: int,
    user_id: int,
    command_name: str,
    status: str,
    error_message: str | None,
    started_monotonic: float,
    started_unix: float,
    snapshot_before: dict[str, Any],
    source: str,
) -> dict[str, Any]:
    ended_monotonic = time.monotonic()
    ended_unix = time.time()
    snapshot_after = _capture_runtime_snapshot()

    duration_seconds = max(0.0, ended_monotonic - started_monotonic)
    rss_before_mb = float(snapshot_before.get("rss_mb", 0.0) or 0.0)
    rss_after_mb = float(snapshot_after.get("rss_mb", 0.0) or 0.0)
    avg_rss_mb = (rss_before_mb + rss_after_mb) / 2.0
    gb_minutes, cost_usd = _estimate_cost_usd(avg_rss_mb=avg_rss_mb, duration_seconds=duration_seconds)

    cache_before = snapshot_before.get("cache_entries", {}) if isinstance(snapshot_before, dict) else {}
    cache_after = snapshot_after.get("cache_entries", {}) if isinstance(snapshot_after, dict) else {}
    lock_before = snapshot_before.get("lock_entries", {}) if isinstance(snapshot_before, dict) else {}
    lock_after = snapshot_after.get("lock_entries", {}) if isinstance(snapshot_after, dict) else {}

    cache_keys = sorted(set(cache_before.keys()) | set(cache_after.keys()))
    lock_keys = sorted(set(lock_before.keys()) | set(lock_after.keys()))

    cache_delta = {
        key: int(cache_after.get(key, 0)) - int(cache_before.get(key, 0))
        for key in cache_keys
    }
    lock_delta = {
        key: int(lock_after.get(key, 0)) - int(lock_before.get(key, 0))
        for key in lock_keys
    }

    return {
        "ts_utc": _utc_iso_now(),
        "interaction_id": interaction_id,
        "guild_id": guild_id,
        "user_id": user_id,
        "command": _normalize_command_name(command_name),
        "status": str(status or "unknown").strip().lower() or "unknown",
        "error": str(error_message).strip() if error_message else None,
        "tracking_source": str(source or "unknown").strip() or "unknown",
        "started_at_unix": float(started_unix),
        "ended_at_unix": ended_unix,
        "duration_seconds": duration_seconds,
        "rss_before_mb": rss_before_mb,
        "rss_after_mb": rss_after_mb,
        "rss_delta_mb": rss_after_mb - rss_before_mb,
        "avg_rss_mb": avg_rss_mb,
        "estimated_gb_minutes": gb_minutes,
        "estimated_cost_usd": cost_usd,
        "cache_before": cache_before,
        "cache_after": cache_after,
        "cache_delta": cache_delta,
        "cache_total_before": _cache_total(snapshot_before),
        "cache_total_after": _cache_total(snapshot_after),
        "cache_delta_total": _cache_total(snapshot_after) - _cache_total(snapshot_before),
        "lock_before": lock_before,
        "lock_after": lock_after,
        "lock_delta": lock_delta,
        "lock_total_before": _lock_total(snapshot_before),
        "lock_total_after": _lock_total(snapshot_after),
        "lock_delta_total": _lock_total(snapshot_after) - _lock_total(snapshot_before),
    }


async def _write_cost_entry(guild_id: int, payload: dict[str, Any]) -> None:
    path = get_guild_cost_log_path(guild_id)

    async with get_lock(int(guild_id)):
        await asyncio.to_thread(_append_jsonl, path, payload)


async def log_cost_event(
    interaction: discord.Interaction,
    *,
    command_name: str,
    status: str = "ok",
    error_message: str | None = None,
    started_monotonic: float | None = None,
    started_unix: float | None = None,
    snapshot_before: dict[str, Any] | None = None,
    source: str = "ui_action",
) -> bool:
    if not await is_cost_logging_enabled_for_guild(int(interaction.guild_id or 0)):
        return False

    if interaction.guild_id is None:
        return False

    guild_id = int(interaction.guild_id)
    user_id = int(interaction.user.id)
    interaction_id = int(interaction.id)
    started_monotonic = float(started_monotonic if started_monotonic is not None else time.monotonic())
    started_unix = float(started_unix if started_unix is not None else time.time())
    snapshot_before = dict(snapshot_before or _capture_runtime_snapshot())

    await ensure_guild_cost_log_file(guild_id)
    payload = _build_cost_payload(
        interaction_id=interaction_id,
        guild_id=guild_id,
        user_id=user_id,
        command_name=command_name,
        status=status,
        error_message=error_message,
        started_monotonic=started_monotonic,
        started_unix=started_unix,
        snapshot_before=snapshot_before,
        source=source,
    )
    await _write_cost_entry(guild_id, payload)
    return True


async def start_command_tracking(interaction: discord.Interaction) -> bool:
    if not await is_cost_logging_enabled_for_guild(int(interaction.guild_id or 0)):
        return False

    if interaction.guild_id is None:
        return False

    if interaction.type is not discord.InteractionType.application_command:
        return False

    interaction_id = int(interaction.id)
    now_monotonic = time.monotonic()
    now_unix = time.time()
    payload = {
        "guild_id": int(interaction.guild_id),
        "user_id": int(interaction.user.id),
        "command": _extract_command_name(interaction),
        "started_monotonic": now_monotonic,
        "started_unix": now_unix,
        "snapshot_before": _capture_runtime_snapshot(),
    }

    async with _ACTIVE_LOCK:
        _purge_stale_active(now_monotonic)
        _ACTIVE_COMMANDS[interaction_id] = payload

    await ensure_guild_cost_log_file(int(interaction.guild_id))

    return True


async def finish_command_tracking(
    interaction: discord.Interaction,
    *,
    status: str,
    command_name: str | None = None,
    error_message: str | None = None,
) -> bool:
    if not await is_cost_logging_enabled_for_guild(int(interaction.guild_id or 0)):
        return False

    if interaction.guild_id is None:
        return False

    interaction_id = int(interaction.id)
    ended_monotonic = time.monotonic()
    ended_unix = time.time()

    async with _ACTIVE_LOCK:
        context = _ACTIVE_COMMANDS.pop(interaction_id, None)
        _purge_stale_active(ended_monotonic)

    if context is None:
        return False

    started_monotonic = float(context.get("started_monotonic", ended_monotonic))
    snapshot_before = context.get("snapshot_before", {}) if isinstance(context, dict) else {}
    resolved_command_name = command_name or str(context.get("command", "")).strip() or _extract_command_name(interaction)
    started_unix = float(context.get("started_unix", ended_unix))

    payload = _build_cost_payload(
        interaction_id=interaction_id,
        guild_id=int(context.get("guild_id", int(interaction.guild_id))),
        user_id=int(context.get("user_id", int(interaction.user.id))),
        command_name=resolved_command_name,
        status=status,
        error_message=error_message,
        started_monotonic=started_monotonic,
        started_unix=started_unix,
        snapshot_before=snapshot_before,
        source="app_command",
    )

    await _write_cost_entry(int(context.get("guild_id", int(interaction.guild_id))), payload)
    return True


async def clear_guild_cost_log(guild_id: int) -> bool:
    path = get_guild_cost_log_path(guild_id)

    def _delete_if_exists(target_path: str) -> bool:
        if not os.path.exists(target_path):
            return False
        os.remove(target_path)
        return True

    async with get_lock(int(guild_id)):
        deleted = await asyncio.to_thread(_delete_if_exists, path)

    return bool(deleted)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _summarize_log_sync(path: str, *, cutoff_unix: float, top_n: int) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "entry_count": 0,
        "command_count": 0,
        "error_count": 0,
        "total_duration_seconds": 0.0,
        "total_estimated_gb_minutes": 0.0,
        "total_estimated_cost_usd": 0.0,
        "total_rss_growth_mb": 0.0,
        "total_rss_shrink_mb": 0.0,
        "total_cache_growth": 0,
        "total_cache_shrink": 0,
        "max_rss_after_mb": 0.0,
        "top_by_cost": [],
        "top_by_rss_growth": [],
        "top_by_cache_growth": [],
    }

    if not os.path.exists(path):
        return summary

    command_stats: dict[str, dict[str, Any]] = {}

    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            ended_at_unix = _safe_float(entry.get("ended_at_unix"), 0.0)
            if cutoff_unix > 0 and ended_at_unix > 0 and ended_at_unix < cutoff_unix:
                continue

            command_name = str(entry.get("command", "unknown")).strip() or "unknown"
            status = str(entry.get("status", "unknown")).strip().lower()
            tracking_source = str(entry.get("tracking_source", "unknown")).strip() or "unknown"
            duration_seconds = _safe_float(entry.get("duration_seconds"), 0.0)
            estimated_gb_minutes = _safe_float(entry.get("estimated_gb_minutes"), 0.0)
            estimated_cost_usd = _safe_float(entry.get("estimated_cost_usd"), 0.0)
            cache_delta_total = _safe_int(entry.get("cache_delta_total"), 0)
            rss_after_mb = _safe_float(entry.get("rss_after_mb"), 0.0)
            rss_delta_mb = _safe_float(entry.get("rss_delta_mb"), 0.0)

            stats = command_stats.setdefault(
                command_name,
                {
                    "command": command_name,
                    "call_count": 0,
                    "error_count": 0,
                    "total_duration_seconds": 0.0,
                    "total_estimated_gb_minutes": 0.0,
                    "total_estimated_cost_usd": 0.0,
                    "total_rss_growth_mb": 0.0,
                    "total_rss_shrink_mb": 0.0,
                    "total_cache_growth": 0,
                    "total_cache_shrink": 0,
                    "max_rss_after_mb": 0.0,
                    "tracking_source": tracking_source,
                },
            )

            existing_source = str(stats.get("tracking_source", "unknown")).strip() or "unknown"
            if existing_source != tracking_source:
                stats["tracking_source"] = "mixed"

            stats["call_count"] += 1
            if status != "ok":
                stats["error_count"] += 1

            stats["total_duration_seconds"] += duration_seconds
            stats["total_estimated_gb_minutes"] += estimated_gb_minutes
            stats["total_estimated_cost_usd"] += estimated_cost_usd
            stats["max_rss_after_mb"] = max(float(stats["max_rss_after_mb"]), rss_after_mb)

            if rss_delta_mb > 0:
                stats["total_rss_growth_mb"] += rss_delta_mb
                summary["total_rss_growth_mb"] += rss_delta_mb
            elif rss_delta_mb < 0:
                shrink = abs(rss_delta_mb)
                stats["total_rss_shrink_mb"] += shrink
                summary["total_rss_shrink_mb"] += shrink

            if cache_delta_total > 0:
                stats["total_cache_growth"] += cache_delta_total
                summary["total_cache_growth"] += cache_delta_total
            elif cache_delta_total < 0:
                shrink = abs(cache_delta_total)
                stats["total_cache_shrink"] += shrink
                summary["total_cache_shrink"] += shrink

            summary["entry_count"] += 1
            if status != "ok":
                summary["error_count"] += 1
            summary["total_duration_seconds"] += duration_seconds
            summary["total_estimated_gb_minutes"] += estimated_gb_minutes
            summary["total_estimated_cost_usd"] += estimated_cost_usd
            summary["max_rss_after_mb"] = max(float(summary["max_rss_after_mb"]), rss_after_mb)

    summary["command_count"] = len(command_stats)

    total_cost = float(summary["total_estimated_cost_usd"])
    total_growth = int(summary["total_cache_growth"])

    rows = list(command_stats.values())
    rows.sort(key=lambda row: (-float(row["total_estimated_cost_usd"]), -int(row["call_count"]), str(row["command"])))
    top_cost = rows[:top_n]

    top_cost_rows: list[dict[str, Any]] = []
    for row in top_cost:
        cost_value = float(row["total_estimated_cost_usd"])
        top_cost_rows.append(
            {
                **row,
                "cost_share_percent": (cost_value / total_cost * 100.0) if total_cost > 0 else 0.0,
            }
        )

    rows.sort(key=lambda row: (-float(row["total_rss_growth_mb"]), -float(row["total_estimated_cost_usd"]), str(row["command"])))
    top_rss_growth = [row for row in rows if float(row["total_rss_growth_mb"]) > 0][:top_n]

    total_rss_growth = float(summary["total_rss_growth_mb"])
    top_rss_rows: list[dict[str, Any]] = []
    for row in top_rss_growth:
        growth_value = float(row["total_rss_growth_mb"])
        top_rss_rows.append(
            {
                **row,
                "rss_growth_share_percent": (growth_value / total_rss_growth * 100.0) if total_rss_growth > 0 else 0.0,
            }
        )

    rows.sort(key=lambda row: (-int(row["total_cache_growth"]), -float(row["total_estimated_cost_usd"]), str(row["command"])))
    top_cache = [row for row in rows if int(row["total_cache_growth"]) > 0][:top_n]

    top_cache_rows: list[dict[str, Any]] = []
    for row in top_cache:
        growth_value = int(row["total_cache_growth"])
        top_cache_rows.append(
            {
                **row,
                "cache_growth_share_percent": (growth_value / total_growth * 100.0) if total_growth > 0 else 0.0,
            }
        )

    summary["top_by_cost"] = top_cost_rows
    summary["top_by_rss_growth"] = top_rss_rows
    summary["top_by_cache_growth"] = top_cache_rows
    return summary


async def log_background_cost_event(
    guild_id: int,
    *,
    operation_name: str,
    status: str = "ok",
    error_message: str | None = None,
    started_monotonic: float | None = None,
    started_unix: float | None = None,
    snapshot_before: dict[str, Any] | None = None,
    source: str = "background",
) -> bool:
    """Log cost event for background operations (RealmShark, picture suggestions, leaderboards, etc.)."""
    if not await is_cost_logging_enabled_for_guild(guild_id):
        return False

    if guild_id is None or guild_id <= 0:
        return False

    guild_id = int(guild_id)
    interaction_id = int(time.time() * 1000000) % (2**63)  # Use nanosecond timestamp as pseudo-ID
    started_monotonic = float(started_monotonic if started_monotonic is not None else time.monotonic())
    started_unix = float(started_unix if started_unix is not None else time.time())
    snapshot_before = dict(snapshot_before or _capture_runtime_snapshot())

    await ensure_guild_cost_log_file(guild_id)
    payload = _build_cost_payload(
        interaction_id=interaction_id,
        guild_id=guild_id,
        user_id=0,  # Background operations have no user
        command_name=operation_name,
        status=status,
        error_message=error_message,
        started_monotonic=started_monotonic,
        started_unix=started_unix,
        snapshot_before=snapshot_before,
        source=source,
    )
    await _write_cost_entry(guild_id, payload)
    return True


def _calculate_30day_projection(summary: dict[str, Any]) -> dict[str, Any]:
    """Calculate 30-day cost projection based on current window's usage rate."""
    window_hours = int(summary.get("window_hours", 24) or 24)
    if window_hours <= 0:
        window_hours = 24

    # Calculate daily rate from the window
    daily_hours = 24.0
    window_multiplier = daily_hours / window_hours
    
    total_cost_current_window = float(summary.get("total_estimated_cost_usd", 0.0) or 0.0)
    total_gb_minutes_current_window = float(summary.get("total_estimated_gb_minutes", 0.0) or 0.0)
    total_duration_current_window = float(summary.get("total_duration_seconds", 0.0) or 0.0)
    entry_count_current_window = int(summary.get("entry_count", 0) or 0)

    # 30 days = 30 * 24 = 720 hours
    days_multiplier = 30.0 / window_hours
    
    return {
        "daily_cost_usd": total_cost_current_window * window_multiplier,
        "total_30day_cost_usd": total_cost_current_window * days_multiplier,
        "daily_gb_minutes": total_gb_minutes_current_window * window_multiplier,
        "total_30day_gb_minutes": total_gb_minutes_current_window * days_multiplier,
        "daily_duration_seconds": total_duration_current_window * window_multiplier,
        "total_30day_duration_seconds": total_duration_current_window * days_multiplier,
        "estimated_daily_commands": int(entry_count_current_window * window_multiplier),
        "estimated_30day_commands": int(entry_count_current_window * days_multiplier),
    }


def _build_source_summary(command_stats: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Build summary of costs grouped by tracking source."""
    source_summary: dict[str, dict[str, Any]] = {}
    
    for command_stats_row in command_stats.values():
        source = str(command_stats_row.get("tracking_source", "unknown")).strip() or "unknown"
        
        if source not in source_summary:
            source_summary[source] = {
                "source": source,
                "call_count": 0,
                "command_count": 0,
                "error_count": 0,
                "total_cost_usd": 0.0,
                "total_gb_minutes": 0.0,
                "total_duration_seconds": 0.0,
                "total_rss_growth_mb": 0.0,
                "total_cache_growth": 0,
            }
        
        source_stats = source_summary[source]
        source_stats["call_count"] += int(command_stats_row.get("call_count", 0) or 0)
        source_stats["command_count"] += 1
        source_stats["error_count"] += int(command_stats_row.get("error_count", 0) or 0)
        source_stats["total_cost_usd"] += float(command_stats_row.get("total_estimated_cost_usd", 0.0) or 0.0)
        source_stats["total_gb_minutes"] += float(command_stats_row.get("total_estimated_gb_minutes", 0.0) or 0.0)
        source_stats["total_duration_seconds"] += float(command_stats_row.get("total_duration_seconds", 0.0) or 0.0)
        source_stats["total_rss_growth_mb"] += float(command_stats_row.get("total_rss_growth_mb", 0.0) or 0.0)
        source_stats["total_cache_growth"] += int(command_stats_row.get("total_cache_growth", 0) or 0)
    
    return source_summary


async def summarize_guild_cost_log(
    guild_id: int,
    *,
    window_hours: int = 24,
    top_n: int = 10,
) -> dict[str, Any]:
    safe_hours = max(1, int(window_hours))
    safe_top_n = max(1, int(top_n))
    cutoff_unix = time.time() - (safe_hours * 3600)
    path = get_guild_cost_log_path(guild_id)

    await ensure_guild_cost_log_file(guild_id)

    async with get_lock(int(guild_id)):
        summary = await asyncio.to_thread(_summarize_log_sync, path, cutoff_unix=cutoff_unix, top_n=safe_top_n)

    summary["guild_id"] = int(guild_id)
    summary["window_hours"] = safe_hours
    summary["top_n"] = safe_top_n
    summary["log_path"] = path
    summary["cost_rate_per_gb_minute"] = _COST_RATE_PER_GB_MINUTE
    
    # Add 30-day projection
    summary["projection_30day"] = _calculate_30day_projection(summary)
    
    return summary

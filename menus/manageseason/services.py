"""Business logic for /manageseason reset and point-settings operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import discord

from utils.guild_config import (
    get_contest_settings,
    get_points_settings,
    get_realmshark_settings,
    load_guild_config,
    set_contest_settings,
    set_points_settings,
    set_realmshark_settings,
    update_global_points_modifiers,
)
from utils.player_records import load_player_records, load_teams, save_player_records, save_teams
from utils.points_service import recompute_ppe_points
from utils.realmshark_pending_store import clear_all_pending_for_guild
from utils.contest_leaderboards import normalize_contest_leaderboard_id


@dataclass(slots=True)
class SeasonResetSummary:
    """Structured result payload for a completed season reset."""

    ppes_cleared: int
    items_cleared: int
    quest_entries_cleared: int
    teams_deleted: int
    team_roles_deleted: int
    default_reset_limit: int
    realmshark_links_before: int
    pending_files_cleared: int
    clear_realmshark_links: bool
    converted_bindings: int = 0
    tokens_updated: int = 0


@dataclass(slots=True)
class PointsRefreshSummary:
    """Structured result payload for bulk PPE point recalculation."""

    ppes_processed: int
    ppes_updated: int


async def load_points_settings_for_menu(interaction: discord.Interaction) -> dict[str, Any]:
    """Load point settings for point-settings embeds/views."""
    settings = await get_points_settings(interaction)
    return dict(settings)


async def load_contest_settings_for_menu(interaction: discord.Interaction) -> dict[str, Any]:
    """Load contest settings for manage-contests embeds/views."""
    settings = await get_contest_settings(interaction)
    return dict(settings)


async def update_default_contest_leaderboard(
    interaction: discord.Interaction,
    *,
    default_leaderboard: str | None,
) -> dict[str, Any]:
    """Persist the default contest leaderboard identifier."""
    settings = await get_contest_settings(interaction)
    normalized_default = normalize_contest_leaderboard_id(default_leaderboard)
    settings["default_contest_leaderboard"] = normalized_default
    saved = await set_contest_settings(interaction, settings)
    return dict(saved)


async def update_team_contest_quest_points_setting(
    interaction: discord.Interaction,
    *,
    enabled: bool,
) -> dict[str, Any]:
    """Toggle whether team contests should include quest points."""
    settings = await get_contest_settings(interaction)
    settings["team_contest_include_quest_points"] = bool(enabled)
    saved = await set_contest_settings(interaction, settings)
    return dict(saved)


async def update_global_point_modifiers(
    interaction: discord.Interaction,
    *,
    loot_percent: float | None = None,
    bonus_percent: float | None = None,
    penalty_percent: float | None = None,
    total_percent: float | None = None,
) -> tuple[dict[str, Any], PointsRefreshSummary]:
    """Update global percent modifiers and refresh all PPE point totals."""
    settings = await update_global_points_modifiers(
        interaction,
        loot_percent=loot_percent,
        bonus_percent=bonus_percent,
        penalty_percent=penalty_percent,
        total_percent=total_percent,
    )
    refresh_summary = await refresh_all_character_points(
        interaction,
        guild_config={"points_settings": settings},
    )
    return dict(settings), refresh_summary


async def update_class_point_override(
    interaction: discord.Interaction,
    *,
    class_name: str,
    loot_percent: float | None = None,
    bonus_percent: float | None = None,
    penalty_percent: float | None = None,
    total_percent: float | None = None,
    minimum_total: float | None = None,
    clear_minimum_total: bool = False,
) -> tuple[dict[str, Any], dict[str, Any], PointsRefreshSummary]:
    """Update one class override and refresh all PPE point totals."""
    settings = await get_points_settings(interaction)
    class_overrides = dict(settings.get("class_overrides", {}))

    existing = class_overrides.get(class_name, {})
    override = dict(existing) if isinstance(existing, dict) else {}

    if loot_percent is not None:
        override["loot_percent"] = float(loot_percent)
    if bonus_percent is not None:
        override["bonus_percent"] = float(bonus_percent)
    if penalty_percent is not None:
        override["penalty_percent"] = float(penalty_percent)
    if total_percent is not None:
        override["total_percent"] = float(total_percent)
    if minimum_total is not None:
        override["minimum_total"] = float(minimum_total)
    if clear_minimum_total:
        override["minimum_total"] = None

    override.setdefault("loot_percent", 0.0)
    override.setdefault("bonus_percent", 0.0)
    override.setdefault("penalty_percent", 0.0)
    override.setdefault("total_percent", 0.0)
    override.setdefault("minimum_total", None)

    class_overrides[class_name] = override
    settings["class_overrides"] = class_overrides
    saved = await set_points_settings(interaction, settings)
    saved_override = dict(saved.get("class_overrides", {}).get(class_name, {}))
    refresh_summary = await refresh_all_character_points(
        interaction,
        guild_config={"points_settings": saved},
    )
    return dict(saved), saved_override, refresh_summary


async def refresh_all_character_points(
    interaction: discord.Interaction,
    *,
    guild_config: dict[str, Any] | None = None,
) -> PointsRefreshSummary:
    """Recompute point totals for every PPE using current guild settings."""
    records = await load_player_records(interaction)
    effective_guild_config = guild_config if isinstance(guild_config, dict) else await load_guild_config(interaction)

    ppes_processed = 0
    ppes_updated = 0
    for player_data in records.values():
        for ppe in getattr(player_data, "ppes", []):
            ppes_processed += 1
            old_points = float(getattr(ppe, "points", 0.0))
            result = recompute_ppe_points(ppe, effective_guild_config)
            if abs(float(result["total"]) - old_points) > 0.01:
                ppes_updated += 1

    await save_player_records(interaction, records)
    return PointsRefreshSummary(ppes_processed=ppes_processed, ppes_updated=ppes_updated)


async def reset_season_data(
    interaction: discord.Interaction,
    *,
    clear_realmshark_links: bool,
) -> SeasonResetSummary:
    """Run the full season reset routine and return a summary for UX/reporting."""
    if interaction.guild is None:
        raise ValueError("This action can only be used in a server.")

    records = await load_player_records(interaction)
    config = await load_guild_config(interaction)
    default_reset_limit = int(config["quest_settings"]["num_resets"])

    teams = await load_teams(interaction)
    team_names = set(teams.keys())

    ppes_cleared, items_cleared, quest_entries_cleared = _reset_player_records(records, default_reset_limit)
    await save_player_records(interaction, records)

    teams_deleted = len(teams)
    teams.clear()
    await save_teams(interaction, teams)

    pending_files_cleared = await clear_all_pending_for_guild(interaction.guild.id)

    realmshark_settings = await get_realmshark_settings(interaction)
    raw_links = realmshark_settings.get("links", {})
    links = raw_links if isinstance(raw_links, dict) else {}
    realmshark_links_before = len(links)

    converted_bindings = 0
    tokens_updated = 0

    if clear_realmshark_links:
        await set_realmshark_settings(
            interaction,
            {
                "enabled": False,
                "mode": "addloot",
                "links": {},
                "announce_channel_id": 0,
                "endpoint": "",
            },
        )
    else:
        migrated_links, converted_bindings, tokens_updated = _migrate_realmshark_links_for_new_season(links)
        await set_realmshark_settings(
            interaction,
            {
                "enabled": bool(realmshark_settings.get("enabled", False)),
                "mode": "addloot",
                "links": migrated_links,
                "announce_channel_id": _coerce_channel_id(realmshark_settings.get("announce_channel_id", 0)),
                "endpoint": str(realmshark_settings.get("endpoint", "")).strip(),
            },
        )

    team_roles_deleted = await _delete_team_roles(interaction.guild, team_names)

    return SeasonResetSummary(
        ppes_cleared=ppes_cleared,
        items_cleared=items_cleared,
        quest_entries_cleared=quest_entries_cleared,
        teams_deleted=teams_deleted,
        team_roles_deleted=team_roles_deleted,
        default_reset_limit=default_reset_limit,
        realmshark_links_before=realmshark_links_before,
        pending_files_cleared=pending_files_cleared,
        clear_realmshark_links=clear_realmshark_links,
        converted_bindings=converted_bindings,
        tokens_updated=tokens_updated,
    )


def _reset_player_records(records: dict[str, Any], default_reset_limit: int) -> tuple[int, int, int]:
    """Clear per-player season state while preserving membership and role status."""
    items_cleared = 0
    ppes_cleared = 0
    quest_entries_cleared = 0

    for player_data in records.values():
        ppes = getattr(player_data, "ppes", [])
        ppes_cleared += len(ppes)
        ppes.clear()
        player_data.active_ppe = None

        unique_items = getattr(player_data, "unique_items", set())
        items_cleared += len(unique_items)
        unique_items.clear()

        quests = getattr(player_data, "quests", None)
        if quests is not None:
            for field_name in (
                "current_items",
                "current_shinies",
                "current_skins",
                "completed_items",
                "completed_shinies",
                "completed_skins",
            ):
                entries = getattr(quests, field_name, [])
                quest_entries_cleared += len(entries)
                entries.clear()

        player_data.quest_resets_remaining = default_reset_limit
        player_data.team_name = None

    return ppes_cleared, items_cleared, quest_entries_cleared


def _migrate_realmshark_links_for_new_season(
    links: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], int, int]:
    """Convert legacy PPE character mappings into seasonal character mappings."""
    migrated_links: dict[str, dict[str, Any]] = {}
    converted_bindings = 0
    tokens_updated = 0

    for token, raw_link_data in links.items():
        if not isinstance(token, str) or not token.strip() or not isinstance(raw_link_data, dict):
            continue

        link_data = dict(raw_link_data)
        raw_bindings = link_data.get("character_bindings", {})
        bindings = raw_bindings if isinstance(raw_bindings, dict) else {}

        seasonal_ids = _normalize_seasonal_ids(link_data.get("seasonal_character_ids", []))
        binding_ids: list[str] = []
        for character_id in bindings.keys():
            parsed = _parse_positive_int(character_id)
            if parsed is None:
                continue
            binding_ids.append(str(parsed))

        if binding_ids:
            converted_bindings += len(binding_ids)
            seasonal_ids.update(binding_ids)
            link_data["character_bindings"] = {}
            link_data["seasonal_character_ids"] = sorted(seasonal_ids, key=int)
            tokens_updated += 1

        migrated_links[token] = link_data

    return migrated_links, converted_bindings, tokens_updated


def _normalize_seasonal_ids(raw_values: Any) -> set[str]:
    seasonal_ids: set[str] = set()
    if not isinstance(raw_values, list):
        return seasonal_ids

    for value in raw_values:
        parsed = _parse_positive_int(value)
        if parsed is None:
            continue
        seasonal_ids.add(str(parsed))

    return seasonal_ids


def _parse_positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _coerce_channel_id(value: Any) -> int:
    parsed = _parse_positive_int(value)
    return parsed if parsed is not None else 0


async def _delete_team_roles(guild: discord.Guild, team_names: set[str]) -> int:
    """Delete non-managed Discord team roles that match previous team names."""
    deleted = 0
    for team_name in team_names:
        if not team_name:
            continue

        try:
            team_role = discord.utils.get(guild.roles, name=team_name)
            if team_role and not team_role.managed:
                await team_role.delete(reason="Season reset - team cleanup")
                deleted += 1
        except (discord.Forbidden, discord.HTTPException):
            # Non-blocking cleanup: keep reset flow successful even if one role cannot be removed.
            continue

    return deleted

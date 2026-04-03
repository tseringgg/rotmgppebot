"""Business logic for /manageseason reset and point-settings operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import discord

from utils.ppe_types import normalize_allowed_ppe_types, normalize_ppe_type_multipliers
from utils.guild_config import (
    get_contest_settings,
    get_max_ppes,
    get_ppe_settings,
    get_points_settings,
    get_realmshark_settings,
    load_guild_config,
    set_contest_settings,
    set_max_ppes,
    set_ppe_settings,
    set_points_settings,
    set_realmshark_settings,
    update_global_points_modifiers,
)
from utils.player_records import load_player_records, load_teams, save_player_records, save_teams
from utils.points_service import recompute_ppe_points
from utils.realmshark_pending_store import clear_all_pending_for_guild
from utils.contest_leaderboards import normalize_contest_leaderboard_id
from utils.realmshark_cleanup import clear_ppe_character_links


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


@dataclass(slots=True)
class MaxCharactersUpdateSummary:
    """Structured result payload for max-character limit updates."""

    old_limit: int
    new_limit: int
    players_trimmed: int
    characters_deleted: int
    inactive_characters_deleted: int
    active_characters_deleted: int


async def load_points_settings_for_menu(interaction: discord.Interaction) -> dict[str, Any]:
    """Load point settings for point-settings embeds/views."""
    settings = await get_points_settings(interaction)
    return dict(settings)


async def load_character_settings_for_menu(interaction: discord.Interaction) -> dict[str, Any]:
    """Load character settings for character-settings embeds/views."""
    settings = await get_ppe_settings(interaction)
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


def _build_join_contest_embed(*, role: discord.Role, emoji: str) -> discord.Embed:
    embed = discord.Embed(
        title="Join the PPE Contest",
        description=(
            f"React with {emoji} to this message to receive the {role.mention} role.\n"
            "After joining, use `/ppehelp` for setup and command guidance."
        ),
        color=discord.Color.green(),
    )
    embed.set_footer(text="Only one join embed can exist at a time.")
    return embed


async def create_join_contest_embed(
    interaction: discord.Interaction,
    *,
    channel_id: int,
) -> dict[str, Any]:
    """Create the single allowed join-contest embed and persist its message reference."""
    if interaction.guild is None:
        raise ValueError("This action can only be used in a server.")

    settings = await get_contest_settings(interaction)
    existing_message_id = int(settings.get("join_contest_message_id", 0) or 0)
    if existing_message_id > 0:
        raise ValueError("A join embed is already configured. Delete it first.")

    channel = interaction.guild.get_channel(int(channel_id))
    if not isinstance(channel, discord.TextChannel):
        raise ValueError("Please provide a valid text channel in this server.")

    role = discord.utils.get(interaction.guild.roles, name="PPE Player")
    if role is None:
        raise ValueError("PPE Player role not found. Create it first.")

    emoji = str(settings.get("join_contest_emoji", "✅") or "✅").strip() or "✅"
    embed = _build_join_contest_embed(role=role, emoji=emoji)
    message = await channel.send(embed=embed)

    try:
        await message.add_reaction(emoji)
    except discord.HTTPException as exc:
        try:
            await message.delete()
        except discord.HTTPException:
            pass
        raise ValueError("Failed to add the reaction emoji to the join embed message.") from exc

    settings["join_contest_channel_id"] = int(channel.id)
    settings["join_contest_message_id"] = int(message.id)
    settings["join_contest_emoji"] = emoji
    saved = await set_contest_settings(interaction, settings)
    return {
        "channel_id": int(channel.id),
        "message_id": int(message.id),
        "settings": dict(saved),
    }


async def delete_join_contest_embed(interaction: discord.Interaction) -> dict[str, Any]:
    """Delete and clear the currently configured join-contest embed reference."""
    if interaction.guild is None:
        raise ValueError("This action can only be used in a server.")

    settings = await get_contest_settings(interaction)
    channel_id = int(settings.get("join_contest_channel_id", 0) or 0)
    message_id = int(settings.get("join_contest_message_id", 0) or 0)
    deleted_message = False

    if channel_id > 0 and message_id > 0:
        channel = interaction.guild.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            try:
                message = await channel.fetch_message(message_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                message = None

            if message is not None:
                try:
                    await message.delete()
                    deleted_message = True
                except (discord.Forbidden, discord.HTTPException):
                    deleted_message = False

    settings["join_contest_channel_id"] = 0
    settings["join_contest_message_id"] = 0
    saved = await set_contest_settings(interaction, settings)
    return {
        "deleted_message": deleted_message,
        "settings": dict(saved),
    }


def _ppe_sort_key_lowest_points(ppe: Any) -> tuple[float, int]:
    points_raw = getattr(ppe, "points", 0.0)
    try:
        points_value = float(points_raw)
    except (TypeError, ValueError):
        points_value = 0.0

    try:
        ppe_id = int(getattr(ppe, "id", 0))
    except (TypeError, ValueError):
        ppe_id = 0
    return (points_value, ppe_id)


def _rebuild_unique_items(player_data: Any) -> None:
    unique_items: set[tuple[str, bool]] = set()
    for ppe in getattr(player_data, "ppes", []):
        for loot_item in getattr(ppe, "loot", []):
            name = str(getattr(loot_item, "item_name", "")).strip()
            if not name:
                continue
            unique_items.add((name, bool(getattr(loot_item, "shiny", False))))
    player_data.unique_items = unique_items


async def update_max_characters_limit(
    interaction: discord.Interaction,
    *,
    new_limit: int,
) -> MaxCharactersUpdateSummary:
    """Update max PPE character limit and trim excess characters if reducing the cap."""
    old_limit = await get_max_ppes(interaction)
    coerced_new_limit = max(1, int(new_limit))

    players_trimmed = 0
    total_deleted = 0
    inactive_deleted = 0
    active_deleted = 0

    if coerced_new_limit < old_limit:
        records = await load_player_records(interaction)
        changed = False

        for user_id, player_data in records.items():
            ppes = list(getattr(player_data, "ppes", []))
            overflow = len(ppes) - coerced_new_limit
            if overflow <= 0:
                continue

            active_ppe_id = getattr(player_data, "active_ppe", None)
            inactive_candidates = sorted(
                [ppe for ppe in ppes if int(getattr(ppe, "id", 0)) != int(active_ppe_id or 0)],
                key=_ppe_sort_key_lowest_points,
            )
            active_candidates = sorted(
                [ppe for ppe in ppes if int(getattr(ppe, "id", 0)) == int(active_ppe_id or 0)],
                key=_ppe_sort_key_lowest_points,
            )

            removal_order = inactive_candidates + active_candidates
            to_remove = removal_order[:overflow]
            if not to_remove:
                continue

            remove_ids = {int(getattr(ppe, "id", 0)) for ppe in to_remove}
            removed_active_count = sum(1 for ppe in to_remove if int(getattr(ppe, "id", 0)) == int(active_ppe_id or 0))
            removed_inactive_count = len(to_remove) - removed_active_count

            player_data.ppes = [ppe for ppe in ppes if int(getattr(ppe, "id", 0)) not in remove_ids]

            if active_ppe_id is not None and int(active_ppe_id) in remove_ids:
                if player_data.ppes:
                    replacement = max(player_data.ppes, key=lambda p: (float(getattr(p, "points", 0.0)), int(getattr(p, "id", 0))))
                    player_data.active_ppe = int(getattr(replacement, "id", 0))
                else:
                    player_data.active_ppe = None

            _rebuild_unique_items(player_data)

            for removed_ppe_id in sorted(remove_ids):
                await clear_ppe_character_links(interaction, int(user_id), int(removed_ppe_id))

            players_trimmed += 1
            total_deleted += len(to_remove)
            inactive_deleted += removed_inactive_count
            active_deleted += removed_active_count
            changed = True

        if changed:
            await save_player_records(interaction, records)

    await set_max_ppes(interaction, max_ppes=coerced_new_limit)

    return MaxCharactersUpdateSummary(
        old_limit=int(old_limit),
        new_limit=int(coerced_new_limit),
        players_trimmed=players_trimmed,
        characters_deleted=total_deleted,
        inactive_characters_deleted=inactive_deleted,
        active_characters_deleted=active_deleted,
    )


async def update_ppe_type_feature_enabled(
    interaction: discord.Interaction,
    *,
    enabled: bool,
) -> dict[str, Any]:
    settings = await get_ppe_settings(interaction)
    settings["enable_ppe_types"] = bool(enabled)
    saved = await set_ppe_settings(interaction, settings)
    return dict(saved)


async def update_allowed_ppe_types(
    interaction: discord.Interaction,
    *,
    allowed_types: list[str],
) -> dict[str, Any]:
    settings = await get_ppe_settings(interaction)
    settings["allowed_ppe_types"] = normalize_allowed_ppe_types(allowed_types)
    saved = await set_ppe_settings(interaction, settings)
    return dict(saved)


async def update_ppe_type_multipliers(
    interaction: discord.Interaction,
    *,
    multipliers: dict[str, float],
) -> tuple[dict[str, Any], PointsRefreshSummary]:
    settings = await get_ppe_settings(interaction)
    settings["ppe_type_multipliers"] = normalize_ppe_type_multipliers(multipliers)
    saved = await set_ppe_settings(interaction, settings)

    guild_config = await load_guild_config(interaction)
    guild_config["ppe_settings"] = dict(saved)
    refresh_summary = await refresh_all_character_points(
        interaction,
        guild_config=guild_config,
    )
    return dict(saved), refresh_summary


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

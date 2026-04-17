"""Business logic for /manageseason reset and point-settings operations."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any

import discord

from utils.ppe_types import normalize_allowed_ppe_types, normalize_ppe_type_multipliers
from utils.bot_cost_tracking import (
    ensure_guild_cost_log_file,
    clear_guild_cost_log,
    get_cost_rate_per_gb_minute,
    get_guild_cost_log_path,
    summarize_guild_cost_log,
)
from utils.guild_config import (
    get_contest_settings,
    get_max_ppes,
    get_ppe_settings,
    get_points_settings,
    get_realmshark_settings,
    load_guild_config,
    save_guild_config,
    set_contest_settings,
    set_max_ppes,
    set_ppe_settings,
    set_points_settings,
    set_realmshark_settings,
    update_global_points_modifiers,
    update_starting_penalty_modifiers,
)
from utils.player_records import load_player_records, load_teams, save_player_records, save_teams
from utils.points_service import recompute_ppe_points
from utils.sniffer_helpers.realmshark_pending_store import clear_all_pending_for_guild
from utils.contest_leaderboards import normalize_contest_leaderboard_id
from utils.sniffer_helpers.realmshark_cleanup import clear_ppe_character_links
from utils.settings.channel_settings import (
    clear_item_suggestions_enabled_channels,
    set_item_suggestions_mode_enabled,
)


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


@dataclass(slots=True)
class ResetPPECharactersSummary:
    """Structured result payload for clearing all PPE characters and loot."""

    players_updated: int
    ppes_cleared: int


@dataclass(slots=True)
class ResetQuestsSummary:
    """Structured result payload for clearing quest progress only."""

    players_updated: int
    quest_entries_cleared: int
    default_reset_limit: int


@dataclass(slots=True)
class ResetSeasonalInfoSummary:
    """Structured result payload for clearing seasonal-only progress state."""

    players_updated: int
    unique_items_cleared: int
    quest_entries_cleared: int
    default_reset_limit: int


@dataclass(slots=True)
class ResetTeamsSummary:
    """Structured result payload for clearing team records and roles."""

    teams_deleted: int
    team_roles_deleted: int
    players_unassigned: int


@dataclass(slots=True)
class ResetSnifferOptions:
    """Selectable sniffer reset options for the reset submenu."""

    clear_character_mappings: bool = True
    revoke_tokens: bool = False
    clear_pending_files: bool = True
    clear_output_channel: bool = False
    clear_endpoint: bool = False
    disable_sniffer: bool = False


@dataclass(slots=True)
class ResetSnifferSummary:
    """Structured result payload for configurable sniffer resets."""

    links_before: int
    links_after: int
    tokens_revoked: int
    character_bindings_cleared: int
    seasonal_ids_cleared: int
    metadata_entries_cleared: int
    pending_files_cleared: int
    endpoint_cleared: bool
    output_channel_cleared: bool
    sniffer_disabled: bool


def _count_unique_items_from_history(season_item_history: Any) -> int:
    if not isinstance(season_item_history, dict) or not season_item_history:
        return 0
    return len({
        key.split("|")[0]
        for key in season_item_history.keys()
        if isinstance(key, str) and key and "|" in key and key.split("|")[0]
    })


@dataclass(slots=True)
class ResetSettingsSummary:
    """Structured result payload for resetting admin-tunable settings."""

    endpoint_preserved: bool
    join_embed_preserved: bool
    picture_suggestion_channels_cleared: int


@dataclass(slots=True)
class BulkRoleUpdateSummary:
    """Structured result payload for bulk role assignment removals."""

    role_name: str
    role_found: bool
    members_updated: int
    members_failed: int
    records_cleared: int = 0
    tokens_revoked: int = 0
    removed_member_ids: list[int] = field(default_factory=list)


@dataclass(slots=True)
class JoinEmbedResetSummary:
    """Structured result payload for clearing join embed settings."""

    join_embed_was_configured: bool
    join_embed_message_deleted: bool


@dataclass(slots=True)
class RoleDeleteSummary:
    """Structured result payload for deleting PPE and team role objects."""

    ppe_roles_deleted: int
    ppe_roles_failed: int
    team_roles_deleted: int
    team_roles_failed: int


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


async def _update_contest_bool_setting(
    interaction: discord.Interaction,
    *,
    setting_key: str,
    enabled: bool,
) -> dict[str, Any]:
    settings = await get_contest_settings(interaction)
    settings[setting_key] = bool(enabled)
    saved = await set_contest_settings(interaction, settings)
    return dict(saved)


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
    return await _update_contest_bool_setting(
        interaction,
        setting_key="team_contest_include_quest_points",
        enabled=enabled,
    )


async def update_ppe_contest_quest_points_setting(
    interaction: discord.Interaction,
    *,
    enabled: bool,
) -> dict[str, Any]:
    """Toggle whether PPE contest leaderboard should include quest points."""
    return await _update_contest_bool_setting(
        interaction,
        setting_key="ppe_contest_include_quest_points",
        enabled=enabled,
    )


async def update_ppe_contest_active_ppe_quest_filter_setting(
    interaction: discord.Interaction,
    *,
    enabled: bool,
) -> dict[str, Any]:
    """Toggle whether PPE contest quest points only count items on the active PPE."""
    return await _update_contest_bool_setting(
        interaction,
        setting_key="ppe_contest_require_active_ppe_quest_items",
        enabled=enabled,
    )


async def update_ppe_aggregate_points_setting(
    interaction: discord.Interaction,
    *,
    enabled: bool,
) -> dict[str, Any]:
    """Toggle whether PPE leaderboard scores should aggregate all characters."""
    return await _update_contest_bool_setting(
        interaction,
        setting_key="ppe_aggregate_points_enabled",
        enabled=enabled,
    )


async def update_team_aggregate_points_setting(
    interaction: discord.Interaction,
    *,
    enabled: bool,
) -> dict[str, Any]:
    """Toggle whether team contest scores should aggregate all team characters."""
    return await _update_contest_bool_setting(
        interaction,
        setting_key="team_aggregate_points_enabled",
        enabled=enabled,
    )


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

    resolver = getattr(interaction.guild, "get_channel_or_thread", interaction.guild.get_channel)
    channel = resolver(int(channel_id))
    if not isinstance(channel, (discord.TextChannel, discord.Thread)):
        raise ValueError("Please provide a valid text channel or thread in this server.")

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
        resolver = getattr(interaction.guild, "get_channel_or_thread", interaction.guild.get_channel)
        channel = resolver(channel_id)
        if isinstance(channel, (discord.TextChannel, discord.Thread)):
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


async def update_pet_point_modifiers(
    interaction: discord.Interaction,
    *,
    pet_level_percent_reduction: float | None = None,
    exalts_percent_reduction: float | None = None,
    loot_percent_reduction: float | None = None,
    incombat_percent_reduction: float | None = None,
    pet_points_per_level: float | None = None,
) -> tuple[dict[str, Any], PointsRefreshSummary]:
    """Update starting penalty reductions and refresh all PPE totals."""
    settings = await update_starting_penalty_modifiers(
        interaction,
        pet_level_percent_reduction=pet_level_percent_reduction,
        exalts_percent_reduction=exalts_percent_reduction,
        loot_percent_reduction=loot_percent_reduction,
        incombat_percent_reduction=incombat_percent_reduction,
    )

    if pet_points_per_level is not None:
        safe_points = abs(float(pet_points_per_level))
        penalty_weights = (
            dict(settings.get("penalty_weights", {}))
            if isinstance(settings.get("penalty_weights"), dict)
            else {}
        )
        penalty_weights["pet_level_per_point"] = 0.0 if safe_points == 0 else 1.0 / safe_points
        settings["penalty_weights"] = penalty_weights
        settings = await set_points_settings(interaction, settings)

    refresh_summary = await refresh_all_character_points(
        interaction,
        guild_config={"points_settings": settings},
    )
    return dict(settings), refresh_summary


async def update_penalty_base_rates(
    interaction: discord.Interaction,
    *,
    pet_points_per_level: float | None = None,
    exalts_points_per_exalt: float | None = None,
    loot_points_per_percent: float | None = None,
    incombat_points_per_second: float | None = None,
) -> tuple[dict[str, Any], PointsRefreshSummary]:
    """Update penalty base-rate weights and refresh all PPE totals."""
    settings = await get_points_settings(interaction)
    penalty_weights = (
        dict(settings.get("penalty_weights", {}))
        if isinstance(settings.get("penalty_weights"), dict)
        else {}
    )

    if pet_points_per_level is not None:
        safe_points = abs(float(pet_points_per_level))
        penalty_weights["pet_level_per_point"] = 0.0 if safe_points == 0 else 1.0 / safe_points

    if exalts_points_per_exalt is not None:
        safe_points = abs(float(exalts_points_per_exalt))
        penalty_weights["exalts_per_point"] = 0.0 if safe_points == 0 else 1.0 / safe_points

    if loot_points_per_percent is not None:
        safe_points = abs(float(loot_points_per_percent))
        penalty_weights["loot_percent_per_point"] = 0.0 if safe_points == 0 else 1.0 / safe_points

    if incombat_points_per_second is not None:
        safe_points = abs(float(incombat_points_per_second))
        penalty_weights["incombat_seconds_per_point"] = 0.0 if safe_points == 0 else 1.0 / safe_points

    settings["penalty_weights"] = penalty_weights
    settings = await set_points_settings(interaction, settings)

    refresh_summary = await refresh_all_character_points(
        interaction,
        guild_config={"points_settings": settings},
    )
    return dict(settings), refresh_summary


async def update_duplicate_item_point_reduction(
    interaction: discord.Interaction,
    *,
    duplicate_point_reduction: float,
) -> tuple[dict[str, Any], PointsRefreshSummary]:
    """Update duplicate item reduction multiplier and refresh all PPE totals."""
    settings = await update_global_points_modifiers(
        interaction,
        duplicate_point_reduction=max(0.0, float(duplicate_point_reduction)),
    )
    refresh_summary = await refresh_all_character_points(
        interaction,
        guild_config={"points_settings": settings},
    )
    return dict(settings), refresh_summary


async def update_duplicate_match_mode(
    interaction: discord.Interaction,
    *,
    duplicate_match_mode: str,
) -> tuple[dict[str, Any], PointsRefreshSummary]:
    """Update duplicate matching mode and refresh all PPE totals."""
    allowed_modes = {"separate_rarity", "any_rarity", "non_divine_any_rarity", "all_including_shiny"}
    normalized_mode = str(duplicate_match_mode).strip().lower()
    if normalized_mode not in allowed_modes:
        raise ValueError("Invalid duplicate match mode.")

    settings = await get_points_settings(interaction)
    settings["duplicate_match_mode"] = normalized_mode
    settings = await set_points_settings(interaction, settings)

    refresh_summary = await refresh_all_character_points(
        interaction,
        guild_config={"points_settings": settings},
    )
    return dict(settings), refresh_summary


async def update_top_point_mode(
    interaction: discord.Interaction,
    *,
    tops_point_mode: str,
) -> tuple[dict[str, Any], PointsRefreshSummary]:
    """Update how Tops loot is scored and refresh all PPE totals."""
    settings = await get_points_settings(interaction)
    mode = str(tops_point_mode).strip().lower()
    if mode not in {"current", "once", "none"}:
        raise ValueError("Invalid top point mode.")

    settings["tops_point_mode"] = mode
    settings = await set_points_settings(interaction, settings)

    refresh_summary = await refresh_all_character_points(
        interaction,
        guild_config={"points_settings": settings},
    )
    return dict(settings), refresh_summary


async def update_rarity_multipliers(
    interaction: discord.Interaction,
    *,
    common: float | None = None,
    uncommon: float | None = None,
    rare: float | None = None,
    legendary: float | None = None,
    divine: float | None = None,
    shiny: float | None = None,
) -> tuple[dict[str, Any], PointsRefreshSummary]:
    """Update rarity multipliers and refresh all PPE totals."""
    settings = await get_points_settings(interaction)
    rarity_multipliers = (
        dict(settings.get("rarity_multipliers", {}))
        if isinstance(settings.get("rarity_multipliers"), dict)
        else {}
    )

    updates = {
        "common": common,
        "uncommon": uncommon,
        "rare": rare,
        "legendary": legendary,
        "divine": divine,
        "shiny": shiny,
    }
    for rarity, value in updates.items():
        if value is None:
            continue
        rarity_multipliers[rarity] = max(0.0, float(value))

    settings["rarity_multipliers"] = rarity_multipliers
    settings = await set_points_settings(interaction, settings)
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
    if isinstance(guild_config, dict):
        base_config = await load_guild_config(interaction)
        effective_guild_config = dict(base_config)
        effective_guild_config.update(guild_config)
    else:
        effective_guild_config = await load_guild_config(interaction)

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


def _iter_player_quest_fields() -> tuple[str, ...]:
    return (
        "current_items",
        "current_shinies",
        "current_skins",
        "completed_items",
        "completed_shinies",
        "completed_skins",
    )


def _collect_team_names_from_records(records: dict[int, Any]) -> set[str]:
    team_names: set[str] = set()
    for player_data in records.values():
        team_name = getattr(player_data, "team_name", None)
        if isinstance(team_name, str) and team_name.strip():
            team_names.add(team_name.strip())
    return team_names


def _clear_team_quest_mode_state(config: dict[str, Any], *, disable_team_mode: bool = False) -> bool:
    quest_settings = config.get("quest_settings", {}) if isinstance(config.get("quest_settings", {}), dict) else {}
    changed = False

    if quest_settings.get("team_quests_state") != {}:
        quest_settings["team_quests_state"] = {}
        changed = True

    if disable_team_mode and bool(quest_settings.get("enable_team_quests", False)):
        quest_settings["enable_team_quests"] = False
        changed = True

    if changed:
        config["quest_settings"] = quest_settings
    return changed


async def reset_all_ppe_characters(interaction: discord.Interaction) -> ResetPPECharactersSummary:
    """Reset all character records while preserving seasonal and quest progress."""
    records = await load_player_records(interaction)

    players_updated = 0
    ppes_cleared = 0

    for player_data in records.values():
        player_changed = False

        ppes = getattr(player_data, "ppes", [])
        if ppes:
            ppes_cleared += len(ppes)
            ppes.clear()
            player_changed = True

        if getattr(player_data, "active_ppe", None) is not None:
            player_data.active_ppe = None
            player_changed = True

        if player_changed:
            players_updated += 1

    await save_player_records(interaction, records)
    return ResetPPECharactersSummary(
        players_updated=players_updated,
        ppes_cleared=ppes_cleared,
    )


async def reset_all_quests(interaction: discord.Interaction) -> ResetQuestsSummary:
    """Reset quest progress and quest reset counters while preserving other seasonal data."""
    records = await load_player_records(interaction)
    config = await load_guild_config(interaction)
    default_reset_limit = int(config["quest_settings"]["num_resets"])
    config_changed = _clear_team_quest_mode_state(config)

    players_updated = 0
    quest_entries_cleared = 0

    for player_data in records.values():
        player_changed = False

        quests = getattr(player_data, "quests", None)
        if quests is not None:
            for field_name in _iter_player_quest_fields():
                entries = getattr(quests, field_name, [])
                if entries:
                    quest_entries_cleared += len(entries)
                    entries.clear()
                    player_changed = True

        if getattr(player_data, "quest_resets_remaining", None) != default_reset_limit:
            player_data.quest_resets_remaining = default_reset_limit
            player_changed = True

        if player_changed:
            players_updated += 1

    await save_player_records(interaction, records)
    if config_changed:
        await save_guild_config(interaction, config)
    return ResetQuestsSummary(
        players_updated=players_updated,
        quest_entries_cleared=quest_entries_cleared,
        default_reset_limit=default_reset_limit,
    )


async def reset_all_seasonal_information(interaction: discord.Interaction) -> ResetSeasonalInfoSummary:
    """Reset seasonal progress state for all players while preserving character records."""
    records = await load_player_records(interaction)
    config = await load_guild_config(interaction)
    default_reset_limit = int(config["quest_settings"]["num_resets"])
    config_changed = _clear_team_quest_mode_state(config)

    players_updated = 0
    unique_items_cleared = 0
    quest_entries_cleared = 0

    for player_data in records.values():
        player_changed = False

        season_item_history = getattr(player_data, "season_item_history", {})
        if isinstance(season_item_history, dict) and season_item_history:
            unique_items_cleared += _count_unique_items_from_history(season_item_history)
            season_item_history.clear()
            player_changed = True

        quests = getattr(player_data, "quests", None)
        if quests is not None:
            for field_name in _iter_player_quest_fields():
                entries = getattr(quests, field_name, [])
                if entries:
                    quest_entries_cleared += len(entries)
                    entries.clear()
                    player_changed = True

        if getattr(player_data, "quest_resets_remaining", None) != default_reset_limit:
            player_data.quest_resets_remaining = default_reset_limit
            player_changed = True

        if player_changed:
            players_updated += 1

    await save_player_records(interaction, records)
    if config_changed:
        await save_guild_config(interaction, config)
    return ResetSeasonalInfoSummary(
        players_updated=players_updated,
        unique_items_cleared=unique_items_cleared,
        quest_entries_cleared=quest_entries_cleared,
        default_reset_limit=default_reset_limit,
    )


async def reset_all_teams(interaction: discord.Interaction) -> ResetTeamsSummary:
    """Remove team records, clear player team assignment, and delete matching team roles."""
    if interaction.guild is None:
        raise ValueError("This action can only be used in a server.")

    records = await load_player_records(interaction)
    teams = await load_teams(interaction)
    config = await load_guild_config(interaction)
    config_changed = _clear_team_quest_mode_state(config, disable_team_mode=True)

    team_names = set(teams.keys())
    team_names.update(_collect_team_names_from_records(records))

    players_unassigned = 0
    for player_data in records.values():
        if getattr(player_data, "team_name", None):
            player_data.team_name = None
            players_unassigned += 1

    await save_player_records(interaction, records)

    teams_deleted = len(teams)
    teams.clear()
    await save_teams(interaction, teams)
    if config_changed:
        await save_guild_config(interaction, config)

    team_roles_deleted = await _delete_team_roles(interaction.guild, team_names)
    return ResetTeamsSummary(
        teams_deleted=teams_deleted,
        team_roles_deleted=team_roles_deleted,
        players_unassigned=players_unassigned,
    )


def _normalize_realmshark_links(settings: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_links = settings.get("links", {})
    if not isinstance(raw_links, dict):
        return {}
    normalized: dict[str, dict[str, Any]] = {}
    for token, link_data in raw_links.items():
        if isinstance(token, str) and token.strip() and isinstance(link_data, dict):
            normalized[token] = dict(link_data)
    return normalized


def _clear_sniffer_link_character_data(link_data: dict[str, Any]) -> tuple[int, int, int]:
    bindings = link_data.get("character_bindings", {})
    seasonal_ids = link_data.get("seasonal_character_ids", [])
    metadata = link_data.get("character_metadata", {})

    bindings_count = len(bindings) if isinstance(bindings, dict) else 0
    seasonal_count = len(seasonal_ids) if isinstance(seasonal_ids, list) else 0
    metadata_count = len(metadata) if isinstance(metadata, dict) else 0

    link_data["character_bindings"] = {}
    link_data["seasonal_character_ids"] = []
    link_data["character_metadata"] = {}
    link_data["last_seen_character_id"] = 0

    return bindings_count, seasonal_count, metadata_count


async def reset_sniffer_data(
    interaction: discord.Interaction,
    *,
    options: ResetSnifferOptions,
) -> ResetSnifferSummary:
    """Apply selected sniffer reset actions without forcing a full reset."""
    if interaction.guild is None:
        raise ValueError("This action can only be used in a server.")

    settings = await get_realmshark_settings(interaction)
    links = _normalize_realmshark_links(settings)

    links_before = len(links)
    links_after = links_before
    tokens_revoked = 0
    character_bindings_cleared = 0
    seasonal_ids_cleared = 0
    metadata_entries_cleared = 0

    if options.revoke_tokens:
        tokens_revoked = links_before
        links_after = 0
        links = {}
    elif options.clear_character_mappings:
        for link_data in links.values():
            bindings_count, seasonal_count, metadata_count = _clear_sniffer_link_character_data(link_data)
            character_bindings_cleared += bindings_count
            seasonal_ids_cleared += seasonal_count
            metadata_entries_cleared += metadata_count

    settings["links"] = links
    if options.clear_output_channel:
        settings["announce_channel_id"] = 0
    if options.clear_endpoint:
        settings["endpoint"] = ""
    if options.disable_sniffer:
        settings["enabled"] = False

    await set_realmshark_settings(interaction, settings)

    pending_files_cleared = 0
    if options.clear_pending_files:
        pending_files_cleared = await clear_all_pending_for_guild(interaction.guild.id)

    return ResetSnifferSummary(
        links_before=links_before,
        links_after=links_after,
        tokens_revoked=tokens_revoked,
        character_bindings_cleared=character_bindings_cleared,
        seasonal_ids_cleared=seasonal_ids_cleared,
        metadata_entries_cleared=metadata_entries_cleared,
        pending_files_cleared=pending_files_cleared,
        endpoint_cleared=bool(options.clear_endpoint),
        output_channel_cleared=bool(options.clear_output_channel),
        sniffer_disabled=bool(options.disable_sniffer),
    )


async def reset_admin_tunable_settings_to_defaults(interaction: discord.Interaction) -> ResetSettingsSummary:
    """Reset all admin-tunable settings to defaults while preserving endpoint and join embed message refs."""
    if interaction.guild is None:
        raise ValueError("This action can only be used in a server.")

    config = await load_guild_config(interaction)
    realmshark_settings = dict(config.get("realmshark_settings", {}))
    contest_settings = dict(config.get("contest_settings", {}))

    preserved_endpoint = str(realmshark_settings.get("endpoint", "")).strip()
    preserved_join_channel_id = int(contest_settings.get("join_contest_channel_id", 0) or 0)
    preserved_join_message_id = int(contest_settings.get("join_contest_message_id", 0) or 0)
    preserved_join_emoji = str(contest_settings.get("join_contest_emoji", "✅") or "✅").strip() or "✅"

    reset_config = await save_guild_config(interaction, {})

    reset_realmshark_settings = dict(reset_config.get("realmshark_settings", {}))
    reset_realmshark_settings["endpoint"] = preserved_endpoint
    reset_config["realmshark_settings"] = reset_realmshark_settings

    reset_contest_settings = dict(reset_config.get("contest_settings", {}))
    reset_contest_settings["join_contest_channel_id"] = preserved_join_channel_id
    reset_contest_settings["join_contest_message_id"] = preserved_join_message_id
    reset_contest_settings["join_contest_emoji"] = preserved_join_emoji
    reset_config["contest_settings"] = reset_contest_settings

    await save_guild_config(interaction, reset_config)

    guild_id = str(interaction.guild.id)
    picture_suggestion_channels_cleared = await clear_item_suggestions_enabled_channels(guild_id)
    await set_item_suggestions_mode_enabled(guild_id, False)

    return ResetSettingsSummary(
        endpoint_preserved=bool(preserved_endpoint),
        join_embed_preserved=preserved_join_channel_id > 0 and preserved_join_message_id > 0,
        picture_suggestion_channels_cleared=picture_suggestion_channels_cleared,
    )


async def _remove_role_from_all_members(
    guild: discord.Guild,
    *,
    role_name: str,
    reason: str,
) -> BulkRoleUpdateSummary:
    role = discord.utils.get(guild.roles, name=role_name)
    if role is None:
        return BulkRoleUpdateSummary(
            role_name=role_name,
            role_found=False,
            members_updated=0,
            members_failed=0,
            records_cleared=0,
            tokens_revoked=0,
            removed_member_ids=[],
        )

    target_members = list(role.members)
    members_updated = 0
    members_failed = 0
    removed_member_ids: list[int] = []
    for member in target_members:
        try:
            await member.remove_roles(role, reason=reason)
            members_updated += 1
            removed_member_ids.append(int(member.id))
        except (discord.Forbidden, discord.HTTPException):
            members_failed += 1

    return BulkRoleUpdateSummary(
        role_name=role_name,
        role_found=True,
        members_updated=members_updated,
        members_failed=members_failed,
        records_cleared=0,
        tokens_revoked=0,
        removed_member_ids=removed_member_ids,
    )


async def _clear_join_embed_reactions(
    interaction: discord.Interaction,
    *,
    member_ids: list[int],
) -> int:
    if interaction.guild is None or not member_ids:
        return 0

    settings = await get_contest_settings(interaction)
    join_channel_id = int(settings.get("join_contest_channel_id", 0) or 0)
    join_message_id = int(settings.get("join_contest_message_id", 0) or 0)
    join_emoji = str(settings.get("join_contest_emoji", "✅") or "✅").strip() or "✅"

    if join_channel_id <= 0 or join_message_id <= 0:
        return 0

    resolver = getattr(interaction.guild, "get_channel_or_thread", interaction.guild.get_channel)
    channel = resolver(join_channel_id)
    if not isinstance(channel, (discord.TextChannel, discord.Thread)):
        return 0

    try:
        message = await channel.fetch_message(join_message_id)
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return 0

    removed_reactions = 0
    for member_id in member_ids:
        member = interaction.guild.get_member(member_id)
        if member is None:
            try:
                member = await interaction.guild.fetch_member(member_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                continue

        try:
            await message.remove_reaction(join_emoji, member)
            removed_reactions += 1
        except (discord.Forbidden, discord.HTTPException):
            continue

    return removed_reactions


async def remove_ppe_player_role_from_everyone(interaction: discord.Interaction) -> BulkRoleUpdateSummary:
    """Remove PPE Player role from all members, revoke tokens, and clear all player records."""
    if interaction.guild is None:
        raise ValueError("This action can only be used in a server.")

    summary = await _remove_role_from_all_members(
        interaction.guild,
        role_name="PPE Player",
        reason="Season reset action - remove PPE Player role from everyone",
    )

    records = await load_player_records(interaction)
    records_cleared = len(records)
    await save_player_records(interaction, {})

    realmshark_settings = await get_realmshark_settings(interaction)
    links = realmshark_settings.get("links", {}) if isinstance(realmshark_settings.get("links", {}), dict) else {}
    tokens_revoked = len(links)
    realmshark_settings["links"] = {}
    await set_realmshark_settings(interaction, realmshark_settings)

    await _clear_join_embed_reactions(interaction, member_ids=summary.removed_member_ids)

    summary.records_cleared = records_cleared
    summary.tokens_revoked = tokens_revoked
    return summary


async def remove_ppe_admin_role_from_everyone(interaction: discord.Interaction) -> BulkRoleUpdateSummary:
    """Remove PPE Admin role from all members who currently have it."""
    if interaction.guild is None:
        raise ValueError("This action can only be used in a server.")

    return await _remove_role_from_all_members(
        interaction.guild,
        role_name="PPE Admin",
        reason="Season reset action - remove PPE Admin role from everyone",
    )


async def clear_join_embed_information(interaction: discord.Interaction) -> JoinEmbedResetSummary:
    """Clear join embed message references and delete the configured embed message when possible."""
    settings = await get_contest_settings(interaction)
    join_channel_id = int(settings.get("join_contest_channel_id", 0) or 0)
    join_message_id = int(settings.get("join_contest_message_id", 0) or 0)
    join_embed_was_configured = join_channel_id > 0 and join_message_id > 0

    if not join_embed_was_configured:
        return JoinEmbedResetSummary(
            join_embed_was_configured=False,
            join_embed_message_deleted=False,
        )

    result = await delete_join_contest_embed(interaction)
    return JoinEmbedResetSummary(
        join_embed_was_configured=True,
        join_embed_message_deleted=bool(result.get("deleted_message", False)),
    )


async def delete_ppe_and_team_roles(interaction: discord.Interaction) -> RoleDeleteSummary:
    """Delete PPE Admin/PPE Player roles and known team roles if they still exist."""
    if interaction.guild is None:
        raise ValueError("This action can only be used in a server.")

    guild = interaction.guild
    records = await load_player_records(interaction)
    teams = await load_teams(interaction)

    ppe_roles_deleted = 0
    ppe_roles_failed = 0
    for role_name in ("PPE Admin", "PPE Player"):
        role = discord.utils.get(guild.roles, name=role_name)
        if role is None or role.managed:
            continue

        try:
            await role.delete(reason="Season reset action - delete PPE role")
            ppe_roles_deleted += 1
        except (discord.Forbidden, discord.HTTPException):
            ppe_roles_failed += 1

    team_role_names = set(teams.keys())
    team_role_names.update(_collect_team_names_from_records(records))

    team_roles_deleted = 0
    team_roles_failed = 0
    for team_name in sorted(team_role_names):
        if not team_name or team_name in {"PPE Admin", "PPE Player"}:
            continue

        role = discord.utils.get(guild.roles, name=team_name)
        if role is None or role.managed:
            continue

        try:
            await role.delete(reason="Season reset action - delete team role")
            team_roles_deleted += 1
        except (discord.Forbidden, discord.HTTPException):
            team_roles_failed += 1

    return RoleDeleteSummary(
        ppe_roles_deleted=ppe_roles_deleted,
        ppe_roles_failed=ppe_roles_failed,
        team_roles_deleted=team_roles_deleted,
        team_roles_failed=team_roles_failed,
    )


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
    config_changed = _clear_team_quest_mode_state(config, disable_team_mode=True)

    teams = await load_teams(interaction)
    team_names = set(teams.keys())

    ppes_cleared, items_cleared, quest_entries_cleared = _reset_player_records(records, default_reset_limit)
    await save_player_records(interaction, records)
    if config_changed:
        await save_guild_config(interaction, config)

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

        season_item_history = getattr(player_data, "season_item_history", {})
        if isinstance(season_item_history, dict):
            items_cleared += _count_unique_items_from_history(season_item_history)
            season_item_history.clear()

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


async def load_bot_cost_summary_for_menu(
    interaction: discord.Interaction,
    *,
    window_hours: int = 24,
    top_n: int = 10,
) -> dict[str, Any]:
    """Load per-guild command-cost summary for /manageseason bot-cost panel."""
    if interaction.guild is None:
        raise ValueError("This action can only be used in a server.")

    guild_id = int(interaction.guild.id)
    await ensure_guild_cost_log_file(guild_id)
    summary = await summarize_guild_cost_log(guild_id, window_hours=window_hours, top_n=top_n)
    summary["log_path"] = get_guild_cost_log_path(guild_id)
    summary["cost_rate_per_gb_minute"] = get_cost_rate_per_gb_minute()
    return summary


async def clear_bot_cost_log_for_menu(interaction: discord.Interaction) -> bool:
    """Delete the guild's command-cost log file."""
    if interaction.guild is None:
        raise ValueError("This action can only be used in a server.")

    return await clear_guild_cost_log(int(interaction.guild.id))


def _format_command_cost_row(index: int, row: dict[str, Any]) -> str:
    command = str(row.get("command", "unknown"))
    calls = int(row.get("call_count", 0) or 0)
    errors = int(row.get("error_count", 0) or 0)
    total_cost = float(row.get("total_estimated_cost_usd", 0.0) or 0.0)
    cost_share = float(row.get("cost_share_percent", 0.0) or 0.0)
    cache_growth = int(row.get("total_cache_growth", 0) or 0)
    tracking_source = str(row.get("tracking_source", "unknown")).strip() or "unknown"
    return (
        f"{index}. {command} | cost=${total_cost:.6f} ({cost_share:.1f}%) | "
        f"calls={calls} | errors={errors} | cache_growth={cache_growth} | src={tracking_source}"
    )


def _format_command_cache_row(index: int, row: dict[str, Any]) -> str:
    command = str(row.get("command", "unknown"))
    calls = int(row.get("call_count", 0) or 0)
    cache_growth = int(row.get("total_cache_growth", 0) or 0)
    cache_share = float(row.get("cache_growth_share_percent", 0.0) or 0.0)
    total_cost = float(row.get("total_estimated_cost_usd", 0.0) or 0.0)
    tracking_source = str(row.get("tracking_source", "unknown")).strip() or "unknown"
    return (
        f"{index}. {command} | cache_growth={cache_growth} ({cache_share:.1f}%) | "
        f"calls={calls} | cost=${total_cost:.6f} | src={tracking_source}"
    )


def _format_command_rss_row(index: int, row: dict[str, Any]) -> str:
    command = str(row.get("command", "unknown"))
    calls = int(row.get("call_count", 0) or 0)
    rss_growth = float(row.get("total_rss_growth_mb", 0.0) or 0.0)
    rss_share = float(row.get("rss_growth_share_percent", 0.0) or 0.0)
    total_cost = float(row.get("total_estimated_cost_usd", 0.0) or 0.0)
    tracking_source = str(row.get("tracking_source", "unknown")).strip() or "unknown"
    return (
        f"{index}. {command} | rss+={rss_growth:.1f} MB ({rss_share:.1f}%) | "
        f"calls={calls} | cost=${total_cost:.6f} | src={tracking_source}"
    )


async def build_bot_cost_summary_markdown_for_menu(
    interaction: discord.Interaction,
    *,
    window_hours: int = 24,
    top_n: int = 15,
) -> str:
    """Build markdown report for per-guild command-cost analysis."""
    summary = await load_bot_cost_summary_for_menu(
        interaction,
        window_hours=window_hours,
        top_n=top_n,
    )

    guild_name = interaction.guild.name if interaction.guild is not None else "Unknown Guild"
    entry_count = int(summary.get("entry_count", 0) or 0)
    command_count = int(summary.get("command_count", 0) or 0)
    error_count = int(summary.get("error_count", 0) or 0)
    total_duration = float(summary.get("total_duration_seconds", 0.0) or 0.0)
    total_gb_minutes = float(summary.get("total_estimated_gb_minutes", 0.0) or 0.0)
    total_cost = float(summary.get("total_estimated_cost_usd", 0.0) or 0.0)
    total_rss_growth = float(summary.get("total_rss_growth_mb", 0.0) or 0.0)
    total_rss_shrink = float(summary.get("total_rss_shrink_mb", 0.0) or 0.0)
    total_cache_growth = int(summary.get("total_cache_growth", 0) or 0)
    total_cache_shrink = int(summary.get("total_cache_shrink", 0) or 0)
    cost_rate = float(summary.get("cost_rate_per_gb_minute", get_cost_rate_per_gb_minute()) or 0.0)
    log_path = str(summary.get("log_path", ""))

    lines: list[str] = [
        "# Bot Cost Summary",
        "",
        f"Guild: {guild_name} ({interaction.guild.id if interaction.guild else 'N/A'})",
        f"Window: last {int(summary.get('window_hours', window_hours) or window_hours)}h",
        f"Cost rate: ${cost_rate:.6f} per GB-minute",
        f"Log file: {log_path}",
        "",
        "## Totals",
        f"- Commands logged: {entry_count}",
        f"- Unique commands: {command_count}",
        f"- Command errors: {error_count}",
        f"- Total command runtime: {total_duration:.2f}s",
        f"- Estimated GB-minutes: {total_gb_minutes:.6f}",
        f"- Estimated cost: ${total_cost:.6f}",
        f"- RSS growth total: +{total_rss_growth:.1f} MB",
        f"- RSS shrink total: -{total_rss_shrink:.1f} MB",
        f"- Cache growth events total: +{total_cache_growth}",
        f"- Cache shrink events total: -{total_cache_shrink}",
        "",
        "## Top Commands By Estimated Cost",
    ]

    top_by_cost = summary.get("top_by_cost", []) if isinstance(summary.get("top_by_cost", []), list) else []
    if top_by_cost:
        for index, row in enumerate(top_by_cost, start=1):
            if not isinstance(row, dict):
                continue
            lines.append(_format_command_cost_row(index, row))
    else:
        lines.append("No command cost data in this window.")

    lines.extend(["", "## Top Commands By RSS Growth"])
    top_by_rss = (
        summary.get("top_by_rss_growth", [])
        if isinstance(summary.get("top_by_rss_growth", []), list)
        else []
    )
    if top_by_rss:
        for index, row in enumerate(top_by_rss, start=1):
            if not isinstance(row, dict):
                continue
            lines.append(_format_command_rss_row(index, row))
    else:
        lines.append("No RSS growth records in this window.")

    lines.extend(["", "## Top Commands By Cache Growth"])
    top_by_cache = (
        summary.get("top_by_cache_growth", [])
        if isinstance(summary.get("top_by_cache_growth", []), list)
        else []
    )
    if top_by_cache:
        for index, row in enumerate(top_by_cache, start=1):
            if not isinstance(row, dict):
                continue
            lines.append(_format_command_cache_row(index, row))
    else:
        lines.append("No cache growth data in this window.")

    return "\n".join(lines).rstrip() + "\n"

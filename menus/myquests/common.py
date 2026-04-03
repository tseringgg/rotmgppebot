"""Data loading and embed/board builders used by the /myquests menu."""

from __future__ import annotations

import glob
import csv
import os
from typing import Dict, Sequence

import discord

from utils.calc_points import normalize_item_name
from utils.gen_graphic_board.generate_board import generate_quest_board
from utils.guild_config import get_quest_points, get_quest_targets, load_guild_config
from utils.player_records import ensure_player_exists, load_player_records, save_player_records
from utils.quest_manager import refresh_player_quests


_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_DUNGEONS_DIR = os.path.join(_BASE_DIR, "dungeons")
_LOOT_CSV_PATH = os.path.join(_BASE_DIR, "rotmg_loot_drops_updated.csv")
_MISSING_IMAGE_PATH = os.path.join(_BASE_DIR, "image_missing.png")

_ITEM_IMAGE_INDEX: Dict[str, str] = {}
_ITEM_IMAGE_INDEX_READY = False
_ITEM_DUNGEON_INDEX: Dict[str, str] = {}
_ITEM_DUNGEON_INDEX_READY = False


async def send_interaction_message(
    interaction: discord.Interaction,
    *,
    content: str | None = None,
    embed: discord.Embed | None = None,
    view: discord.ui.View | None = None,
    ephemeral: bool = False,
) -> None:
    if not interaction.response.is_done():
        await interaction.response.send_message(content=content, embed=embed, view=view, ephemeral=ephemeral)
        return

    await interaction.followup.send(content=content, embed=embed, view=view, ephemeral=ephemeral)


def strip_shiny_suffix(item_name: str) -> str:
    normalized = normalize_item_name(item_name)
    if normalized.lower().endswith("(shiny)"):
        return normalized[: -len("(shiny)")].strip()
    return normalized


def build_item_image_index_if_needed() -> None:
    global _ITEM_IMAGE_INDEX_READY
    if _ITEM_IMAGE_INDEX_READY:
        return

    _ITEM_IMAGE_INDEX.clear()
    # Build once and cache by normalized item name for faster board rendering.
    for png_file in glob.glob(os.path.join(_DUNGEONS_DIR, "**", "*.png"), recursive=True):
        base_name = os.path.splitext(os.path.basename(png_file))[0]
        normalized = normalize_item_name(base_name).lower()
        if normalized and normalized not in _ITEM_IMAGE_INDEX:
            _ITEM_IMAGE_INDEX[normalized] = png_file

    _ITEM_IMAGE_INDEX_READY = True


def resolve_item_image_path(item_name: str) -> str | None:
    """Resolve best-fit item icon path, including shiny/base fallback matching."""

    build_item_image_index_if_needed()

    full_name = normalize_item_name(item_name)
    base_name = strip_shiny_suffix(item_name)

    candidates = [full_name, base_name]
    if not full_name.lower().endswith("(shiny)"):
        candidates.append(f"{base_name} (shiny)")

    for candidate in candidates:
        key = normalize_item_name(candidate).lower()
        path = _ITEM_IMAGE_INDEX.get(key)
        if path:
            return path

    return _MISSING_IMAGE_PATH if os.path.exists(_MISSING_IMAGE_PATH) else None


def build_dungeon_lookup_if_needed() -> None:
    """Build a normalized item->dungeon cache from rotmg_loot_drops_updated.csv once."""

    global _ITEM_DUNGEON_INDEX_READY
    if _ITEM_DUNGEON_INDEX_READY:
        return

    _ITEM_DUNGEON_INDEX.clear()
    try:
        with open(_LOOT_CSV_PATH, "r", encoding="utf-8", newline="") as file_handle:
            reader = csv.DictReader(file_handle)
            for row in reader:
                item_name = normalize_item_name(str(row.get("Item Name", "")).strip())
                dungeon_name = str(row.get("Dungeon", "")).strip()
                if not item_name or not dungeon_name:
                    continue

                full_norm = normalize_item_name(item_name).lower()
                base_norm = normalize_item_name(strip_shiny_suffix(item_name)).lower()
                if full_norm and full_norm not in _ITEM_DUNGEON_INDEX:
                    _ITEM_DUNGEON_INDEX[full_norm] = dungeon_name
                if base_norm and base_norm not in _ITEM_DUNGEON_INDEX:
                    _ITEM_DUNGEON_INDEX[base_norm] = dungeon_name
    except OSError:
        _ITEM_DUNGEON_INDEX_READY = True
        return

    _ITEM_DUNGEON_INDEX_READY = True


def dungeon_for_item(item_name: str) -> str:
    build_dungeon_lookup_if_needed()
    full_norm = normalize_item_name(item_name).lower()
    base_norm = normalize_item_name(strip_shiny_suffix(item_name)).lower()
    return _ITEM_DUNGEON_INDEX.get(full_norm) or _ITEM_DUNGEON_INDEX.get(base_norm) or "Dungeon unknown"


def coerce_resets_remaining(player_data, default_reset_limit: int) -> int:
    """Normalize persisted reset counters and recover from invalid legacy values."""

    value = player_data.quest_resets_remaining
    if value is None:
        return max(0, default_reset_limit)
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return max(0, default_reset_limit)


def board_file(item_names: Sequence[str], title: str, filename: str) -> discord.File:
    """Render a quest board image and return it as a Discord file attachment."""

    buffer = generate_quest_board(
        item_names,
        resolve_item_image_path,
        title=title,
        missing_image_path=_MISSING_IMAGE_PATH if os.path.exists(_MISSING_IMAGE_PATH) else None,
        columns=None,
        icon_size=34,
    )
    return discord.File(buffer, filename=filename)


def build_quest_lines(item_names: Sequence[str]) -> str:
    if not item_names:
        return "• None"
    return "\n".join(f"• {item_name} - {dungeon_for_item(item_name)}" for item_name in item_names)


def build_home_embed(
    display_name: str,
    quests,
    resets_remaining: int,
    reset_limit: int,
    points_regular: int,
    points_shiny: int,
    points_skin: int,
    target_regular: int,
    target_shiny: int,
    target_skin: int,
    global_mode_enabled: bool,
) -> discord.Embed:
    completed_regular = len(quests.completed_items)
    completed_shiny = len(quests.completed_shinies)
    completed_skin = len(quests.completed_skins)

    active_regular = len(quests.current_items)
    active_shiny = len(quests.current_shinies)
    active_skin = len(quests.current_skins)

    total_completed = completed_regular + completed_shiny + completed_skin
    total_points = (
        (completed_regular * points_regular)
        + (completed_shiny * points_shiny)
        + (completed_skin * points_skin)
    )

    embed = discord.Embed(
        title=f"My Quests - {display_name}",
        description=(
            (
                "Global quest mode is active. Your quest list is shared server-wide and shrinks as quests are completed.\n"
                if global_mode_enabled
                else f"Resets remaining: **{resets_remaining}/{reset_limit}**\n"
            )
            + (
                "Use the menu below to view quest boards and completed quests."
                if global_mode_enabled
                else "Use the menu below to view quest boards, completed quests, or reset any number of your quests."
            )
        ),
        color=discord.Color.from_rgb(54, 57, 63),
    )
    embed.add_field(
        name="Quest Progress",
        value=(
            f"Active: **{active_regular}** Regular, **{active_shiny}** Shiny, **{active_skin}** Skin\n"
            + (
                "Targets: **Global List**\n"
                if global_mode_enabled
                else f"Targets: **{target_regular}** Regular, **{target_shiny}** Shiny, **{target_skin}** Skin\n"
            )
            +
            f"Completed: **{total_completed}** total"
        ),
        inline=False,
    )
    embed.add_field(
        name="Points",
        value=(
            f"Regular: **{points_regular}** each\n"
            f"Shiny: **{points_shiny}** each\n"
            f"Skin: **{points_skin}** each\n"
            f"Completed quest points: **{total_points}**"
        ),
        inline=False,
    )
    embed.set_footer(text="Boards render only when selected to keep this panel clean.")
    return embed


def build_category_embed(title: str, item_names: Sequence[str], attachment_name: str) -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=build_quest_lines(item_names),
        color=discord.Color.from_rgb(88, 101, 242),
    )
    embed.set_image(url=f"attachment://{attachment_name}")
    return embed


def build_completed_embed(quests, points_regular: int, points_shiny: int, points_skin: int) -> discord.Embed:
    lines = ["**Completed Quests**", ""]

    total_points = 0
    if quests.completed_items:
        lines.append("Regular:")
        for item_name in quests.completed_items:
            total_points += points_regular
            lines.append(f"• {item_name}: +{points_regular} pts")
        lines.append("")

    if quests.completed_shinies:
        lines.append("Shiny:")
        for item_name in quests.completed_shinies:
            total_points += points_shiny
            lines.append(f"• {item_name}: +{points_shiny} pts")
        lines.append("")

    if quests.completed_skins:
        lines.append("Skins:")
        for item_name in quests.completed_skins:
            total_points += points_skin
            lines.append(f"• {item_name}: +{points_skin} pts")
        lines.append("")

    if total_points == 0:
        lines = ["• No completed quests yet."]

    description = "\n".join(lines)
    if len(description) > 3900:
        description = description[:3850].rstrip() + "\n... (truncated)"

    embed = discord.Embed(
        title="Completed Quest Log",
        description=description,
        color=discord.Color.green(),
    )
    embed.add_field(name="Total Completed Quest Points", value=f"**{total_points}**", inline=False)
    return embed


async def build_myquests_state_for_player(
    interaction: discord.Interaction,
    *,
    player_id: int,
    display_name: str,
    not_in_contest_message: str,
) -> dict:
    """Assemble all embeds and quest lists needed to render a quests menu for one player."""

    records = await load_player_records(interaction)
    key = ensure_player_exists(records, player_id)

    if key not in records or not records[key].is_member:
        raise KeyError(not_in_contest_message)

    player_data = records[key]
    config = await load_guild_config(interaction)
    default_reset_limit = int(config["quest_settings"]["num_resets"])
    resets_remaining = coerce_resets_remaining(player_data, default_reset_limit)

    regular_target, shiny_target, skin_target = await get_quest_targets(interaction)
    regular_points, shiny_points, skin_points = await get_quest_points(interaction)

    changed = refresh_player_quests(
        player_data,
        target_item_quests=regular_target,
        target_shiny_quests=shiny_target,
        target_skin_quests=skin_target,
        global_quests={
            "enabled": bool(config["quest_settings"].get("use_global_quests", False)),
            "regular": list(config["quest_settings"].get("global_regular_quests", [])),
            "shiny": list(config["quest_settings"].get("global_shiny_quests", [])),
            "skin": list(config["quest_settings"].get("global_skin_quests", [])),
        },
    )

    if player_data.quest_resets_remaining != resets_remaining:
        player_data.quest_resets_remaining = resets_remaining
        changed = True

    if changed:
        await save_player_records(interaction, records)

    quests = player_data.quests
    current_regular = list(quests.current_items)
    current_shiny = list(quests.current_shinies)
    current_skin = list(quests.current_skins)

    return {
        "user_id": int(player_id),
        "display_name": display_name,
        "home_embed": build_home_embed(
            display_name,
            quests,
            resets_remaining,
            default_reset_limit,
            regular_points,
            shiny_points,
            skin_points,
            regular_target,
            shiny_target,
            skin_target,
            bool(config["quest_settings"].get("use_global_quests", False)),
        ),
        "completed_embed": build_completed_embed(quests, regular_points, shiny_points, skin_points),
        "current_regular": current_regular,
        "current_shiny": current_shiny,
        "current_skin": current_skin,
        "current_all": current_regular + current_shiny + current_skin,
        "global_mode_enabled": bool(config["quest_settings"].get("use_global_quests", False)),
    }


async def build_myquests_state(interaction: discord.Interaction):
    """Assemble all embeds and item lists required to render the quests view for the invoking player."""

    return await build_myquests_state_for_player(
        interaction,
        player_id=interaction.user.id,
        display_name=interaction.user.display_name,
        not_in_contest_message="❌ You're not part of the PPE contest.",
    )

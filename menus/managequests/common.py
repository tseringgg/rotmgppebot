"""Shared embed/state helpers for the /managequests admin menu."""

from __future__ import annotations

import discord

from utils.guild_config import load_guild_config


def build_global_payload(settings: dict) -> dict:
    """Create the quest-manager payload structure expected by refresh_player_quests."""
    return {
        "enabled": bool(settings.get("use_global_quests", False)),
        "regular": list(settings.get("global_regular_quests", [])),
        "shiny": list(settings.get("global_shiny_quests", [])),
        "skin": list(settings.get("global_skin_quests", [])),
    }


def coerce_non_negative_int(raw_value: str, field_name: str) -> int:
    try:
        value = int(str(raw_value).strip())
    except (TypeError, ValueError):
        raise ValueError(f"❌ `{field_name}` must be a whole number.")
    if value < 0:
        raise ValueError(f"❌ `{field_name}` must be 0 or greater.")
    return value


def dedupe_items(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        text = str(item).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        output.append(text)
    return output


async def load_managequests_settings(interaction: discord.Interaction) -> dict:
    config = await load_guild_config(interaction)
    return dict(config["quest_settings"])


def build_managequests_home_embed(settings: dict) -> discord.Embed:
    global_enabled = bool(settings.get("use_global_quests", False))
    regular_global = len(settings.get("global_regular_quests", []))
    shiny_global = len(settings.get("global_shiny_quests", []))
    skin_global = len(settings.get("global_skin_quests", []))

    embed = discord.Embed(
        title="Manage Quests",
        description="Admin quest controls for this server.",
        color=discord.Color.blurple(),
    )
    embed.add_field(
        name="Quest Generation",
        value=(
            f"Regular target: **{settings['regular_target']}**\n"
            f"Shiny target: **{settings['shiny_target']}**\n"
            f"Skin target: **{settings['skin_target']}**\n"
            f"Resets per player: **{settings['num_resets']}**"
        ),
        inline=True,
    )
    embed.add_field(
        name="Quest Points",
        value=(
            f"Regular: **{settings['regular_points']}**\n"
            f"Shiny: **{settings['shiny_points']}**\n"
            f"Skin: **{settings['skin_points']}**"
        ),
        inline=True,
    )
    embed.add_field(
        name="Global Quests",
        value=(
            f"Enabled: **{'Yes' if global_enabled else 'No'}**\n"
            f"Regular pool: **{regular_global}**\n"
            f"Shiny pool: **{shiny_global}**\n"
            f"Skin pool: **{skin_global}**"
        ),
        inline=False,
    )
    embed.add_field(
        name="Reset All Quests",
        value=(
            "Clears all current and completed quests for every player, "
            "then resets each player's reset-attempt counter to the configured default."
        ),
        inline=False,
    )
    embed.set_footer(
        text="Use Edit Quest Settings to update targets/points, Set Global Quests to enforce shared quests, or Manage Player's Quests for targeted actions."
    )
    return embed


def build_global_quests_embed(settings: dict) -> discord.Embed:
    enabled = bool(settings.get("use_global_quests", False))
    if not enabled:
        return discord.Embed(
            title="Set Global Quests",
            description=(
                "Global quests are currently **disabled**.\n"
                "Enable this mode to force one shared quest list for everyone."
            ),
            color=discord.Color.orange(),
        )

    regular = list(settings.get("global_regular_quests", []))
    shiny = list(settings.get("global_shiny_quests", []))
    skin = list(settings.get("global_skin_quests", []))

    def format_list(items: list[str]) -> str:
        if not items:
            return "• None"
        text = "\n".join(f"• {item}" for item in items)
        if len(text) > 1024:
            text = text[:1000].rstrip() + "\n..."
        return text

    embed = discord.Embed(
        title="Set Global Quests",
        description=(
            "Global quests are **enabled**.\n"
            "Use item names exactly as they appear in **rotmg_loot_drops_updated.csv**.\n"
            "Completing a quest removes it from your active list and does not auto-generate replacements."
        ),
        color=discord.Color.green(),
    )
    embed.add_field(name="Regular Global Quests", value=format_list(regular), inline=False)
    embed.add_field(name="Shiny Global Quests", value=format_list(shiny), inline=False)
    embed.add_field(name="Skin Global Quests", value=format_list(skin), inline=False)
    return embed


def build_reset_active_lines(
    active_item_quests: list[str],
    active_shiny_quests: list[str],
    active_skin_quests: list[str],
) -> list[str]:
    lines: list[str] = []
    for item in active_item_quests:
        lines.append(f"- Item: {item}")
    for shiny in active_shiny_quests:
        lines.append(f"- Shiny: {shiny}")
    for skin in active_skin_quests:
        lines.append(f"- Skin: {skin}")
    return lines or ["- None"]


def build_reset_completion_lines(
    *,
    member_display_name: str,
    summary: dict,
    default_reset_limit: int,
    consume_reset_on_confirm: bool,
) -> list[str]:
    lines = [f"✅ Updated quest reset for {member_display_name}."]
    if summary["removed_current_items"]:
        lines.append(f"- Active item quests reset: {', '.join(summary['removed_current_items'])}")
    if summary["removed_current_shinies"]:
        lines.append(f"- Active shiny quests reset: {', '.join(summary['removed_current_shinies'])}")
    if summary["removed_current_skins"]:
        lines.append(f"- Active skin quests reset: {', '.join(summary['removed_current_skins'])}")
    if summary["reset_completed_items"]:
        lines.append("- Reset all completed item quests")
    if summary["reset_completed_shinies"]:
        lines.append("- Reset all completed shiny quests")
    if summary["reset_completed_skins"]:
        lines.append("- Reset all completed skin quests")
    if summary["cleared_all_info"]:
        lines.append("- Cleared all quest information")
    if summary["reset_counter_to_default"]:
        lines.append(f"- Reset quest reset attempts to default ({default_reset_limit})")

    lines.append(f"- Quest resets remaining: {summary['quest_resets_remaining']}")
    footer_line = (
        "Use /myquests to verify the updated quest state."
        if consume_reset_on_confirm
        else "Use /manageplayer or /managequests to view the updated quest state."
    )
    lines.append(footer_line)
    return lines

"""Shared embed and formatting helpers for /manageseason views."""

from __future__ import annotations

import discord

from menus.manageseason.services import SeasonResetSummary


def _format_percent(value: float) -> str:
    return f"{float(value):.2f}%"


def _format_minimum_total(value: float | None) -> str:
    return "none" if value is None else f"{float(value):.2f}"


def build_manageseason_home_embed() -> discord.Embed:
    """Build the top-level /manageseason embed with action guidance."""
    embed = discord.Embed(
        title="Manage Season",
        description=(
            "Admin controls for season lifecycle actions and point modifier configuration.\n"
            "Use the buttons below to choose a workflow."
        ),
        color=discord.Color.blurple(),
    )
    embed.add_field(
        name="Reset Season",
        value=(
            "Clears all PPE characters, season uniques, quest progress, and teams.\n"
            "This action requires **Discord Administrator** permission and always asks for confirmation."
        ),
        inline=False,
    )
    embed.add_field(
        name="Manage Point Settings",
        value=(
            "Open the interactive point-settings panel to view and update:\n"
            "- Global loot/bonus/penalty/total modifiers\n"
            "- Class-specific modifier overrides"
        ),
        inline=False,
    )
    embed.set_footer(text="This menu is owner-bound: only the admin who opened it can use the controls.")
    return embed


def build_reset_mode_embed() -> discord.Embed:
    """Build the mode-selection embed for reset actions."""
    embed = discord.Embed(
        title="Reset Season",
        description=(
            "Choose how RealmShark links should be handled during the reset.\n"
            "Both options clear PPE/season/quest/team data."
        ),
        color=discord.Color.orange(),
    )
    embed.add_field(
        name="Keep RealmShark Links",
        value=(
            "Preserves linked tokens and converts active PPE mappings into seasonal mappings\n"
            "so linked users can continue ingesting into season loot after reset."
        ),
        inline=False,
    )
    embed.add_field(
        name="Unlink RealmShark Links",
        value=(
            "Fully resets sniffer integrations: disables sniffer, revokes all link tokens, and clears mappings."
        ),
        inline=False,
    )
    embed.set_footer(text="You will be asked to confirm before any reset is executed.")
    return embed


def build_point_settings_embed(settings: dict) -> discord.Embed:
    """Build the point-settings summary embed for the management subview."""
    global_settings = settings.get("global", {}) if isinstance(settings.get("global"), dict) else {}
    class_overrides = settings.get("class_overrides", {}) if isinstance(settings.get("class_overrides"), dict) else {}

    embed = discord.Embed(
        title="Manage Point Settings",
        description=(
            "Use this panel to control percent-based point modifiers for this guild.\n"
            "Updates are saved immediately to guild config."
        ),
        color=discord.Color.dark_teal(),
    )

    embed.add_field(
        name="Global Modifiers",
        value=(
            f"Loot: **{_format_percent(global_settings.get('loot_percent', 0.0))}**\n"
            f"Bonus: **{_format_percent(global_settings.get('bonus_percent', 0.0))}**\n"
            f"Penalty: **{_format_percent(global_settings.get('penalty_percent', 0.0))}**\n"
            f"Total: **{_format_percent(global_settings.get('total_percent', 0.0))}**"
        ),
        inline=False,
    )

    if class_overrides:
        lines: list[str] = []
        for class_name in sorted(class_overrides.keys()):
            override = class_overrides[class_name]
            if not isinstance(override, dict):
                continue
            lines.append(
                f"- **{class_name}**: loot {_format_percent(override.get('loot_percent', 0.0))}, "
                f"bonus {_format_percent(override.get('bonus_percent', 0.0))}, "
                f"penalty {_format_percent(override.get('penalty_percent', 0.0))}, "
                f"total {_format_percent(override.get('total_percent', 0.0))}, "
                f"minimum_total {_format_minimum_total(override.get('minimum_total'))}"
            )

        text = "\n".join(lines) if lines else "No class overrides configured."
        if len(text) > 1024:
            text = text[:1000].rstrip() + "\n..."
    else:
        text = "No class overrides configured."

    embed.add_field(name="Class Overrides", value=text, inline=False)
    embed.add_field(
        name="How This Works",
        value=(
            "Global modifiers apply to all classes by default.\n"
            "A class override replaces the global values for that class only."
        ),
        inline=False,
    )
    embed.set_footer(text="Use Edit Global Modifiers or Edit Class Override to apply changes.")
    return embed


def build_reset_completion_embed(summary: SeasonResetSummary, *, actor_name: str) -> discord.Embed:
    """Build a public summary embed after a reset is completed."""
    embed = discord.Embed(
        title="Season Reset Complete",
        description=f"Triggered by **{actor_name}**.",
        color=discord.Color.red(),
    )
    embed.add_field(
        name="Cleared Player Data",
        value=(
            f"PPE characters: **{summary.ppes_cleared}**\n"
            f"Season unique items: **{summary.items_cleared}**\n"
            f"Quest entries: **{summary.quest_entries_cleared}**"
        ),
        inline=True,
    )
    embed.add_field(
        name="Cleared Team Data",
        value=(
            f"Teams deleted: **{summary.teams_deleted}**\n"
            f"Team roles deleted: **{summary.team_roles_deleted}**"
        ),
        inline=True,
    )
    embed.add_field(
        name="Quest Reset Limit",
        value=f"Per-player reset attempts restored to **{summary.default_reset_limit}**.",
        inline=False,
    )

    if summary.clear_realmshark_links:
        realmshark_value = (
            f"Links revoked: **{summary.realmshark_links_before}**\n"
            f"Pending files removed: **{summary.pending_files_cleared}**\n"
            "Sniffer state reset to disabled/default mode."
        )
    else:
        realmshark_value = (
            f"Links preserved: **{summary.realmshark_links_before}**\n"
            f"PPE mappings converted to seasonal: **{summary.converted_bindings}**\n"
            f"Tokens updated: **{summary.tokens_updated}**\n"
            f"Pending files removed: **{summary.pending_files_cleared}**"
        )

    embed.add_field(name="RealmShark Result", value=realmshark_value, inline=False)
    embed.set_footer(text="Player membership status and PPE roles were preserved.")
    return embed

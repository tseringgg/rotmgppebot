"""Shared embed and formatting helpers for /manageseason views."""

from __future__ import annotations

import discord

from menus.manageseason.services import SeasonResetSummary
from utils.ppe_types import all_ppe_types, ppe_type_label
from utils.contest_leaderboards import CONTEST_LEADERBOARD_OPTIONS, contest_leaderboard_label


def _format_percent(value: float) -> str:
    return f"{float(value):.2f}%"


def _format_minimum_total(value: float | None) -> str:
    return "none" if value is None else f"{float(value):.2f}"


def _truncate_field_value(text: str, *, max_chars: int = 1024) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 4].rstrip() + "\n..."


def _build_class_override_lines(class_overrides: dict) -> list[str]:
    lines: list[str] = []
    for class_name in sorted(class_overrides.keys()):
        override = class_overrides[class_name]
        if not isinstance(override, dict):
            continue
        lines.append(
            f"• **{class_name}**: loot {_format_percent(override.get('loot_percent', 0.0))}, "
            f"bonus {_format_percent(override.get('bonus_percent', 0.0))}, "
            f"penalty {_format_percent(override.get('penalty_percent', 0.0))}, "
            f"total {_format_percent(override.get('total_percent', 0.0))}, "
            f"minimum {_format_minimum_total(override.get('minimum_total'))}"
        )
    return lines


def _build_ppe_type_multiplier_lines(multipliers: dict) -> list[str]:
    lines: list[str] = []
    for ppe_type in all_ppe_types():
        value = 1.0
        try:
            value = float(multipliers.get(ppe_type, 1.0))
        except (TypeError, ValueError):
            value = 1.0
        lines.append(f"• {ppe_type_label(ppe_type)}: {value:.2f}x")
    return lines


def build_manageseason_home_embed() -> discord.Embed:
    """Build the top-level /manageseason embed with action guidance."""
    embed = discord.Embed(
        title="Manage Season",
        description=(
            "Admin controls for season lifecycle actions, contest behavior, point modifiers, and picture suggestions.\n"
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
            "Open point modifier menus to review and edit global or class-specific percentage modifiers."
        ),
        inline=False,
    )
    embed.add_field(
        name="Manage Contests",
        value=(
            "Set the default `/leaderboard` contest board, configure team leaderboard scoring, and manage the join-role embed."
        ),
        inline=False,
    )
    embed.add_field(
        name="Character Settings",
        value=(
            "Adjust server-wide character limits and prune excess characters when reducing the cap."
        ),
        inline=False,
    )
    embed.add_field(
        name="Picture Suggestions",
        value=(
            "Configure channels that accept hovered-item screenshots for item suggestion matching."
        ),
        inline=False,
    )
    embed.set_footer(text="This menu is owner-bound: only the admin who opened it can use the controls.")
    return embed


def build_manage_contests_embed(settings: dict) -> discord.Embed:
    """Build the Manage Contests home embed."""
    default_choice = settings.get("default_contest_leaderboard")
    default_label = contest_leaderboard_label(default_choice)
    team_quest_enabled = bool(settings.get("team_contest_include_quest_points", False))
    join_channel_id = int(settings.get("join_contest_channel_id", 0) or 0)
    join_message_id = int(settings.get("join_contest_message_id", 0) or 0)
    if join_channel_id > 0 and join_message_id > 0:
        join_embed_status = (
            f"Configured in <#{join_channel_id}>\n"
            f"Message ID: `{join_message_id}`"
        )
    else:
        join_embed_status = "Not configured."

    embed = discord.Embed(
        title="Manage Contests",
        description="Configure contest leaderboard defaults and team leaderboard scoring rules.",
        color=discord.Color.dark_magenta(),
    )
    embed.add_field(
        name="Set Contest Type",
        value=(
            "Choose the default board used by **Contest Leaderboard** in `/leaderboard`.\n"
            f"Current default: **{default_label}**"
        ),
        inline=False,
    )
    embed.add_field(
        name="Manage Leaderboards",
        value=(
            "Open contest leaderboard scoring controls.\n"
            f"Team contest quest scoring: **{'Enabled' if team_quest_enabled else 'Disabled'}**"
        ),
        inline=False,
    )
    embed.add_field(
        name="Join Contest Embed",
        value=(
            "Create or delete the single allowed join-role embed for PPE Player onboarding.\n"
            f"Current status:\n{join_embed_status}"
        ),
        inline=False,
    )
    embed.set_footer(text="Quest scoring is disabled by default for team contests.")
    return embed


def build_character_settings_home_embed(
    *,
    current_max_characters: int,
    ppe_types_enabled: bool,
    allowed_ppe_types: list[str],
) -> discord.Embed:
    """Build character settings embed for /manageseason character controls."""
    embed = discord.Embed(
        title="Character Settings",
        description="Manage server-wide character capacity settings.",
        color=discord.Color.dark_gold(),
    )
    embed.add_field(
        name="Change Max Characters",
        value=(
            f"Current max characters per player: **{current_max_characters}**\n"
            "If reduced, excess characters are removed starting from the lowest-point inactive characters."
        ),
        inline=False,
    )
    embed.add_field(
        name="PPE Type Controls",
        value=(
            f"Type selection: **{'Enabled' if ppe_types_enabled else 'Disabled'}**\n"
            f"Allowed types ({len(allowed_ppe_types)}): "
            + ", ".join(ppe_type_label(ppe_type) for ppe_type in allowed_ppe_types)
        ),
        inline=False,
    )
    return embed


def build_set_contest_type_embed(settings: dict) -> discord.Embed:
    """Build the contest-type selection embed."""
    default_choice = settings.get("default_contest_leaderboard")
    default_label = contest_leaderboard_label(default_choice)
    option_lines = [f"• {label}" for _key, label in CONTEST_LEADERBOARD_OPTIONS]

    embed = discord.Embed(
        title="Set Contest Type",
        description=(
            "Pick the default leaderboard used by the **Contest Leaderboard** button in `/leaderboard`."
        ),
        color=discord.Color.dark_magenta(),
    )
    embed.add_field(name="Current Default", value=f"**{default_label}**", inline=False)
    embed.add_field(
        name="Available Contest Leaderboards",
        value="\n".join(option_lines),
        inline=False,
    )
    embed.add_field(
        name="Clear Default",
        value="Use **Clear Default** to require manual setup before Contest Leaderboard can be used.",
        inline=False,
    )
    return embed


def build_leaderboard_manager_embed(settings: dict) -> discord.Embed:
    """Build the leaderboard manager embed."""
    team_quest_enabled = bool(settings.get("team_contest_include_quest_points", False))
    status_text = "Enabled" if team_quest_enabled else "Disabled"

    embed = discord.Embed(
        title="Leaderboard Manager",
        description="Configure how points are calculated for team contests.",
        color=discord.Color.dark_magenta(),
    )
    embed.add_field(
        name="Team Contest Quest Scoring",
        value=(
            f"Current status: **{status_text}**\n"
            "When enabled, completed quests add points to team totals.\n"
            "When disabled, team totals use PPE points only."
        ),
        inline=False,
    )
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
    """Build the point-settings landing embed."""
    global_settings = settings.get("global", {}) if isinstance(settings.get("global"), dict) else {}
    class_overrides = settings.get("class_overrides", {}) if isinstance(settings.get("class_overrides"), dict) else {}

    embed = discord.Embed(
        title="Manage Point Settings",
        description=(
            "Choose which modifier group to manage.\n"
            "Each submenu explains exactly how modifiers affect final points."
        ),
        color=discord.Color.dark_teal(),
    )
    embed.add_field(
        name="Global Snapshot",
        value=(
            f"Loot: **{_format_percent(global_settings.get('loot_percent', 0.0))}**\n"
            f"Bonus: **{_format_percent(global_settings.get('bonus_percent', 0.0))}**\n"
            f"Penalty: **{_format_percent(global_settings.get('penalty_percent', 0.0))}**\n"
            f"Total: **{_format_percent(global_settings.get('total_percent', 0.0))}**"
        ),
        inline=False,
    )
    override_lines = _build_class_override_lines(class_overrides)
    preview = "No class overrides configured."
    if override_lines:
        preview = "\n".join(override_lines[:6])
        if len(override_lines) > 6:
            preview += f"\n... and {len(override_lines) - 6} more"
    embed.add_field(name="Class Override Snapshot", value=_truncate_field_value(preview), inline=False)
    embed.add_field(
        name="PPE Type Multipliers",
        value="Use **Edit PPE Type Points** to manage per-type point multipliers.",
        inline=False,
    )
    embed.set_footer(text="Use Edit Global Modifiers or Edit Class Modifiers to continue.")
    return embed


def build_ppe_type_points_embed(character_settings: dict) -> discord.Embed:
    multipliers = (
        character_settings.get("ppe_type_multipliers", {})
        if isinstance(character_settings.get("ppe_type_multipliers"), dict)
        else {}
    )
    lines = _build_ppe_type_multiplier_lines(multipliers)
    embed = discord.Embed(
        title="PPE Type Point Multipliers",
        description="Edit how much each PPE type scales final points.",
        color=discord.Color.dark_teal(),
    )
    embed.add_field(name="Current Multipliers", value="\n".join(lines), inline=False)
    embed.set_footer(text="Changing multipliers recalculates all character totals immediately.")
    return embed


def build_global_modifier_settings_embed(settings: dict) -> discord.Embed:
    """Build the global modifier management embed with behavior details."""
    global_settings = settings.get("global", {}) if isinstance(settings.get("global"), dict) else {}

    embed = discord.Embed(
        title="Global Point Modifiers",
        description="Global modifiers apply to every class unless a class override replaces them.",
        color=discord.Color.dark_teal(),
    )
    embed.add_field(
        name="Current Global Values",
        value=(
            f"Loot Percent: **{_format_percent(global_settings.get('loot_percent', 0.0))}**\n"
            f"Bonus Percent: **{_format_percent(global_settings.get('bonus_percent', 0.0))}**\n"
            f"Penalty Percent: **{_format_percent(global_settings.get('penalty_percent', 0.0))}**\n"
            f"Total Percent: **{_format_percent(global_settings.get('total_percent', 0.0))}**"
        ),
        inline=False,
    )
    embed.add_field(
        name="What Each Modifier Does",
        value=(
            "• Loot Percent scales loot points subtotal.\n"
            "Example: `40 loot` with `+10%` becomes `44`.\n"
            "• Bonus Percent scales bonus points subtotal.\n"
            "Example: `12 bonus` with `-25%` becomes `9`.\n"
            "• Penalty Percent scales penalty subtotal before subtracting.\n"
            "Example: `8 penalty` with `+50%` becomes `12`.\n"
            "• Total Percent scales the final result after loot/bonus/penalty.\n"
            "Example: `80 total` with `+5%` becomes `84`."
        ),
        inline=False,
    )
    embed.set_footer(text="Use Edit Global Modifiers to update values immediately.")
    return embed


def build_class_modifier_settings_embed(settings: dict, *, selected_class: str | None) -> discord.Embed:
    """Build the class modifier management embed with behavior details."""
    class_overrides = settings.get("class_overrides", {}) if isinstance(settings.get("class_overrides"), dict) else {}
    selected_override = class_overrides.get(selected_class or "", {})
    selected_override = selected_override if isinstance(selected_override, dict) else {}

    embed = discord.Embed(
        title="Class Point Modifiers",
        description=(
            "Class modifiers replace global modifiers for one class only.\n"
            "Select a class below, then edit its modifier profile."
        ),
        color=discord.Color.dark_teal(),
    )

    if selected_class is None:
        current_selection = "No class selected yet."
    elif selected_override:
        current_selection = (
            f"**{selected_class}**\n"
            f"Loot: {_format_percent(selected_override.get('loot_percent', 0.0))}\n"
            f"Bonus: {_format_percent(selected_override.get('bonus_percent', 0.0))}\n"
            f"Penalty: {_format_percent(selected_override.get('penalty_percent', 0.0))}\n"
            f"Total: {_format_percent(selected_override.get('total_percent', 0.0))}\n"
            f"Minimum Total: {_format_minimum_total(selected_override.get('minimum_total'))}"
        )
    else:
        current_selection = (
            f"**{selected_class}**\n"
            "No override exists yet. Editing this class will create one."
        )

    embed.add_field(name="Current Selection", value=current_selection, inline=False)

    override_lines = _build_class_override_lines(class_overrides)
    override_text = "No class overrides configured."
    if override_lines:
        override_text = "\n".join(override_lines[:8])
        if len(override_lines) > 8:
            override_text += f"\n... and {len(override_lines) - 8} more"
    embed.add_field(name="Configured Class Overrides", value=_truncate_field_value(override_text), inline=False)
    embed.add_field(
        name="How Class Modifiers Work",
        value=(
            "• Override values replace global values for the selected class only.\n"
            "• `minimum_total` sets a final floor after all calculations.\n"
            "Example: if final points calculate to `27.5` and minimum is `35`, final becomes `35`.\n"
            "• Leave minimum as `none` to remove the floor."
        ),
        inline=False,
    )
    embed.set_footer(text="Use Edit Selected Class to update this class profile.")
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

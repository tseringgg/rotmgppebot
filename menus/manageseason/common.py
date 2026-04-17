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


def _build_starting_penalty_modifier_lines(modifiers: dict) -> list[str]:
    return [
        f"• Pet Level Reduction Rate: {_format_percent(modifiers.get('pet_level_percent_reduction', 0.0))} per level",
        f"• Exalts Reduction Rate: {_format_percent(modifiers.get('exalts_percent_reduction', 0.0))} per exalt",
        f"• Loot Boost Reduction Rate: {_format_percent(modifiers.get('loot_percent_reduction', 0.0))} per 1% boost",
        f"• In-Combat Reduction Rate: {_format_percent(modifiers.get('incombat_percent_reduction', 0.0))} per 1.0s",
    ]


def _build_rarity_multiplier_lines(rarity_multipliers: dict) -> list[str]:
    lines: list[str] = []
    for rarity in ("common", "uncommon", "rare", "legendary", "divine", "shiny"):
        value = 1.0
        default = 2.0 if rarity in {"divine", "shiny"} else 1.0
        try:
            value = float(rarity_multipliers.get(rarity, default))
        except (TypeError, ValueError):
            value = default
        lines.append(f"• {rarity.title()}: **{value:.2f}x**")
    return lines


def _duplicate_mode_label(mode: str) -> str:
    normalized = str(mode or "").strip().lower()
    mapping = {
        "separate_rarity": "Different rarities are separate",
        "any_rarity": "Any rarity of same item is duplicate",
        "non_divine_any_rarity": "Divines are exempt; others group",
        "all_including_shiny": "All variants including shinies group",
    }
    return mapping.get(normalized, mapping["separate_rarity"])


def _duplicate_mode_description_lines(mode: str) -> list[str]:
    normalized = str(mode or "").strip().lower()
    if normalized == "any_rarity":
        return [
            "• Same item + shiny state counts as one duplicate bucket.",
            "• Different rarities are treated as duplicate copies.",
        ]
    if normalized == "non_divine_any_rarity":
        return [
            "• Divine drops never lose points to duplicate reduction.",
            "• Non-divine rarities of the same item + shiny state share one bucket.",
        ]
    if normalized == "all_including_shiny":
        return [
            "• Same item name always shares one duplicate bucket.",
            "• Rarity and shiny are ignored for duplicate matching.",
        ]
    return [
        "• Current default behavior.",
        "• Duplicate matching requires same item + rarity + shiny state.",
    ]


def build_manage_duplicate_items_embed(settings: dict) -> discord.Embed:
    """Build duplicate-settings overview embed."""
    try:
        duplicate_reduction = float(settings.get("duplicate_point_reduction", 0.5))
    except (TypeError, ValueError):
        duplicate_reduction = 0.5
    if duplicate_reduction < 0:
        duplicate_reduction = 0.5

    duplicate_mode = str(settings.get("duplicate_match_mode", "separate_rarity")).strip().lower()

    embed = discord.Embed(
        title="Manage Duplicate Items",
        description="Control duplicate-copy point reduction and what counts as a duplicate copy.",
        color=discord.Color.dark_teal(),
    )
    embed.add_field(
        name="Duplicate Point Reduction",
        value=(
            f"• Current value: **{duplicate_reduction:.2f}x**\n"
            "• Applied to each duplicate copy after the first in a duplicate bucket.\n"
            "• Set to `0` to disable duplicate points."
        ),
        inline=False,
    )
    embed.add_field(
        name="What Is Duplicate",
        value=(
            f"• Current mode: **{_duplicate_mode_label(duplicate_mode)}**\n"
            + "\n".join(_duplicate_mode_description_lines(duplicate_mode))
        ),
        inline=False,
    )
    embed.set_footer(text="Any duplicate-setting change triggers a full PPE points recalculation.")
    return embed


def build_manage_duplicate_mode_embed(settings: dict) -> discord.Embed:
    """Build duplicate-mode selection embed."""
    duplicate_mode = str(settings.get("duplicate_match_mode", "separate_rarity")).strip().lower()
    embed = discord.Embed(
        title="Manage What Is Duplicate",
        description="Choose how duplicate buckets are grouped before reduction is applied.",
        color=discord.Color.dark_teal(),
    )
    embed.add_field(name="Current Mode", value=f"**{_duplicate_mode_label(duplicate_mode)}**", inline=False)
    embed.add_field(
        name="Mode Meanings",
        value=(
            "• Different rarities are separate: item + rarity + shiny must match (default).\n"
            "• Any rarity of same item is duplicate: item + shiny must match.\n"
            "• Divines are exempt; others group: divine drops are always full points, others use item + shiny.\n"
            "• All variants including shinies group: only item name matters."
        ),
        inline=False,
    )
    return embed


def _safe_positive_float(value: object, fallback: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


def _build_penalty_rate_lines(penalty_weights: dict) -> list[str]:
    def _format_rate(value: object, fallback: float) -> str:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            parsed = fallback
        if parsed <= 0:
            return "0"
        return f"{-1.0 / parsed:.2f}"

    def _format_incombat_rate(value: object, fallback: float) -> str:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            parsed = fallback
        if parsed <= 0:
            return "0"
        return f"{-0.2 / parsed:.2f}"

    return [
        f"• Pet Level: **{_format_rate(penalty_weights.get('pet_level_per_point'), 4.0)}** pts per level",
        f"• Exalts: **{_format_rate(penalty_weights.get('exalts_per_point'), 2.0)}** pts per exalt",
        f"• Loot Boost: **{_format_rate(penalty_weights.get('loot_percent_per_point'), 0.5)}** pts per 1% boost",
        f"• In-Combat Reduction: **{_format_incombat_rate(penalty_weights.get('incombat_seconds_per_point'), 0.1)}** pts per 0.2 seconds",
    ]


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
            "Open granular season reset actions and choose exactly what to reset.\n"
            "Each reset action requires **Discord Administrator** permission and always asks for confirmation."
        ),
        inline=False,
    )
    embed.add_field(
        name="Manage Point Settings",
        value=(
            "Open point modifier menus to review and edit global, pet, or class-specific percentage modifiers."
        ),
        inline=False,
    )
    embed.add_field(
        name="Manage Contests",
        value=(
            "Set the default `/leaderboard` contest board, configure leaderboard scoring, and manage the join-role embed.\n"
            "Default PPE quest behavior: only completed quest items found on the active PPE count toward PPE leaderboard quest points."
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
    embed.add_field(
        name="Manage Bot Cost",
        value=(
            "Review per-command memory/cache cost logs, identify expensive commands, and export cost summaries."
        ),
        inline=False,
    )
    embed.add_field(
        name="Factory Reset Settings",
        value=(
            "Quick reset for admin-tunable settings only. Preserves sniffer endpoint and join embed references."
        ),
        inline=False,
    )
    embed.set_footer(text="This menu is owner-bound: only the admin who opened it can use the controls.")
    return embed


def build_manage_bot_cost_embed(summary: dict[str, object]) -> discord.Embed:
    """Build the bot-cost management embed for /manageseason."""
    window_hours = int(summary.get("window_hours", 24) or 24)
    entry_count = int(summary.get("entry_count", 0) or 0)
    command_count = int(summary.get("command_count", 0) or 0)
    error_count = int(summary.get("error_count", 0) or 0)
    total_duration_seconds = float(summary.get("total_duration_seconds", 0.0) or 0.0)
    total_gb_minutes = float(summary.get("total_estimated_gb_minutes", 0.0) or 0.0)
    total_cost = float(summary.get("total_estimated_cost_usd", 0.0) or 0.0)
    total_rss_growth = float(summary.get("total_rss_growth_mb", 0.0) or 0.0)
    total_rss_shrink = float(summary.get("total_rss_shrink_mb", 0.0) or 0.0)
    total_cache_growth = int(summary.get("total_cache_growth", 0) or 0)
    total_cache_shrink = int(summary.get("total_cache_shrink", 0) or 0)
    max_rss_after_mb = float(summary.get("max_rss_after_mb", 0.0) or 0.0)
    cost_rate = float(summary.get("cost_rate_per_gb_minute", 0.0) or 0.0)
    log_path = str(summary.get("log_path", "N/A") or "N/A")

    top_by_cost = summary.get("top_by_cost", []) if isinstance(summary.get("top_by_cost", []), list) else []
    cost_lines: list[str] = []
    for index, row in enumerate(top_by_cost[:5], start=1):
        if not isinstance(row, dict):
            continue
        command = str(row.get("command", "unknown"))
        command_cost = float(row.get("total_estimated_cost_usd", 0.0) or 0.0)
        cost_share = float(row.get("cost_share_percent", 0.0) or 0.0)
        call_count = int(row.get("call_count", 0) or 0)
        cache_growth = int(row.get("total_cache_growth", 0) or 0)
        tracking_source = str(row.get("tracking_source", "unknown")).strip() or "unknown"
        cost_lines.append(
            f"{index}. {command} - ${command_cost:.6f} ({cost_share:.1f}%), calls={call_count}, cache+={cache_growth}, src={tracking_source}"
        )
    if not cost_lines:
        cost_lines = ["No command cost records in this window yet."]

    top_by_rss = summary.get("top_by_rss_growth", []) if isinstance(summary.get("top_by_rss_growth", []), list) else []
    rss_lines: list[str] = []
    for index, row in enumerate(top_by_rss[:5], start=1):
        if not isinstance(row, dict):
            continue
        command = str(row.get("command", "unknown"))
        rss_growth = float(row.get("total_rss_growth_mb", 0.0) or 0.0)
        rss_share = float(row.get("rss_growth_share_percent", 0.0) or 0.0)
        call_count = int(row.get("call_count", 0) or 0)
        command_cost = float(row.get("total_estimated_cost_usd", 0.0) or 0.0)
        tracking_source = str(row.get("tracking_source", "unknown")).strip() or "unknown"
        rss_lines.append(
            f"{index}. {command} - rss+={rss_growth:.1f} MB ({rss_share:.1f}%), calls={call_count}, cost=${command_cost:.6f}, src={tracking_source}"
        )
    if not rss_lines:
        rss_lines = ["No RSS growth records in this window yet."]

    top_by_cache = (
        summary.get("top_by_cache_growth", [])
        if isinstance(summary.get("top_by_cache_growth", []), list)
        else []
    )
    cache_lines: list[str] = []
    for index, row in enumerate(top_by_cache[:5], start=1):
        if not isinstance(row, dict):
            continue
        command = str(row.get("command", "unknown"))
        cache_growth = int(row.get("total_cache_growth", 0) or 0)
        cache_share = float(row.get("cache_growth_share_percent", 0.0) or 0.0)
        call_count = int(row.get("call_count", 0) or 0)
        command_cost = float(row.get("total_estimated_cost_usd", 0.0) or 0.0)
        tracking_source = str(row.get("tracking_source", "unknown")).strip() or "unknown"
        cache_lines.append(
            f"{index}. {command} - cache+={cache_growth} ({cache_share:.1f}%), calls={call_count}, cost=${command_cost:.6f}, src={tracking_source}"
        )
    if not cache_lines:
        cache_lines = ["No cache growth records in this window yet."]

    embed = discord.Embed(
        title="Manage Bot Cost",
        description=(
            "Per-guild command telemetry to estimate memory spend, RSS growth, and cache growth by command.\n"
            f"Viewing last **{window_hours}h**."
        ),
        color=discord.Color.orange(),
    )
    embed.add_field(
        name="Window Summary",
        value=(
            f"Commands logged: **{entry_count}** across **{command_count}** command names\n"
            f"Errors: **{error_count}**\n"
            f"Total runtime: **{total_duration_seconds:.2f}s**\n"
            f"Estimated usage: **{total_gb_minutes:.6f} GB-min**\n"
            f"Estimated cost: **${total_cost:.6f}**\n"
            f"RSS growth total: **+{total_rss_growth:.1f} MB** / shrink total: **-{total_rss_shrink:.1f} MB**\n"
            f"Cache growth total: **+{total_cache_growth}** / shrink total: **-{total_cache_shrink}**\n"
            f"Peak RSS observed after command: **{max_rss_after_mb:.1f} MB**"
        ),
        inline=False,
    )
    embed.add_field(
        name="Top Cost Contributors",
        value=_truncate_field_value("\n".join(cost_lines)),
        inline=False,
    )
    embed.add_field(
        name="Top RSS Growth Contributors",
        value=_truncate_field_value("\n".join(rss_lines)),
        inline=False,
    )
    embed.add_field(
        name="Top Cache Growth Contributors",
        value=_truncate_field_value("\n".join(cache_lines)),
        inline=False,
    )
    embed.add_field(
        name="Telemetry",
        value=(
            f"Cost rate: **${cost_rate:.6f} / GB-minute**\n"
            f"Log file: `{log_path}`"
        ),
        inline=False,
    )
    embed.set_footer(text="Use this panel to refresh windows, export summary/raw logs, or clear guild cost logs.")
    return embed


def build_manage_contests_embed(settings: dict) -> discord.Embed:
    """Build the Manage Contests home embed."""
    default_choice = settings.get("default_contest_leaderboard")
    default_label = contest_leaderboard_label(default_choice)
    ppe_aggregate_enabled = bool(settings.get("ppe_aggregate_points_enabled", False))
    team_aggregate_enabled = bool(settings.get("team_aggregate_points_enabled", False))
    ppe_quest_enabled = bool(settings.get("ppe_contest_include_quest_points", False))
    ppe_active_filter_enabled = bool(settings.get("ppe_contest_require_active_ppe_quest_items", True))
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
            f"PPE aggregate points: **{'Enabled' if ppe_aggregate_enabled else 'Disabled'}**\n"
            f"Team aggregate points: **{'Enabled' if team_aggregate_enabled else 'Disabled'}**\n"
            f"PPE contest quest scoring: **{'Enabled' if ppe_quest_enabled else 'Disabled'}**\n"
            f"PPE quest/PPE item match required: **{'Enabled' if ppe_active_filter_enabled else 'Disabled'}**\n"
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
    embed.set_footer(text="PPE quest-to-active-PPE matching is enabled by default.")
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
    ppe_aggregate_enabled = bool(settings.get("ppe_aggregate_points_enabled", False))
    ppe_quest_enabled = bool(settings.get("ppe_contest_include_quest_points", False))
    ppe_active_filter_enabled = bool(settings.get("ppe_contest_require_active_ppe_quest_items", True))
    team_aggregate_enabled = bool(settings.get("team_aggregate_points_enabled", False))
    team_quest_enabled = bool(settings.get("team_contest_include_quest_points", False))

    embed = discord.Embed(
        title="Leaderboard Manager",
        description="Configure how points are calculated for contest leaderboards.",
        color=discord.Color.dark_magenta(),
    )
    embed.add_field(
        name="PPE Aggregate Points",
        value=(
            f"Current status: **{'Enabled' if ppe_aggregate_enabled else 'Disabled'}**\n"
            "When enabled, each player's PPE leaderboard score adds all of their PPE characters together.\n"
            "When disabled, PPE leaderboard score uses only that player's best PPE."
        ),
        inline=False,
    )
    embed.add_field(
        name="PPE Contest Quest Scoring",
        value=(
            f"Current status: **{'Enabled' if ppe_quest_enabled else 'Disabled'}**\n"
            "When enabled, completed quests add to PPE leaderboard totals.\n"
            "If team shared quests are enabled, each team member receives their team shared quest total.\n"
            "Works with aggregate mode: all PPE points + quest points are combined."
        ),
        inline=False,
    )
    embed.add_field(
        name="PPE Quest/PPE Item Match",
        value=(
            f"Current status: **{'Enabled' if ppe_active_filter_enabled else 'Disabled'}**\n"
            "When enabled, PPE quest points only count completed quests where the item exists on that player's active PPE loot.\n"
            "When disabled, all completed quests count for PPE quest points (legacy behavior)."
        ),
        inline=False,
    )
    embed.add_field(
        name="Team Aggregate Points",
        value=(
            f"Current status: **{'Enabled' if team_aggregate_enabled else 'Disabled'}**\n"
            "When enabled, team leaderboard score adds every character on every member.\n"
            "When disabled, team leaderboard score uses each member's best PPE."
        ),
        inline=False,
    )
    embed.add_field(
        name="Team Contest Quest Scoring",
        value=(
            f"Current status: **{'Enabled' if team_quest_enabled else 'Disabled'}**\n"
            "When enabled, completed quests add points to team totals.\n"
            "If team shared quests are enabled, shared quest points are counted once per team.\n"
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
    penalty_weights = settings.get("penalty_weights", {}) if isinstance(settings.get("penalty_weights"), dict) else {}
    starting_penalty_modifiers = (
        settings.get("starting_penalty_modifiers", {})
        if isinstance(settings.get("starting_penalty_modifiers"), dict)
        else {}
    )
    rarity_multipliers = (
        settings.get("rarity_multipliers", {})
        if isinstance(settings.get("rarity_multipliers"), dict)
        else {}
    )
    try:
        duplicate_reduction = float(settings.get("duplicate_point_reduction", 0.5))
    except (TypeError, ValueError):
        duplicate_reduction = 0.5
    if duplicate_reduction < 0:
        duplicate_reduction = 0.5

    embed = discord.Embed(
        title="Manage Point Settings",
        description=(
            "Point controls are split into global/class modifiers, starting-penalty tuning, and duplicate/type scaling."
        ),
        color=discord.Color.dark_teal(),
    )
    embed.add_field(
        name="Global Modifiers",
        value=(
            f"• Loot: **{_format_percent(global_settings.get('loot_percent', 0.0))}**\n"
            f"• Bonus: **{_format_percent(global_settings.get('bonus_percent', 0.0))}**\n"
            f"• Penalty: **{_format_percent(global_settings.get('penalty_percent', 0.0))}**\n"
            f"• Total: **{_format_percent(global_settings.get('total_percent', 0.0))}**"
        ),
        inline=False,
    )
    override_lines = _build_class_override_lines(class_overrides)
    preview = "No class overrides configured."
    if override_lines:
        preview = "\n".join(override_lines[:6])
        if len(override_lines) > 6:
            preview += f"\n... and {len(override_lines) - 6} more"
    embed.add_field(name="Class Overrides", value=_truncate_field_value(preview), inline=False)
    embed.add_field(
        name="Penalty Base Rates",
        value="\n".join(_build_penalty_rate_lines(penalty_weights)),
        inline=False,
    )
    embed.add_field(
        name="Penalty Reduction Modifiers",
        value=("\n".join(_build_starting_penalty_modifier_lines(starting_penalty_modifiers))
               + "\n• Reductions stack additively per starting stat."),
        inline=False,
    )
    embed.add_field(
        name="Duplicate Item Points",
        value=(
            f"• Point Reduction: **{duplicate_reduction:.2f}x**\n"
            f"• Duplicate Mode: **{_duplicate_mode_label(str(settings.get('duplicate_match_mode', 'separate_rarity')))}**\n"
            "• Applies to every duplicate copy after the first.\n"
            "• Set `0` to disable duplicate points"
        ),
        inline=False,
    )
    embed.add_field(
        name="Top Point Handling",
        value=(
            f"• Mode: **{str(settings.get('tops_point_mode', 'current')).title()}**\n"
            "• Current: Tops keep their normal repeat behavior.\n"
            "• Once: Tops only award points the first time they are logged.\n"
            "• None: Tops still log to seasonal loot, but award no points."
        ),
        inline=False,
    )
    embed.add_field(
        name="Rarity Modifiers",
        value="\n".join(_build_rarity_multiplier_lines(rarity_multipliers)),
        inline=False,
    )
    embed.add_field(
        name="PPE Type Multipliers",
        value="Use **Edit PPE Type Points** to manage final-score multipliers per PPE type.",
        inline=False,
    )
    embed.set_footer(text="Any points-setting change triggers a full PPE points recalculation.")
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

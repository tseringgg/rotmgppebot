"""Shared helpers that build embeds and perform actions for the /myinfo menu flow."""

from __future__ import annotations

import os

import discord

from dataclass import PPEData, PlayerData
from menus.menu_utils import SafeResponse
from utils.group_ppes import duo_partner_id_from_options, duo_link_id_from_options
from utils.ppe_types import is_duo_ppe_type, normalize_ppe_type, ppe_type_compact_summary, ppe_type_display_from_options
from utils.guild_config import get_realmshark_settings, load_guild_config
from utils.loot_helpers.loot_share_commands import share_active_ppe_loot_image
from utils.message_utils.loot_table_md_builder import create_loot_markdown_file, create_season_loot_markdown_file
from utils.message_utils.ppe_list_md_builder import create_ppe_list_markdown_file
from utils.points_service import (
    format_starting_penalty_line,
    loot_adjustment_detail_lines,
    loot_adjustments_for_ppe,
    penalty_inputs_from_bonuses,
    recompute_ppe_points,
    starting_penalty_breakdown_from_inputs,
)
from utils.player_records import ensure_player_exists, load_player_records, save_player_records
from utils.season_loot_history import iter_season_variants, unique_season_item_count


async def send_interaction_text(interaction: discord.Interaction, content: str, *, ephemeral: bool) -> None:
    await SafeResponse.send_text(interaction, content, ephemeral=ephemeral)


async def close_myinfo_menu(interaction: discord.Interaction) -> None:
    """Safely close an existing myinfo menu message if still editable."""
    await SafeResponse.close(interaction, close_message="Closed `/myinfo` menu.")


def display_class_name(ppe: PPEData) -> str:
    return str(getattr(ppe.name, "value", ppe.name))


def format_points(value: float) -> str:
    rounded = round(float(value), 2)
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:.2f}".rstrip("0").rstrip(".")


def get_best_ppe(player_data: PlayerData) -> PPEData | None:
    sorted_ppes = sorted(player_data.ppes, key=lambda p: int(p.id))
    return max(sorted_ppes, key=lambda p: float(p.points), default=None)


def ppe_type_text(ppe: PPEData, *, compact: bool = False, guild_config: dict | None = None) -> str:
    normalized = normalize_ppe_type(getattr(ppe, "ppe_type", None))
    options = getattr(ppe, "ppe_type_options", None)
    ppe_settings = guild_config.get("ppe_settings", {}) if isinstance(guild_config, dict) and isinstance(guild_config.get("ppe_settings", {}), dict) else None
    if compact:
        return ppe_type_compact_summary(options, fallback_type=normalized, ppe_settings=ppe_settings)
    return ppe_type_display_from_options(
        options,
        fallback_type=normalized,
        ppe_settings=ppe_settings,
        compact=False,
    )


def duo_partner_label_for_ppe(ppe: PPEData, guild: discord.Guild | None = None) -> str | None:
    options = getattr(ppe, "ppe_type_options", None)
    partner_id = duo_partner_id_from_options(options)
    if partner_id is None:
        return None

    if guild is not None:
        member = guild.get_member(partner_id)
        if member is not None:
            return member.display_name

    return f"<@{partner_id}>"


def duo_link_id_for_ppe(ppe: PPEData) -> str | None:
    return duo_link_id_from_options(getattr(ppe, "ppe_type_options", None))


def duo_partner_details_for_ppe(
    ppe: PPEData,
    *,
    owner_user_id: int,
    records: dict[int, PlayerData] | None,
    guild: discord.Guild | None = None,
    guild_config: dict | None = None,
) -> str | None:
    options = getattr(ppe, "ppe_type_options", None)
    partner_id = duo_partner_id_from_options(options)
    if partner_id is None:
        return None

    if guild is not None:
        member = guild.get_member(partner_id)
        partner_label = member.display_name if member is not None else f"<@{partner_id}>"
    else:
        partner_label = f"<@{partner_id}>"

    if not isinstance(records, dict):
        return partner_label

    partner_data = records.get(int(partner_id))
    if partner_data is None:
        return partner_label

    expected_link_id = duo_link_id_for_ppe(ppe)
    fallback_match: PPEData | None = None
    matched_partner_ppe: PPEData | None = None

    for candidate in getattr(partner_data, "ppes", []):
        candidate_options = getattr(candidate, "ppe_type_options", None)
        candidate_partner_id = duo_partner_id_from_options(candidate_options)
        if candidate_partner_id != int(owner_user_id):
            continue

        if fallback_match is None:
            fallback_match = candidate

        if expected_link_id is None:
            continue
        if duo_link_id_for_ppe(candidate) == expected_link_id:
            matched_partner_ppe = candidate
            break

    partner_ppe = matched_partner_ppe or fallback_match
    if partner_ppe is None:
        return partner_label

    partner_type = ppe_type_text(partner_ppe, compact=True, guild_config=guild_config)
    return (
        f"{partner_label}\n"
        f"Linked PPE: #{partner_ppe.id} - {display_class_name(partner_ppe)} [{partner_type}]"
    )


def penalty_stats_text(ppe: PPEData, guild_config: dict | None = None) -> str:
    """Convert stored penalty bonuses into user-friendly stat values."""

    defaults = penalty_input_defaults(ppe, guild_config)
    breakdown = starting_penalty_breakdown_from_inputs(
        int(defaults["pet_level"]),
        int(defaults["num_exalts"]),
        float(defaults["percent_loot"]),
        float(defaults["incombat_reduction"]),
        guild_config=guild_config,
    )

    def _line(label: str, value_text: str, details: dict[str, float]) -> str:
        return format_starting_penalty_line(label, value_text, details)

    return (
        _line("Pet Level", str(int(defaults["pet_level"])), breakdown["Pet Level Penalty"])
        + "\n"
        + _line("Exalts", str(int(defaults["num_exalts"])), breakdown["Exalts Penalty"])
        + "\n"
        + _line("Loot Boost", f"{float(defaults['percent_loot']):g}%", breakdown["Loot Boost Penalty"])
        + "\n"
        + _line(
            "In-Combat Reduction",
            f"{float(defaults['incombat_reduction']):g}s",
            breakdown["In-Combat Reduction Penalty"],
        )
    )


def penalty_input_defaults(ppe: PPEData, guild_config: dict | None = None) -> dict[str, float]:
    """Return editable penalty form defaults derived from stored penalty bonuses."""
    return penalty_inputs_from_bonuses(ppe.bonuses, guild_config=guild_config)


def loot_adjustments_text(ppe: PPEData, guild_config: dict | None = None) -> str:
    adjustments = loot_adjustments_for_ppe(ppe, guild_config)
    return "\n".join(loot_adjustment_detail_lines(adjustments))


def build_home_embed(
    user: discord.abc.User,
    player_data: PlayerData,
    active_ppe: PPEData | None,
    *,
    max_ppes: int,
) -> discord.Embed:
    best_ppe = get_best_ppe(player_data)

    if best_ppe:
        best_line = (
            f"PPE #{best_ppe.id} ({display_class_name(best_ppe)}, {ppe_type_text(best_ppe, compact=True)}): "
            f"**{format_points(best_ppe.points)}**"
        )
    else:
        best_line = "None"

    if active_ppe:
        active_line = (
            f"PPE #{active_ppe.id} ({display_class_name(active_ppe)}, {ppe_type_text(active_ppe, compact=True)}): "
            f"**{format_points(active_ppe.points)}**"
        )
    else:
        active_line = "No active PPE"

    embed = discord.Embed(
        title=f"My Info Dashboard - {user.display_name}",
        description="Everything for your PPE tracking in one place.",
        color=discord.Color.blurple(),
    )
    team_name = player_data.team_name or "N/A"
    embed.add_field(name="Number of PPEs", value=f"**{len(player_data.ppes)}/{max_ppes}**", inline=True)
    embed.add_field(name="Best PPE", value=best_line, inline=True)
    embed.add_field(name="Number of Season Items", value=f"**{unique_season_item_count(player_data)}**", inline=True)
    embed.add_field(name="Team", value=f"**{team_name}**", inline=True)
    embed.add_field(name="Current Active PPE", value=active_line, inline=False)

    help_lines = [
        "Use **/newppe** to create a new PPE.",
        "Use **/addloot** and **/addseasonloot** to log loot.",
        "Use **/removeloot** and **/removeseasonloot** to remove loot.",
        "Use **/addbonus** and **/removebonus** to manage bonuses such as fame or maxed stats.",
        "Use **/setactiveppe** to quickly manage which PPE is active (determines character affected by /addloot).",
    ]
    embed.add_field(name="How To Use The Bot", value="\n".join(help_lines), inline=False)
    embed.set_footer(text="Buttons below open actions and dashboards.")
    return embed


def build_character_embed(
    *,
    user: discord.abc.User,
    player_data: PlayerData,
    ppe: PPEData,
    index: int,
    total: int,
    is_active: bool,
    is_best: bool,
    is_realmshark_connected: bool,
    duo_partner_details: str | None = None,
    guild_config: dict | None = None,
    guild: discord.Guild | None = None,
) -> discord.Embed:
    character_type = ppe_type_text(ppe, guild_config=guild_config)
    compact_type = ppe_type_text(ppe, compact=True, guild_config=guild_config)
    distinct_loot_items = len([loot for loot in ppe.loot if int(loot.quantity) > 0])

    title_prefix: list[str] = []
    if is_best:
        title_prefix.append("🏅")
    if is_active:
        title_prefix.append("⭐")

    title_core = f"PPE #{ppe.id} - {display_class_name(ppe)} [{compact_type}]"
    title = f"{' '.join(title_prefix)} {title_core}" if title_prefix else title_core

    embed = discord.Embed(
        title=title,
        description=(
            f"{user.display_name}'s Character Panel\n"
            f"Character {index}/{total}"
        ),
        color=discord.Color.teal(),
    )

    embed.add_field(name="Points", value=f"**{format_points(ppe.points)}**", inline=True)
    embed.add_field(name="RealmShark Connected", value="Yes" if is_realmshark_connected else "No", inline=True)
    embed.add_field(name="Different Loot Items", value=str(distinct_loot_items), inline=True)
    embed.add_field(name="Starting Penalty Stats", value=penalty_stats_text(ppe, guild_config), inline=False)
    embed.add_field(name="Loot Adjustments", value=loot_adjustments_text(ppe, guild_config), inline=False)
    embed.add_field(name="Character Type", value=character_type, inline=True)
    duo_partner_label = duo_partner_label_for_ppe(ppe, guild)
    if duo_partner_details is not None:
        embed.add_field(name="Duo Partner", value=duo_partner_details, inline=True)
    else:
        if duo_partner_label is not None:
            embed.add_field(name="Duo Partner", value=duo_partner_label, inline=True)
    if duo_partner_details is None and duo_partner_label is None and is_duo_ppe_type(normalize_ppe_type(getattr(ppe, "ppe_type", None))):
        embed.add_field(name="Duo Partner", value="Not set yet. Use Set Duo Partner to link this legacy duo PPE.", inline=True)
    embed.add_field(name="Active Status", value="⭐ Active PPE" if is_active else "Not Active", inline=True)

    embed.set_footer(text="Click Manage PPE to edit starting penalties. Set As Active will cause addloot to add items to this PPE.")
    return embed


async def realmshark_connected_ppe_ids(interaction: discord.Interaction, user_id: int) -> set[int]:
    settings = await get_realmshark_settings(interaction)
    links = settings.get("links", {}) if isinstance(settings.get("links"), dict) else {}

    connected: set[int] = set()
    for link_data in links.values():
        if not isinstance(link_data, dict):
            continue

        try:
            linked_user_id = int(link_data.get("user_id"))
        except (TypeError, ValueError):
            continue

        if linked_user_id != int(user_id):
            continue

        bindings = link_data.get("character_bindings", {})
        if not isinstance(bindings, dict):
            continue

        for raw_ppe_id in bindings.values():
            try:
                parsed = int(raw_ppe_id)
            except (TypeError, ValueError):
                continue
            if parsed > 0:
                connected.add(parsed)

    return connected


async def send_season_loot_markdown_followup(interaction: discord.Interaction) -> None:
    records = await load_player_records(interaction)
    key = ensure_player_exists(records, interaction.user.id)

    if key not in records or not records[key].is_member:
        await interaction.followup.send("❌ You're not part of the PPE contest.", ephemeral=True)
        return

    player_data = records[key]
    season_variants = iter_season_variants(player_data)

    if not season_variants:
        await interaction.followup.send(
            "You haven't collected any season loot yet!\nUse `/addseasonloot` to start tracking your unique items.",
            ephemeral=True,
        )
        return

    temp_file_path = create_season_loot_markdown_file(
        player_data.season_item_history,
        display_name=interaction.user.display_name,
    )

    try:
        await interaction.followup.send(file=discord.File(temp_file_path), ephemeral=True)
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


async def send_ppe_list_markdown_followup(interaction: discord.Interaction, player_data: PlayerData) -> None:
    temp_file_path = ""
    try:
        guild_config = await load_guild_config(interaction)
        temp_file_path = create_ppe_list_markdown_file(
            player_data,
            display_name=interaction.user.display_name,
            include_best_marker=True,
            guild_config=guild_config,
        )
        await interaction.followup.send(file=discord.File(temp_file_path), ephemeral=True)
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)


async def send_myloot_markdown_followup(interaction: discord.Interaction, ppe: PPEData) -> None:
    guild_config = await load_guild_config(interaction)
    temp_file_path = create_loot_markdown_file(ppe, guild_config=guild_config)
    try:
        await interaction.followup.send(file=discord.File(temp_file_path), ephemeral=True)
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


async def temporarily_switch_active_ppe_and_share(
    interaction: discord.Interaction,
    ppe_id: int,
    *,
    include_skins: bool,
    include_limited: bool,
    target_user_id: int | None = None,
    target_display_name: str | None = None,
) -> None:
    # Temporarily target the selected PPE so the share helper can reuse active-PPE logic.
    records = await load_player_records(interaction)
    resolved_target_user_id = int(target_user_id) if target_user_id is not None else int(interaction.user.id)
    key = ensure_player_exists(records, resolved_target_user_id)
    player_data = records[key]
    old_active = player_data.active_ppe

    if old_active == ppe_id:
        await share_active_ppe_loot_image(
            interaction,
            include_skins=include_skins,
            include_limited=include_limited,
            target_user_id=resolved_target_user_id,
            target_display_name=target_display_name,
        )
        return

    player_data.active_ppe = ppe_id
    await save_player_records(interaction, records)

    try:
        await share_active_ppe_loot_image(
            interaction,
            include_skins=include_skins,
            include_limited=include_limited,
            target_user_id=resolved_target_user_id,
            target_display_name=target_display_name,
        )
    finally:
        records_restore = await load_player_records(interaction)
        restore_key = ensure_player_exists(records_restore, resolved_target_user_id)
        records_restore[restore_key].active_ppe = old_active
        await save_player_records(interaction, records_restore)


async def refresh_player_data(interaction: discord.Interaction, user_id: int) -> PlayerData:
    guild_config = await load_guild_config(interaction)
    records = await load_player_records(interaction)
    key = ensure_player_exists(records, user_id)
    player_data = records[key]

    changed = False
    for ppe in player_data.ppes:
        previous_points = round(float(ppe.points), 2)
        breakdown = recompute_ppe_points(ppe, guild_config)
        if round(float(breakdown.get("total", ppe.points)), 2) != previous_points:
            changed = True

    if changed:
        await save_player_records(interaction, records)

    return player_data


def find_ppe_or_raise(player_data: PlayerData, ppe_id: int) -> PPEData:
    for ppe in player_data.ppes:
        if int(ppe.id) == int(ppe_id):
            return ppe
    raise LookupError(f"PPE #{ppe_id} not found.")

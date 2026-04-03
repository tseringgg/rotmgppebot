"""Shared helpers that build embeds and perform actions for the /myinfo menu flow."""

from __future__ import annotations

import os

import discord

from dataclass import PPEData, PlayerData
from menus.menu_utils import SafeResponse
from utils.ppe_types import normalize_ppe_type, ppe_type_label, ppe_type_short_label
from utils.guild_config import get_realmshark_settings, load_guild_config
from utils.helpers.loot_share_commands import share_active_ppe_loot_image
from utils.loot_table_md_builder import create_loot_markdown_file, create_season_loot_markdown_file
from utils.ppe_list_md_builder import create_ppe_list_markdown_file
from utils.points_service import penalty_inputs_from_bonuses
from utils.player_records import ensure_player_exists, load_player_records, save_player_records


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


def ppe_type_text(ppe: PPEData, *, compact: bool = False) -> str:
    normalized = normalize_ppe_type(getattr(ppe, "ppe_type", None))
    if compact:
        return ppe_type_short_label(normalized)

    full = ppe_type_label(normalized)
    short = ppe_type_short_label(normalized)
    if full == short:
        return full
    return f"{full} ({short})"


def penalty_stats_text(ppe: PPEData, guild_config: dict | None = None) -> str:
    """Convert stored penalty bonuses into user-friendly stat values."""

    defaults = penalty_input_defaults(ppe, guild_config)

    return (
        f"Pet Level: **{int(defaults['pet_level'])}**\n"
        f"Exalts: **{int(defaults['num_exalts'])}**\n"
        f"Loot Boost: **{float(defaults['percent_loot']):g}%**\n"
        f"In-Combat Reduction: **{float(defaults['incombat_reduction']):g}s**"
    )


def penalty_input_defaults(ppe: PPEData, guild_config: dict | None = None) -> dict[str, float]:
    """Return editable penalty form defaults derived from stored penalty bonuses."""
    return penalty_inputs_from_bonuses(ppe.bonuses, guild_config=guild_config)


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
    embed.add_field(name="Number of Season Items", value=f"**{len(player_data.unique_items)}**", inline=True)
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
    guild_config: dict | None = None,
) -> discord.Embed:
    character_type = ppe_type_text(ppe)
    compact_type = ppe_type_text(ppe, compact=True)
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
    embed.add_field(name="Character Type", value=character_type, inline=True)
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
    items_list = sorted(player_data.unique_items, key=lambda x: (x[0].lower(), x[1]))

    if not items_list:
        await interaction.followup.send(
            "You haven't collected any season loot yet!\nUse `/addseasonloot` to start tracking your unique items.",
            ephemeral=True,
        )
        return

    temp_file_path = create_season_loot_markdown_file(
        player_data.unique_items,
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
) -> None:
    # Temporarily target the selected PPE so the share helper can reuse active-PPE logic.
    records = await load_player_records(interaction)
    key = ensure_player_exists(records, interaction.user.id)
    player_data = records[key]
    old_active = player_data.active_ppe

    if old_active == ppe_id:
        await share_active_ppe_loot_image(interaction, include_skins=include_skins, include_limited=include_limited)
        return

    player_data.active_ppe = ppe_id
    await save_player_records(interaction, records)

    try:
        await share_active_ppe_loot_image(interaction, include_skins=include_skins, include_limited=include_limited)
    finally:
        records_restore = await load_player_records(interaction)
        restore_key = ensure_player_exists(records_restore, interaction.user.id)
        records_restore[restore_key].active_ppe = old_active
        await save_player_records(interaction, records_restore)


async def refresh_player_data(interaction: discord.Interaction, user_id: int) -> PlayerData:
    records = await load_player_records(interaction)
    key = ensure_player_exists(records, user_id)
    return records[key]


def find_ppe_or_raise(player_data: PlayerData, ppe_id: int) -> PPEData:
    for ppe in player_data.ppes:
        if int(ppe.id) == int(ppe_id):
            return ppe
    raise LookupError(f"PPE #{ppe_id} not found.")

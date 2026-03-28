"""Shared helpers that build embeds and perform actions for the /myinfo menu flow."""

from __future__ import annotations

import os

import discord

from dataclass import PPEData, PlayerData
from utils.guild_config import get_max_ppes, get_realmshark_settings
from utils.helpers.loot_share_commands import share_active_ppe_loot_image
from utils.loot_table_md_builder import create_loot_markdown_file
from utils.markdown_message_builder import MarkdownMessageBuilder
from utils.player_records import ensure_player_exists, load_player_records, save_player_records


async def send_interaction_text(interaction: discord.Interaction, content: str, *, ephemeral: bool) -> None:
    if not interaction.response.is_done():
        await interaction.response.send_message(content, ephemeral=ephemeral)
        return
    await interaction.followup.send(content, ephemeral=ephemeral)


async def close_myinfo_menu(interaction: discord.Interaction) -> None:
    """Safely close an existing myinfo menu message if still editable."""

    if interaction.response.is_done():
        return

    try:
        await interaction.response.edit_message(content="Closed `/myinfo` menu.", embed=None, view=None)
    except discord.NotFound:
        await interaction.response.defer()


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


def get_penalty_map(ppe: PPEData) -> dict[str, float]:
    result = {
        "pet": 0.0,
        "exalts": 0.0,
        "loot": 0.0,
        "incombat": 0.0,
    }

    for bonus in ppe.bonuses:
        total = float(bonus.points) * max(1, int(getattr(bonus, "quantity", 1)))
        if bonus.name == "Pet Level Penalty":
            result["pet"] += total
        elif bonus.name == "Exalts Penalty":
            result["exalts"] += total
        elif bonus.name == "Loot Boost Penalty":
            result["loot"] += total
        elif bonus.name == "In-Combat Reduction Penalty":
            result["incombat"] += total

    return result


def penalty_stats_text(ppe: PPEData) -> str:
    """Convert stored penalty bonuses into user-friendly stat values."""

    penalties = get_penalty_map(ppe)

    pet_level = int(round(-4.0 * penalties["pet"])) if penalties["pet"] != 0 else 0
    exalts = int(round(-2.0 * penalties["exalts"])) if penalties["exalts"] != 0 else 0
    loot_boost = round(-0.5 * penalties["loot"], 1) if penalties["loot"] != 0 else 0.0
    incombat = round(-0.1 * penalties["incombat"], 1) if penalties["incombat"] != 0 else 0.0

    return (
        f"Pet Level: **{pet_level}**\n"
        f"Exalts: **{exalts}**\n"
        f"Loot Boost: **{loot_boost}%**\n"
        f"In-Combat Reduction: **{incombat}s**"
    )


def penalty_input_defaults(ppe: PPEData) -> dict[str, float]:
    """Return editable penalty form defaults derived from stored penalty bonuses."""

    penalties = get_penalty_map(ppe)
    pet_level = int(round(-4.0 * penalties["pet"])) if penalties["pet"] != 0 else 0
    exalts = int(round(-2.0 * penalties["exalts"])) if penalties["exalts"] != 0 else 0
    loot_boost = round(-0.5 * penalties["loot"], 1) if penalties["loot"] != 0 else 0.0
    incombat = round(-0.1 * penalties["incombat"], 1) if penalties["incombat"] != 0 else 0.0
    return {
        "pet_level": max(0, pet_level),
        "num_exalts": max(0, exalts),
        "percent_loot": max(0.0, loot_boost),
        "incombat_reduction": max(0.0, incombat),
    }


def team_type_text(player_data: PlayerData) -> str:
    return "Team PPE" if player_data.team_name else "Regular PPE"


def build_home_embed(
    user: discord.abc.User,
    player_data: PlayerData,
    active_ppe: PPEData | None,
    *,
    max_ppes: int,
) -> discord.Embed:
    best_ppe = get_best_ppe(player_data)

    if best_ppe:
        best_line = f"PPE #{best_ppe.id} ({display_class_name(best_ppe)}): **{format_points(best_ppe.points)}**"
    else:
        best_line = "None"

    if active_ppe:
        active_line = f"PPE #{active_ppe.id} ({display_class_name(active_ppe)}): **{format_points(active_ppe.points)}**"
    else:
        active_line = "No active PPE"

    embed = discord.Embed(
        title=f"My Info Dashboard - {user.display_name}",
        description="Everything for your PPE tracking in one place.",
        color=discord.Color.blurple(),
    )
    embed.add_field(name="Number of PPEs", value=f"**{len(player_data.ppes)}/{max_ppes}**", inline=True)
    embed.add_field(name="Best PPE", value=best_line, inline=True)
    embed.add_field(name="Number of Season Items", value=f"**{len(player_data.unique_items)}**", inline=True)
    embed.add_field(name="Current Active PPE", value=active_line, inline=False)

    help_lines = [
        "Use **/newppe** to create a new PPE.",
        "Use **/addloot** and **/addseasonloot** to log loot.",
        "Use **/removeloot** and **/removeseasonloot** to remove loot.",
        "Use **Manage Characters -> Modify PPE** to add or remove bonuses.",
        "Use **/setactiveppe** if you prefer quick switching from slash commands.",
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
) -> discord.Embed:
    character_type = team_type_text(player_data)
    distinct_loot_items = len([loot for loot in ppe.loot if int(loot.quantity) > 0])

    title_prefix: list[str] = []
    if is_best:
        title_prefix.append("🏅")
    if is_active:
        title_prefix.append("⭐")

    title = (
        f"{' '.join(title_prefix)} PPE #{ppe.id} - {display_class_name(ppe)}"
        if title_prefix
        else f"PPE #{ppe.id} - {display_class_name(ppe)}"
    )

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
    embed.add_field(name="Starting Penalty Stats", value=penalty_stats_text(ppe), inline=False)
    embed.add_field(name="Character Type", value=character_type, inline=True)
    embed.add_field(name="Active Status", value="⭐ Active PPE" if is_active else "Not Active", inline=True)

    embed.set_footer(text="Use Show Loot, Set As Active, or Manage PPE to edit penalties.")
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

    builder = MarkdownMessageBuilder(f"Season Loot for {interaction.user.display_name}")
    builder.add_paragraph(f"Total unique items: {len(items_list)}")

    lines: list[str] = []
    for item_name, shiny in items_list:
        marker = " [shiny]" if shiny else ""
        lines.append(f"{item_name}{marker}")

    builder.add_numbered_list(lines, heading="Items")
    temp_file_path = builder.write_temp_file(prefix="season_loot", username=interaction.user.display_name)

    try:
        await interaction.followup.send(file=discord.File(temp_file_path), ephemeral=True)
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


async def send_ppe_list_markdown_followup(interaction: discord.Interaction, player_data: PlayerData) -> None:
    sorted_ppes = sorted(player_data.ppes, key=lambda p: int(p.id))
    best_ppe = get_best_ppe(player_data)
    best_ppe_id = int(best_ppe.id) if best_ppe else None

    builder = MarkdownMessageBuilder(f"PPE List for {interaction.user.display_name}")
    try:
        if not sorted_ppes:
            builder.add_paragraph("No PPEs found.")
        else:
            lines: list[str] = []
            for ppe in sorted_ppes:
                labels: list[str] = []
                if int(ppe.id) == int(player_data.active_ppe or -1):
                    labels.append("ACTIVE")
                if best_ppe_id is not None and int(ppe.id) == best_ppe_id:
                    labels.append("BEST")
                suffix = f" [{' | '.join(labels)}]" if labels else ""
                lines.append(
                    f"PPE #{ppe.id} | Class: {display_class_name(ppe)} | Points: {format_points(ppe.points)}{suffix}"
                )
            builder.add_numbered_list(lines, heading="Characters")

        temp_file_path = builder.write_temp_file(prefix="ppe_list", username=interaction.user.display_name)
        await interaction.followup.send(file=discord.File(temp_file_path), ephemeral=True)
    finally:
        if "temp_file_path" in locals() and os.path.exists(temp_file_path):
            os.remove(temp_file_path)


async def send_myloot_markdown_followup(interaction: discord.Interaction, ppe: PPEData) -> None:
    temp_file_path = create_loot_markdown_file(ppe)
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


async def open_myinfo_home(interaction: discord.Interaction, *, max_ppes: int) -> None:
    from menus.myinfo.home_view import MyInfoHomeView

    records = await load_player_records(interaction)
    key = ensure_player_exists(records, interaction.user.id)
    player_data = records[key]

    active_ppe = None
    for ppe in player_data.ppes:
        if ppe.id == player_data.active_ppe:
            active_ppe = ppe
            break

    embed = build_home_embed(interaction.user, player_data, active_ppe, max_ppes=max_ppes)
    view = MyInfoHomeView(interaction.user.id, max_ppes=max_ppes)
    await interaction.response.edit_message(embed=embed, view=view)


async def open_myinfo_menu(interaction: discord.Interaction) -> None:
    """Open the /myinfo dashboard entry menu for the invoking user."""

    from menus.myinfo.home_view import MyInfoHomeView

    if not interaction.guild:
        await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
        return

    records = await load_player_records(interaction)
    key = ensure_player_exists(records, interaction.user.id)
    player_data = records[key]
    max_ppes = await get_max_ppes(interaction)

    active_ppe = None
    for ppe in player_data.ppes:
        if ppe.id == player_data.active_ppe:
            active_ppe = ppe
            break

    embed = build_home_embed(interaction.user, player_data, active_ppe, max_ppes=max_ppes)
    view = MyInfoHomeView(interaction.user.id, max_ppes=max_ppes)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

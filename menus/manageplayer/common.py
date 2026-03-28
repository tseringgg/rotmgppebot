"""Shared helpers for the /manageplayer admin menu flow."""

from __future__ import annotations

import os
from dataclasses import dataclass

import discord

from dataclass import PPEData, PlayerData
from menus.myinfo.common import (
    build_character_embed,
    display_class_name,
    format_points,
    penalty_input_defaults,
)
from utils.guild_config import get_max_ppes, get_quest_targets, load_guild_config
from utils.loot_table_md_builder import create_season_loot_markdown_file
from utils.pagination import LootPaginationView, chunk_lines_to_pages
from utils.penalty_embed import build_penalty_infographic_embed
from utils.player_manager import player_manager
from utils.player_records import ensure_player_exists, load_player_records, save_player_records
from utils.points_service import apply_penalties_to_ppe, parse_penalty_inputs, recompute_ppe_points
from utils.quest_manager import refresh_player_quests
from utils.realmshark_cleanup import clear_member_character_links, clear_ppe_character_links
from utils.team_manager import team_manager


@dataclass
class ManagedPlayerTarget:
    user_id: int
    display_name: str
    mention_text: str
    member: discord.Member | None
    has_player_role: bool


def _player_role(guild: discord.Guild) -> discord.Role | None:
    return discord.utils.get(guild.roles, name="PPE Player")


def _safe_display_name(member: discord.Member | None, user_id: int) -> str:
    if member is not None:
        return member.display_name
    return f"User {user_id}"


async def close_manageplayer_menu(interaction: discord.Interaction) -> None:
    if interaction.response.is_done():
        return

    try:
        await interaction.response.edit_message(content="Closed /manageplayer menu.", embed=None, view=None)
    except discord.NotFound:
        await interaction.response.defer()


async def send_followup_text(interaction: discord.Interaction, content: str, *, ephemeral: bool = True) -> None:
    if not interaction.response.is_done():
        await interaction.response.send_message(content, ephemeral=ephemeral)
        return
    await interaction.followup.send(content, ephemeral=ephemeral)


async def resolve_target(
    interaction: discord.Interaction,
    *,
    member: discord.Member | None,
    user_id: str | None,
) -> tuple[ManagedPlayerTarget | None, str | None]:
    if not interaction.guild:
        return None, "❌ This command can only be used in a server."

    if member is None and not user_id:
        return None, "❌ Provide either a server member or a Discord user ID."

    if member is not None and user_id:
        return None, "❌ Provide only one target: member OR user_id."

    target_member = member
    if member is not None:
        target_id = int(member.id)
    else:
        assert user_id is not None
        if not user_id.isdigit():
            return None, "❌ user_id must be a numeric Discord ID."

        target_id = int(user_id)
        target_member = interaction.guild.get_member(target_id)
        if target_member is None:
            try:
                target_member = await interaction.guild.fetch_member(target_id)
            except Exception:
                target_member = None

    records = await load_player_records(interaction)
    has_record = int(target_id) in records

    # Allow direct management by ID only when data already exists.
    if target_member is None and not has_record:
        return None, f"❌ No PPE data found for Discord user ID {target_id}."

    if target_member is not None:
        key = ensure_player_exists(records, int(target_id))
        records[key].is_member = records[key].is_member and True
        await save_player_records(interaction, records)

    role = _player_role(interaction.guild)
    has_player_role = bool(target_member and role and role in target_member.roles)

    display_name = _safe_display_name(target_member, target_id)
    mention_text = target_member.mention if target_member is not None else f"User {target_id}"
    return (
        ManagedPlayerTarget(
            user_id=int(target_id),
            display_name=display_name,
            mention_text=mention_text,
            member=target_member,
            has_player_role=has_player_role,
        ),
        None,
    )


def target_home_embed(
    *,
    target: ManagedPlayerTarget,
    player_data: PlayerData,
    active_ppe: PPEData | None,
    max_ppes: int,
) -> discord.Embed:
    best_ppe = max(player_data.ppes, key=lambda p: float(p.points), default=None)

    if best_ppe:
        best_line = f"PPE #{best_ppe.id} ({display_class_name(best_ppe)}): {format_points(best_ppe.points)}"
    else:
        best_line = "None"

    if active_ppe:
        active_line = f"PPE #{active_ppe.id} ({display_class_name(active_ppe)}): {format_points(active_ppe.points)}"
    else:
        active_line = "No active PPE"

    embed = discord.Embed(
        title=f"Manage Player - {target.display_name}",
        description=(
            "Admin management dashboard for this player. "
            "All changes made from this panel are posted publicly."
        ),
        color=discord.Color.dark_teal(),
    )
    embed.add_field(name="Discord ID", value=str(target.user_id), inline=True)
    embed.add_field(name="PPE Role", value="Has PPE Player" if target.has_player_role else "Missing PPE Player", inline=True)
    embed.add_field(name="PPE Count", value=f"{len(player_data.ppes)}/{max_ppes}", inline=True)
    embed.add_field(name="Team", value=player_data.team_name or "N/A", inline=True)
    embed.add_field(name="Best PPE", value=best_line, inline=False)
    embed.add_field(name="Active PPE", value=active_line, inline=False)
    embed.add_field(name="Season Items", value=str(len(player_data.unique_items)), inline=True)
    embed.set_footer(text="Use buttons below to manage player data, roles, and loot views.")
    return embed


def add_to_contest_embed(target: ManagedPlayerTarget) -> discord.Embed:
    embed = discord.Embed(
        title=f"Manage Player - {target.display_name}",
        description=(
            "This user does not currently have the PPE Player role.\n"
            "Use Add To Contest to give the role and enable standard PPE player commands."
        ),
        color=discord.Color.orange(),
    )
    embed.add_field(name="Discord ID", value=str(target.user_id), inline=True)
    embed.add_field(name="Current Status", value="Not in contest", inline=True)
    return embed


async def load_target_player_data(interaction: discord.Interaction, target_user_id: int) -> PlayerData:
    records = await load_player_records(interaction)
    key = ensure_player_exists(records, target_user_id)
    return records[key]


def active_ppe_for_player(player_data: PlayerData) -> PPEData | None:
    for ppe in player_data.ppes:
        if int(ppe.id) == int(player_data.active_ppe or -1):
            return ppe
    return None


async def open_manageplayer_home(
    interaction: discord.Interaction,
    *,
    owner_id: int,
    target: ManagedPlayerTarget,
    max_ppes: int,
) -> None:
    from menus.manageplayer.home_view import ManagePlayerHomeView, NotInContestView

    player_data = await load_target_player_data(interaction, target.user_id)
    active_ppe = active_ppe_for_player(player_data)

    if target.member is not None and not target.has_player_role:
        view = NotInContestView(owner_id=owner_id, target=target)
        await interaction.response.edit_message(embed=add_to_contest_embed(target), view=view)
        return

    embed = target_home_embed(target=target, player_data=player_data, active_ppe=active_ppe, max_ppes=max_ppes)
    view = ManagePlayerHomeView(
        owner_id=owner_id,
        target=target,
        max_ppes=max_ppes,
        target_team_name=player_data.team_name,
    )
    await interaction.response.edit_message(embed=embed, view=view)


async def open_manageplayer_menu(
    interaction: discord.Interaction,
    *,
    member: discord.Member | None = None,
    user_id: str | None = None,
) -> None:
    from menus.manageplayer.home_view import ManagePlayerHomeView, NotInContestView

    target, error = await resolve_target(interaction, member=member, user_id=user_id)
    if error:
        await interaction.response.send_message(error, ephemeral=False)
        return

    assert target is not None
    player_data = await load_target_player_data(interaction, target.user_id)
    active_ppe = active_ppe_for_player(player_data)
    max_ppes = await get_max_ppes(interaction)

    if target.member is not None and not target.has_player_role:
        view = NotInContestView(owner_id=interaction.user.id, target=target)
        await interaction.response.send_message(embed=add_to_contest_embed(target), view=view, ephemeral=False)
        return

    embed = target_home_embed(target=target, player_data=player_data, active_ppe=active_ppe, max_ppes=max_ppes)
    view = ManagePlayerHomeView(
        owner_id=interaction.user.id,
        target=target,
        max_ppes=max_ppes,
        target_team_name=player_data.team_name,
    )
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


def find_ppe_or_raise(player_data: PlayerData, ppe_id: int) -> PPEData:
    for ppe in player_data.ppes:
        if int(ppe.id) == int(ppe_id):
            return ppe
    raise LookupError(f"PPE #{ppe_id} not found.")


async def send_target_ppe_list_markdown_followup(
    interaction: discord.Interaction,
    *,
    target: ManagedPlayerTarget,
    player_data: PlayerData,
) -> None:
    sorted_ppes = sorted(player_data.ppes, key=lambda p: int(p.id))

    if not sorted_ppes:
        await interaction.followup.send(f"No PPEs found for {target.display_name}.", ephemeral=True)
        return

    lines: list[str] = []
    for ppe in sorted_ppes:
        labels: list[str] = []
        if int(ppe.id) == int(player_data.active_ppe or -1):
            labels.append("ACTIVE")
        suffix = f" [{' | '.join(labels)}]" if labels else ""
        lines.append(f"PPE #{ppe.id} | Class: {display_class_name(ppe)} | Points: {format_points(ppe.points)}{suffix}")

    await interaction.followup.send(
        f"PPE list for {target.mention_text}\n" + "\n".join(lines),
        ephemeral=True,
    )


async def send_target_season_loot_markdown_followup(
    interaction: discord.Interaction,
    *,
    target: ManagedPlayerTarget,
    player_data: PlayerData,
) -> None:
    items_list = sorted(player_data.unique_items, key=lambda x: (x[0].lower(), x[1]))

    if not items_list:
        await interaction.followup.send(f"{target.display_name} has no season loot tracked yet.", ephemeral=True)
        return

    temp_file_path = create_season_loot_markdown_file(
        player_data.unique_items,
        display_name=target.display_name,
    )
    try:
        await interaction.followup.send(file=discord.File(temp_file_path), ephemeral=True)
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


async def set_target_ppe_penalties(
    interaction: discord.Interaction,
    *,
    user_id: int,
    ppe_id: int,
    pet_level: int | str,
    num_exalts: int | str,
    percent_loot: float | str,
    incombat_reduction: float | str,
) -> tuple[PPEData, dict[str, float], discord.Embed]:
    parsed_inputs, error = parse_penalty_inputs(pet_level, num_exalts, percent_loot, incombat_reduction)
    if error:
        raise ValueError(error)

    assert parsed_inputs is not None

    records = await load_player_records(interaction)
    key = ensure_player_exists(records, user_id)
    player_data = records[key]

    if not player_data.ppes:
        raise LookupError("❌ This player does not have any PPEs.")

    target_ppe = find_ppe_or_raise(player_data, ppe_id)
    guild_config = await load_guild_config(interaction)

    penalty_result = apply_penalties_to_ppe(
        target_ppe,
        pet_level=int(parsed_inputs["pet_level"]),
        num_exalts=int(parsed_inputs["num_exalts"]),
        percent_loot=float(parsed_inputs["percent_loot"]),
        incombat_reduction=float(parsed_inputs["incombat_reduction"]),
        guild_config=guild_config,
    )
    points_breakdown = recompute_ppe_points(target_ppe, guild_config)
    await save_player_records(interaction, records)

    components = penalty_result["components"]
    embed = build_penalty_infographic_embed(
        pet_level=int(parsed_inputs["pet_level"]),
        num_exalts=int(parsed_inputs["num_exalts"]),
        percent_loot=float(parsed_inputs["percent_loot"]),
        incombat_reduction=float(parsed_inputs["incombat_reduction"]),
        pet_penalty=components["Pet Level Penalty"],
        exalt_penalty=components["Exalts Penalty"],
        loot_penalty=components["Loot Boost Penalty"],
        incombat_penalty=components["In-Combat Reduction Penalty"],
        total_points=points_breakdown["total"],
    )

    return target_ppe, points_breakdown, embed


async def delete_all_ppes_for_target(interaction: discord.Interaction, target: ManagedPlayerTarget) -> str:
    await player_manager.delete_all_ppes(interaction, target.user_id)
    cleanup = await clear_member_character_links(interaction, target.user_id)

    cleanup_note = ""
    if cleanup.tokens_updated > 0 or cleanup.pending_file_removed:
        cleanup_note = (
            f" RealmShark cleanup: tokens={cleanup.tokens_updated},"
            f" ppe_mappings={cleanup.ppe_mappings_removed},"
            f" seasonal={cleanup.seasonal_mappings_removed},"
            f" metadata={cleanup.metadata_entries_removed},"
            f" pending_file_removed={cleanup.pending_file_removed}."
        )

    return f"✅ Deleted all PPEs for {target.mention_text}.{cleanup_note}"


async def delete_single_ppe_for_target(interaction: discord.Interaction, target: ManagedPlayerTarget, ppe_id: int) -> str:
    await player_manager.delete_ppe(interaction, target.user_id, ppe_id)
    cleanup = await clear_ppe_character_links(interaction, target.user_id, ppe_id)

    cleanup_note = ""
    if cleanup.ppe_mappings_removed > 0 or cleanup.pending_entries_removed > 0:
        cleanup_note = (
            f" RealmShark cleanup: tokens={cleanup.tokens_updated},"
            f" disconnected_characters={cleanup.ppe_mappings_removed},"
            f" pending_entries_removed={cleanup.pending_entries_removed}."
        )

    return f"✅ Deleted PPE #{ppe_id} for {target.mention_text}.{cleanup_note}"


async def remove_target_from_contest(interaction: discord.Interaction, target: ManagedPlayerTarget) -> str:
    records = await load_player_records(interaction)
    removed_record = int(target.user_id) in records

    team_name = await team_manager.force_remove_player_from_teams(interaction, target.user_id)

    if int(target.user_id) in records:
        del records[int(target.user_id)]

    await save_player_records(interaction, records)

    realmshark_cleanup = await clear_member_character_links(interaction, target.user_id)

    role = _player_role(interaction.guild) if interaction.guild else None
    if target.member and role and role in target.member.roles:
        await target.member.remove_roles(role)

    if team_name and target.member:
        team_role = discord.utils.get(interaction.guild.roles, name=team_name) if interaction.guild else None
        if team_role and team_role in target.member.roles:
            try:
                await target.member.remove_roles(team_role)
            except discord.Forbidden:
                pass

    if not removed_record and not team_name:
        return f"⚠️ No PPE record or team membership found for {target.display_name} ({target.user_id})."

    realmshark_note = ""
    if realmshark_cleanup.tokens_updated > 0 or realmshark_cleanup.pending_file_removed:
        realmshark_note = (
            f" RealmShark links cleaned: tokens={realmshark_cleanup.tokens_updated}"
            f", ppe_mappings={realmshark_cleanup.ppe_mappings_removed}"
            f", seasonal={realmshark_cleanup.seasonal_mappings_removed}"
            f", metadata={realmshark_cleanup.metadata_entries_removed}"
            f", pending_file_removed={realmshark_cleanup.pending_file_removed}"
        )

    if team_name:
        return (
            f"✅ Removed {target.mention_text} from the PPE contest and removed them from team `{team_name}`. "
            f"All PPE data has been deleted.{realmshark_note}"
        )

    return f"✅ Removed {target.mention_text} from the PPE contest. All PPE data has been deleted.{realmshark_note}"


async def add_target_to_contest(interaction: discord.Interaction, target: ManagedPlayerTarget) -> str:
    if not interaction.guild:
        raise ValueError("❌ This command can only be used in a server.")

    if target.member is None:
        raise LookupError("❌ Cannot add by ID because this user is not currently in the server.")

    role = _player_role(interaction.guild)
    if role is None:
        raise LookupError("❌ PPE Player role not found. Create it first.")

    if role not in target.member.roles:
        await target.member.add_roles(role)

    await player_manager.add_player_to_contest(interaction, target.user_id)
    return (
        f"✅ {target.member.mention} has been added to the PPE contest. "
        "Use /ppehelp for bot commands and guidance."
    )


async def give_target_admin_role(interaction: discord.Interaction, target: ManagedPlayerTarget) -> str:
    if not interaction.guild:
        raise ValueError("❌ This command can only be used in a server.")

    if target.member is None:
        raise LookupError("❌ Cannot grant PPE Admin by ID because this user is not currently in the server.")

    role = discord.utils.get(interaction.guild.roles, name="PPE Admin")
    if not role:
        raise LookupError("❌ PPE Admin role not found. Create it first.")

    await target.member.add_roles(role)
    return f"✅ Gave PPE Admin role to {target.member.mention}."


async def send_target_quests_followup(interaction: discord.Interaction, target: ManagedPlayerTarget) -> None:
    records = await load_player_records(interaction)
    key = int(target.user_id)

    if key not in records or not records[key].is_member:
        await interaction.followup.send(
            f"❌ {target.display_name} is not part of the PPE contest.",
            ephemeral=True,
        )
        return

    player_data = records[key]
    config = await load_guild_config(interaction)
    default_reset_limit = config["quest_settings"]["num_resets"]
    if player_data.quest_resets_remaining is None:
        player_data.quest_resets_remaining = default_reset_limit

    try:
        resets_remaining = max(0, int(player_data.quest_resets_remaining))
    except (TypeError, ValueError):
        resets_remaining = default_reset_limit

    regular_target, shiny_target, skin_target = await get_quest_targets(interaction)
    changed = refresh_player_quests(
        player_data,
        target_item_quests=regular_target,
        target_shiny_quests=shiny_target,
        target_skin_quests=skin_target,
    )
    if changed:
        await save_player_records(interaction, records)
    elif player_data.quest_resets_remaining != resets_remaining:
        player_data.quest_resets_remaining = resets_remaining
        await save_player_records(interaction, records)

    quests = player_data.quests

    lines = [
        f"Quest Resets Remaining: {resets_remaining}",
        "",
        "Current Quests:",
        "- Items To Find:",
        *([f"• {item}" for item in quests.current_items] or ["• None"]),
        "",
        "- Shiny Items To Find:",
        *([f"• {item}" for item in quests.current_shinies] or ["• None"]),
        "",
        "- Skins To Find:",
        *([f"• {item}" for item in quests.current_skins] or ["• None"]),
        "",
        "Completed Quests:",
        "- Item Quests Completed:",
        *([f"• {item}" for item in quests.completed_items] or ["• None"]),
        "",
        "- Shiny Quests Completed:",
        *([f"• {item}" for item in quests.completed_shinies] or ["• None"]),
        "",
        "- Skins Quests Completed:",
        *([f"• {item}" for item in quests.completed_skins] or ["• None"]),
    ]

    pages = chunk_lines_to_pages(lines, 3900)
    embeds: list[discord.Embed] = []
    for page_num, page_lines in enumerate(pages, start=1):
        embed = discord.Embed(
            title=f"Quests for {target.display_name}",
            color=discord.Color.gold(),
            description="\n".join(page_lines),
        )
        if len(pages) > 1:
            embed.set_footer(text=f"Page {page_num}/{len(pages)}")
        embeds.append(embed)

    if len(embeds) == 1:
        await interaction.followup.send(embed=embeds[0], ephemeral=False)
    else:
        view = LootPaginationView(embeds=embeds, user_id=interaction.user.id)
        await interaction.followup.send(embed=embeds[0], view=view, ephemeral=False)


async def send_target_loot_markdown_followup(interaction: discord.Interaction, *, ppe: PPEData) -> None:
    from utils.loot_table_md_builder import create_loot_markdown_file

    temp_file_path = create_loot_markdown_file(ppe)
    try:
        await interaction.followup.send(file=discord.File(temp_file_path), ephemeral=True)
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


def character_embed_for_target(
    *,
    target: ManagedPlayerTarget,
    player_data: PlayerData,
    ppe: PPEData,
    index: int,
    total: int,
    is_active: bool,
    is_best: bool,
    is_realmshark_connected: bool,
    guild_config: dict | None,
) -> discord.Embed:
    proxy_user = target.member if target.member is not None else discord.Object(id=target.user_id)
    embed = build_character_embed(
        user=proxy_user,
        player_data=player_data,
        ppe=ppe,
        index=index,
        total=total,
        is_active=is_active,
        is_best=is_best,
        is_realmshark_connected=is_realmshark_connected,
        guild_config=guild_config,
    )
    embed.description = f"{target.display_name}'s Character Panel\nCharacter {index}/{total}"
    return embed


async def realmshark_connected_ppe_ids(interaction: discord.Interaction, user_id: int) -> set[int]:
    from menus.myinfo.common import realmshark_connected_ppe_ids as myinfo_connected_ids

    return await myinfo_connected_ids(interaction, user_id)


__all__ = [
    "ManagedPlayerTarget",
    "active_ppe_for_player",
    "add_target_to_contest",
    "character_embed_for_target",
    "close_manageplayer_menu",
    "delete_all_ppes_for_target",
    "delete_single_ppe_for_target",
    "find_ppe_or_raise",
    "give_target_admin_role",
    "load_target_player_data",
    "open_manageplayer_home",
    "open_manageplayer_menu",
    "penalty_input_defaults",
    "realmshark_connected_ppe_ids",
    "remove_target_from_contest",
    "send_followup_text",
    "send_target_loot_markdown_followup",
    "send_target_ppe_list_markdown_followup",
    "send_target_quests_followup",
    "send_target_season_loot_markdown_followup",
    "set_target_ppe_penalties",
    "target_home_embed",
]

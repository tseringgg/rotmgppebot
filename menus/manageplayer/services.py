"""Business operations for the /manageplayer menu."""

from __future__ import annotations

import discord

from dataclass import PPEData, PlayerData
from menus.manageplayer.targets import ManagedPlayerTarget, admin_role, player_role
from utils.guild_config import get_quest_targets, load_guild_config
from utils.pagination import LootPaginationView, chunk_lines_to_pages
from utils.player_manager import player_manager
from utils.player_records import ensure_player_exists, load_player_records, save_player_records
from utils.realmshark_cleanup import clear_member_character_links, clear_ppe_character_links
from utils.quest_manager import refresh_player_quests
from utils.team_manager import team_manager


async def load_target_player_data(interaction: discord.Interaction, target_user_id: int) -> PlayerData:
    records = await load_player_records(interaction)
    key = ensure_player_exists(records, target_user_id)
    return records[key]


def find_ppe_or_raise(player_data: PlayerData, ppe_id: int) -> PPEData:
    for ppe in player_data.ppes:
        if int(ppe.id) == int(ppe_id):
            return ppe
    raise LookupError(f"PPE #{ppe_id} not found.")


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
        global_quests={
            "enabled": bool(config["quest_settings"].get("use_global_quests", False)),
            "regular": list(config["quest_settings"].get("global_regular_quests", [])),
            "shiny": list(config["quest_settings"].get("global_shiny_quests", [])),
            "skin": list(config["quest_settings"].get("global_skin_quests", [])),
        },
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

    role = player_role(interaction.guild) if interaction.guild else None
    if target.member and role and role in target.member.roles:
        await target.member.remove_roles(role)

    # Also remove PPE admin role if they have it
    if target.member and interaction.guild:
        admin_role_obj = admin_role(interaction.guild)
        if admin_role_obj and admin_role_obj in target.member.roles:
            try:
                await target.member.remove_roles(admin_role_obj)
            except discord.Forbidden:
                pass

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

    role = player_role(interaction.guild)
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

    role = admin_role(interaction.guild)
    if not role:
        raise LookupError("❌ PPE Admin role not found. Create it first.")

    await target.member.add_roles(role)
    return f"✅ Gave PPE Admin role to {target.member.mention}."


async def remove_target_admin_role(interaction: discord.Interaction, target: ManagedPlayerTarget) -> str:
    if not interaction.guild:
        raise ValueError("❌ This command can only be used in a server.")

    if target.member is None:
        raise LookupError("❌ Cannot remove PPE Admin by ID because this user is not currently in the server.")

    role = admin_role(interaction.guild)
    if not role:
        raise LookupError("❌ PPE Admin role not found. Create it first.")

    await target.member.remove_roles(role)
    return f"✅ Removed PPE Admin role from {target.member.mention}."


async def assign_target_to_team(
    interaction: discord.Interaction,
    target: ManagedPlayerTarget,
    team_name: str,
) -> str:
    team = await team_manager.add_player_to_team(interaction, target.user_id, team_name)

    if target.member and interaction.guild:
        team_role = discord.utils.get(interaction.guild.roles, name=team.name)
        if team_role is None:
            team_role = await interaction.guild.create_role(
                name=team.name,
                reason=f"PPE Team role for {team.name}",
            )
        await target.member.add_roles(team_role)

    return f"✅ Added {target.mention_text} to team `{team.name}`."


async def remove_target_from_team(interaction: discord.Interaction, target: ManagedPlayerTarget) -> str:
    removed_team_name = await team_manager.force_remove_player_from_teams(interaction, target.user_id)
    if not removed_team_name:
        return f"⚠️ {target.display_name} is not on any team."

    if target.member and interaction.guild:
        team_role = discord.utils.get(interaction.guild.roles, name=removed_team_name)
        if team_role and team_role in target.member.roles:
            try:
                await target.member.remove_roles(team_role)
            except discord.Forbidden:
                pass

    return f"✅ Removed {target.mention_text} from team `{removed_team_name}`."


def target_has_admin_role(interaction: discord.Interaction, target: ManagedPlayerTarget) -> bool:
    if not interaction.guild or not target.member:
        return False
    role = admin_role(interaction.guild)
    if role is None:
        return False
    return role in target.member.roles


__all__ = [
    "add_target_to_contest",
    "delete_all_ppes_for_target",
    "delete_single_ppe_for_target",
    "find_ppe_or_raise",
    "give_target_admin_role",
    "load_target_player_data",
    "assign_target_to_team",
    "remove_target_from_team",
    "remove_target_admin_role",
    "remove_target_from_contest",
    "send_target_quests_followup",
    "target_has_admin_role",
]

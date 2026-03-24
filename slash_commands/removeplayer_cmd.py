

import discord

from utils.player_records import load_player_records, save_player_records
from utils.realmshark_cleanup import clear_member_character_links
from utils.team_manager import team_manager


async def command(
    interaction: discord.Interaction,
    member: discord.Member | None = None,
    user_id: str | None = None
):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")

    if member is None and not user_id:
        return await interaction.response.send_message("❌ Provide either a server member or a Discord user ID.", ephemeral=True)
    if member is not None and user_id:
        return await interaction.response.send_message("❌ Provide only one target: member OR user_id.", ephemeral=True)

    target_member = member
    target_id: int
    target_name: str

    if member is not None:
        target_id = member.id
        target_name = member.display_name
    else:
        if not user_id.isdigit():
            return await interaction.response.send_message("❌ `user_id` must be a numeric Discord ID.", ephemeral=True)
        target_id = int(user_id)
        fetched_member = interaction.guild.get_member(target_id)
        if fetched_member is None:
            try:
                fetched_member = await interaction.guild.fetch_member(target_id)
            except Exception:
                fetched_member = None
        target_member = fetched_member
        target_name = fetched_member.display_name if fetched_member else f"User {target_id}"
    
    role = discord.utils.get(interaction.guild.roles, name="PPE Player")
    if not role:
        return await interaction.response.send_message("❌ PPE Player role not found. Create it first.")
    
    try:
        # Remove player from team first (this removes them from team.members and team_name)
        team_name = await team_manager.force_remove_player_from_teams(interaction, target_id)
        
        # Remove all PPE characters and associated data by deleting the record entry.
        records = await load_player_records(interaction)
        key = target_id
        removed_record = key in records
        
        if key in records:
            del records[key]
        
        await save_player_records(interaction, records)

        # Also sever RealmShark character mappings/pending state for this user.
        realmshark_cleanup = await clear_member_character_links(interaction, target_id)

        # Remove the PPE Player role if they still exist in the guild.
        if target_member and role in target_member.roles:
            await target_member.remove_roles(role)
        
        # Remove the team role if they were on a team
        if team_name and target_member:
            try:
                team_role = discord.utils.get(interaction.guild.roles, name=team_name)
                if team_role and team_role in target_member.roles:
                    await target_member.remove_roles(team_role)
            except discord.Forbidden:
                pass  # Silently ignore if we can't remove the role
            except Exception:
                pass  # Silently ignore any other errors

        if not removed_record and not team_name:
            return await interaction.response.send_message(
                f"⚠️ No PPE record or team membership found for `{target_name}` (`{target_id}`).",
                ephemeral=True
            )

        realmshark_note = ""
        if (
            realmshark_cleanup.tokens_updated > 0
            or realmshark_cleanup.pending_file_removed
        ):
            realmshark_note = (
                f" RealmShark links cleaned: tokens=`{realmshark_cleanup.tokens_updated}`"
                f", ppe_mappings=`{realmshark_cleanup.ppe_mappings_removed}`"
                f", seasonal=`{realmshark_cleanup.seasonal_mappings_removed}`"
                f", metadata=`{realmshark_cleanup.metadata_entries_removed}`"
                f", pending_file_removed=`{realmshark_cleanup.pending_file_removed}`"
            )

        return await interaction.response.send_message(
            f"✅ Removed `{target_name}` (`{target_id}`) from the PPE contest. All PPE data has been deleted.{realmshark_note}"
        )
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to manage that role. Move my bot role higher in the hierarchy.")
    except Exception as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
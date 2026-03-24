

import discord

from utils.player_manager import player_manager
from utils.realmshark_cleanup import clear_member_character_links


async def command(interaction: discord.Interaction, member: discord.Member):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    
    try:
        await player_manager.delete_all_ppes(interaction, member.id)
        cleanup = await clear_member_character_links(interaction, member.id)

        cleanup_note = ""
        if cleanup.tokens_updated > 0 or cleanup.pending_file_removed:
            cleanup_note = (
                f" RealmShark cleanup: tokens=`{cleanup.tokens_updated}`,"
                f" ppe_mappings=`{cleanup.ppe_mappings_removed}`,"
                f" seasonal=`{cleanup.seasonal_mappings_removed}`,"
                f" metadata=`{cleanup.metadata_entries_removed}`,"
                f" pending_file_removed=`{cleanup.pending_file_removed}`."
            )

        await interaction.response.send_message(
            f"✅ All of {member.display_name}'s PPEs have been deleted.{cleanup_note}"
        )
    except (ValueError, KeyError, LookupError) as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
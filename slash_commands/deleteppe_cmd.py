import discord

from utils.player_manager import player_manager
from utils.realmshark_cleanup import clear_ppe_character_links


async def command(interaction: discord.Interaction, member: discord.Member, ppe_id: int):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    
    try:
        await player_manager.delete_ppe(interaction, member.id, ppe_id)
        cleanup = await clear_ppe_character_links(interaction, member.id, ppe_id)

        cleanup_note = ""
        if cleanup.ppe_mappings_removed > 0 or cleanup.pending_entries_removed > 0:
            cleanup_note = (
                f" RealmShark cleanup: tokens=`{cleanup.tokens_updated}`,"
                f" disconnected_characters=`{cleanup.ppe_mappings_removed}`,"
                f" pending_entries_removed=`{cleanup.pending_entries_removed}`."
            )

        await interaction.response.send_message(
            f"✅ PPE #{ppe_id} of {member.display_name} has been deleted.{cleanup_note}"
        )
    except (ValueError, KeyError, LookupError) as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
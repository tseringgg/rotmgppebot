

import discord

from utils.player_manager import player_manager


async def command(interaction: discord.Interaction, member: discord.Member, ppe_id: int, amount: float):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    
    try:
        points_added, ppe_id, total_points = await player_manager.add_points_to_member(interaction, member.id, ppe_id, amount)
        await interaction.response.send_message(
            f"✅ Added `{points_added:.1f}` points to `{member.display_name}`'s active PPE (PPE #{ppe_id}).\n"
            f"`New total:` {total_points:.1f} points."
        )
    except (ValueError, KeyError, LookupError) as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
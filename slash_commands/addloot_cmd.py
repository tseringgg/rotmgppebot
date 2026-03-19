import discord

from utils.embed_builders import build_loot_embed
from utils.loot_data import LOOT
from utils.player_manager import player_manager
from utils.calc_points import calc_points, load_loot_points
from utils.player_records import get_active_ppe_of_user


async def command(
        interaction: discord.Interaction,
        item_name: str,
        divine: bool = False,
        shiny: bool = False
    ):
    if item_name not in LOOT:
        return await interaction.response.send_message(
            f"❌ `{item_name}` is not a recognized item name.\n"
            f"Use the autocomplete suggestions to select a valid item.",
            ephemeral=True
        )
    
    # Validate that shiny variant exists in database
    if shiny:
        loot_points = load_loot_points()
        shiny_item_name = f"{item_name} (shiny)"
        if shiny_item_name not in loot_points:
            return await interaction.response.send_message(
                f"❌ Shiny variant of `{item_name}` is not currently in bot.",
                ephemeral=True
            )
    
    try:
        points = calc_points(item_name, divine, shiny)
        ppe_id = (await get_active_ppe_of_user(interaction)).id
        user = interaction.user
        if not isinstance(user, discord.Member):
            raise ValueError("❌ Could not retrieve your member information.")
        final_key, points_added, active_ppe, quest_update = await player_manager.add_loot_and_points(
            interaction, user=user, ppe_id=ppe_id, item_name=item_name, divine=divine, shiny=shiny, points=points
        )
        embed = await build_loot_embed(active_ppe, user_id=user.id, recently_added=final_key)

        quest_lines = []
        for completed_item in quest_update.get("completed_items", []):
            quest_lines.append(f"✅ Item quest completed: **{completed_item}**")
        for completed_skin in quest_update.get("completed_skins", []):
            quest_lines.append(f"✅ Skin quest completed: **{completed_skin}**")

        if quest_lines:
            quest_lines.append("Use `/myquests` to view your updated quest list.")
        
        await interaction.response.send_message(
            content=f"> ✅ Added **{final_key}** to your active PPE for {points_added} points.",
            ephemeral=False
        )
        await interaction.followup.send(
            content=f"Your active PPE now has **{active_ppe.points} total points**.",
            view=embed,
            embed=embed.embeds[0],
            ephemeral=True
        )

        if quest_lines:
            await interaction.followup.send("\n".join(quest_lines), ephemeral=True)
    except (ValueError, KeyError, LookupError) as e:
        return await interaction.response.send_message(str(e), ephemeral=True)

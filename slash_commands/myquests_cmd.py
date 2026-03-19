import discord

from utils.player_records import load_player_records, save_player_records, ensure_player_exists
from utils.quest_manager import refresh_player_quests
from utils.pagination import chunk_lines_to_pages, LootPaginationView


async def command(interaction: discord.Interaction):
    try:
        records = await load_player_records(interaction)
        user_id = interaction.user.id
        key = ensure_player_exists(records, user_id)

        if key not in records or not records[key].is_member:
            raise KeyError("❌ You're not part of the PPE contest.")

        player_data = records[key]

        changed = refresh_player_quests(player_data)
        if changed:
            await save_player_records(interaction, records)

        quests = player_data.quests

        lines = [
            "**Current Quests:**",
            "- Items To Find:",
            *([f"• {item}" for item in quests.current_items] or ["• None"]),
            "",
            "- Skins To Find:",
            *([f"• {item}" for item in quests.current_skins] or ["• None"]),
            "",
            "**Completed Quests:**",
            "- Item Quests Completed:",
            *([f"• {item}" for item in quests.completed_items] or ["• None"]),
            "",
            "- Skins Quests Completed:",
            *([f"• {item}" for item in quests.completed_skins] or ["• None"]),
        ]

        pages = chunk_lines_to_pages(lines, 3900)
        embeds = []
        for page_num, page_lines in enumerate(pages, start=1):
            embed = discord.Embed(
                title="📜 My Quests",
                color=discord.Color.blurple(),
                description="\n".join(page_lines),
            )
            if len(pages) > 1:
                embed.set_footer(text=f"Page {page_num}/{len(pages)}")
            embeds.append(embed)

        if len(embeds) == 1:
            await interaction.response.send_message(embed=embeds[0], ephemeral=True)
        else:
            view = LootPaginationView(embeds=embeds, user_id=user_id)
            await interaction.response.send_message(embed=embeds[0], view=view, ephemeral=True)

    except (ValueError, KeyError, LookupError) as e:
        return await interaction.response.send_message(str(e), ephemeral=True)

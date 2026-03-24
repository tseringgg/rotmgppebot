import discord

from utils.player_records import load_player_records, save_player_records
from utils.quest_manager import refresh_player_quests
from utils.pagination import chunk_lines_to_pages, LootPaginationView
from utils.guild_config import get_quest_targets, load_guild_config


async def command(interaction: discord.Interaction, member: discord.Member):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)

    try:
        records = await load_player_records(interaction)
        key = member.id

        if key not in records or not records[key].is_member:
            return await interaction.response.send_message(
                f"❌ {member.display_name} is not part of the PPE contest.",
                ephemeral=True,
            )

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
            f"**Quest Resets Remaining:** {resets_remaining}",
            "",
            "**Current Quests:**",
            "- Items To Find:",
            *([f"• {item}" for item in quests.current_items] or ["• None"]),
            "",
            "- Shiny Items To Find:",
            *([f"• {item}" for item in quests.current_shinies] or ["• None"]),
            "",
            "- Skins To Find:",
            *([f"• {item}" for item in quests.current_skins] or ["• None"]),
            "",
            "**Completed Quests:**",
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
        embeds = []
        for page_num, page_lines in enumerate(pages, start=1):
            embed = discord.Embed(
                title=f"📜 Quests for {member.display_name}",
                color=discord.Color.gold(),
                description="\n".join(page_lines),
            )
            if len(pages) > 1:
                embed.set_footer(text=f"Page {page_num}/{len(pages)}")
            embeds.append(embed)

        if len(embeds) == 1:
            await interaction.response.send_message(embed=embeds[0], ephemeral=True)
        else:
            view = LootPaginationView(embeds=embeds, user_id=interaction.user.id)
            await interaction.response.send_message(embed=embeds[0], view=view, ephemeral=True)

    except (ValueError, KeyError, LookupError) as e:
        return await interaction.response.send_message(str(e), ephemeral=True)

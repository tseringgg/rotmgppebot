import discord
from utils.player_records import load_player_records, ensure_player_exists
from utils.pagination import chunk_lines_to_pages, LootPaginationView


async def command(interaction: discord.Interaction):
    try:
        records = await load_player_records(interaction)
        user_id = interaction.user.id
        key = ensure_player_exists(records, user_id)
        
        # Check if user is member
        if key not in records or not records[key].is_member:
            raise KeyError("❌ You're not part of the PPE contest.")
        
        player_data = records[key]
        
        # Build sorted list of items
        items_list = sorted(player_data.unique_items, key=lambda x: (x[0].lower(), x[1]))
        
        if not items_list:
            return await interaction.response.send_message(
                "You haven't collected any season loot yet!\n"
                "Use `/addseasonloot` to start tracking your unique items.",
                ephemeral=True
            )
        
        # Build lines for display
        lines = []
        for item_name, shiny in items_list:
            shiny_marker = " ✨" if shiny else ""
            lines.append(f"• {item_name}{shiny_marker}")
        
        # Add total count at the end
        total_count = len(items_list)
        lines.append(f"\n**Total: {total_count} unique items**")
        
        # Paginate if necessary (Discord embed description limit is 4096 chars)
        MAX_CHARS = 4000  # Leave some buffer
        pages = chunk_lines_to_pages(lines, MAX_CHARS)
        
        # Create embeds
        embeds = []
        for page_num, page_lines in enumerate(pages, start=1):
            embed = discord.Embed(
                title=f"Your Season Loot Collection",
                description="\n".join(page_lines),
                color=discord.Color.gold()
            )
            if len(pages) > 1:
                embed.set_footer(text=f"Page {page_num}/{len(pages)}")
            embeds.append(embed)
        
        # Send with pagination if needed
        if len(embeds) == 1:
            await interaction.response.send_message(embed=embeds[0], ephemeral=True)
        else:
            view = LootPaginationView(embeds=embeds, user_id=user_id)
            await interaction.response.send_message(
                embed=embeds[0],
                view=view,
                ephemeral=True
            )
        
    except (ValueError, KeyError, LookupError) as e:
        return await interaction.response.send_message(str(e), ephemeral=True)

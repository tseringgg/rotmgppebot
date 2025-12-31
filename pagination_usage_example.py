"""
Example usage of the loot embed pagination system.

This shows how to integrate the pagination into your Discord bot commands.
You can adapt this pattern to your existing command structure.
"""
import discord
from discord.ext import commands
from utils.embed_builders import build_loot_embeds, build_loot_embed
from utils.pagination import LootPaginationView


class LootCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @discord.app_command.command(name="loot", description="View your PPE loot")
    async def loot_command(self, interaction: discord.Interaction):
        # Your existing logic to get active_ppe would go here
        # active_ppe = get_user_active_ppe(interaction.user.id)
        
        # For demonstration, assuming you have active_ppe
        # active_ppe = ... your existing PPE data retrieval logic
        
        # Build the paginated embeds
        embeds = build_loot_embeds(active_ppe, recently_added="")  # or pass recently_added item
        
        if len(embeds) == 1:
            # Single page - send normally without pagination
            await interaction.response.send_message(embed=embeds[0])
        else:
            # Multiple pages - send with pagination view
            view = LootPaginationView(embeds, interaction.user.id)
            await interaction.response.send_message(embed=embeds[0], view=view)
            # Set the message reference for timeout handling
            view.message = await interaction.original_response()
    
    @commands.command(name="loot")  # For prefix commands
    async def loot_prefix_command(self, ctx):
        # Your existing logic to get active_ppe would go here
        # active_ppe = get_user_active_ppe(ctx.author.id)
        
        # Build the paginated embeds
        embeds = build_loot_embeds(active_ppe, recently_added="")
        
        if len(embeds) == 1:
            # Single page - send normally
            await ctx.send(embed=embeds[0])
        else:
            # Multiple pages - send with pagination
            view = LootPaginationView(embeds, ctx.author.id)
            message = await ctx.send(embed=embeds[0], view=view)
            # Set the message reference for timeout handling
            view.message = message


# Alternative usage in existing command handlers:
async def handle_add_loot_command(interaction_or_ctx, item_name, active_ppe):
    """Example of how to use pagination when adding loot."""
    # Your existing add loot logic here would go before this
    # add_loot_to_ppe(user_id, item_name, ...)
    # active_ppe = get_updated_ppe_data(user_id)  # Get fresh data
    
    # Build embeds with recently_added highlighting
    embeds = build_loot_embeds(active_ppe, recently_added=item_name)
    
    # Determine user_id and send method based on interaction type
    if hasattr(interaction_or_ctx, 'response'):  # Slash command
        user_id = interaction_or_ctx.user.id
        
        if len(embeds) == 1:
            await interaction_or_ctx.response.send_message(embed=embeds[0])
        else:
            view = LootPaginationView(embeds, user_id)
            await interaction_or_ctx.response.send_message(embed=embeds[0], view=view)
            view.message = await interaction_or_ctx.original_response()
            
    else:  # Prefix command
        user_id = interaction_or_ctx.author.id
        
        if len(embeds) == 1:
            await interaction_or_ctx.send(embed=embeds[0])
        else:
            view = LootPaginationView(embeds, user_id)
            message = await interaction_or_ctx.send(embed=embeds[0], view=view)
            view.message = message


# You can also still use the original single-embed function if needed
# from utils.embed_builders import build_loot_embed  # Original function still available


"""
Usage Pattern Summary:

1. For commands that might need pagination:
   ```python
   embeds = build_loot_embeds(active_ppe, recently_added="item_name")
   
   if len(embeds) == 1:
       await ctx.send(embed=embeds[0])  # No pagination needed
   else:
       view = LootPaginationView(embeds, ctx.author.id)
       message = await ctx.send(embed=embeds[0], view=view)
       view.message = message  # Important for timeout handling
   ```

2. For existing code that uses build_loot_embed():
   - Keep using it as normal, no changes needed
   - Or gradually migrate to build_loot_embeds() for pagination support

3. The pagination automatically handles:
   - Splitting long lists into manageable pages
   - Button state management (disabled on first/last pages)  
   - User permission checking ("Not your menu!")
   - 120-second timeout with button disabling
   - Preserving all your existing formatting
"""
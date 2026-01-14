import json
import discord
from utils.player_records import load_player_records, save_player_records


async def command(interaction: discord.Interaction):
    """
    Migrate all player records to normalize apostrophes in item names.
    Converts curly/smart apostrophes (U+2019, U+2018) to regular ones (U+0027).
    
    Admin only command.
    Safely uses the same data loading/saving as other admin commands.
    """
    
    if not interaction.guild:
        return await interaction.response.send_message(
            "❌ This command can only be used in a server.",
            ephemeral=True
        )
    
    try:
        # Defer response since this might take a moment
        await interaction.response.defer()
        
        # Load player records using the safe utility (same as /refreshallpoints)
        records = await load_player_records(interaction)
        
        changes_made = {}
        total_items_fixed = 0
        
        # Iterate through all players (safe iteration)
        for user_key, player_data in records.items():
            # Normalize season loot (unique_items)
            if player_data.unique_items:
                normalized_items = set()
                
                for item_tuple in player_data.unique_items:
                    item_name, shiny = item_tuple
                    
                    # Normalize apostrophes: curly → regular
                    original_name = item_name
                    normalized_name = item_name.replace('\u2019', "'").replace('\u2018', "'")
                    
                    if original_name != normalized_name:
                        total_items_fixed += 1
                        if user_key not in changes_made:
                            changes_made[user_key] = []
                        changes_made[user_key].append(original_name)
                    
                    # Add normalized tuple to set
                    normalized_items.add((normalized_name, shiny))
                
                # Update the player's season items
                player_data.unique_items = normalized_items
            
            # Normalize regular PPE loot
            if player_data.ppes:
                for ppe in player_data.ppes:
                    if ppe.loot:
                        for loot_item in ppe.loot:
                            item_name = loot_item.item_name
                            
                            # Normalize apostrophes: curly → regular
                            original_name = item_name
                            normalized_name = item_name.replace('\u2019', "'").replace('\u2018', "'")
                            
                            if original_name != normalized_name:
                                total_items_fixed += 1
                                if user_key not in changes_made:
                                    changes_made[user_key] = []
                                changes_made[user_key].append(original_name)
                            
                            # Update the loot item's name
                            loot_item.item_name = normalized_name
        
        # Save using the safe utility (same as /refreshallpoints)
        await save_player_records(interaction, records)
        
        # Build response
        embed = discord.Embed(
            title="✅ Apostrophe Migration Complete",
            color=discord.Color.green() if total_items_fixed > 0 else discord.Color.greyple()
        )
        
        embed.add_field(
            name="📊 Summary",
            value=f"**Total items fixed:** {total_items_fixed}\n**Players affected:** {len(changes_made)}",
            inline=False
        )
        
        if total_items_fixed == 0:
            embed.add_field(
                name="ℹ️ Status",
                value="All apostrophes were already normalized - no changes needed!",
                inline=False
            )
        else:
            # Show which items were fixed
            affected_items = set()
            for items in changes_made.values():
                affected_items.update(items)
            
            items_list = "\n".join(sorted(affected_items))
            if len(items_list) > 1024:
                items_list = "\n".join(sorted(affected_items)[:10]) + f"\n... and {len(affected_items) - 10} more"
            
            embed.add_field(
                name="🔧 Items Fixed",
                value=items_list,
                inline=False
            )
        
        embed.set_footer(text="All apostrophes converted to regular (U+0027)")
        
        await interaction.followup.send(embed=embed)
        
    except json.JSONDecodeError as e:
        await interaction.followup.send(
            f"❌ Error reading player records: Invalid JSON format.\n{str(e)}",
            ephemeral=True
        )
    except FileNotFoundError:
        await interaction.followup.send(
            f"❌ No player records found yet for this guild. Nothing to migrate.",
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(
            f"❌ Unexpected error during migration: {str(e)}",
            ephemeral=True
        )

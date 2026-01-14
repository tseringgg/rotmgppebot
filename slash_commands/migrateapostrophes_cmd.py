import discord
import json
import os

PLAYER_RECORD_FILE = "./guild_loot_records.json"


async def command(interaction: discord.Interaction):
    """
    Migrate all player records to normalize apostrophes in item names.
    Converts curly/smart apostrophes (U+2019, U+2018) to regular ones (U+0027).
    
    Admin only command.
    """
    
    if not os.path.exists(PLAYER_RECORD_FILE):
        return await interaction.response.send_message(
            "⚠️ No player records found yet. Nothing to migrate.",
            ephemeral=True
        )
    
    try:
        # Defer response since this might take a moment
        await interaction.response.defer()
        
        # Load player records
        with open(PLAYER_RECORD_FILE, 'r', encoding='utf-8') as f:
            records = json.load(f)
        
        changes_made = {}
        total_items_fixed = 0
        
        # Process each player's records
        for user_key, player_data in records.items():
            if 'unique_items' not in player_data:
                continue
            
            original_items = player_data['unique_items']
            normalized_items = []
            player_changes = 0
            
            for item in original_items:
                item_name, shiny = item[0], item[1]
                
                # Normalize apostrophes: curly → regular
                original_name = item_name
                normalized_name = item_name.replace('\u2019', "'").replace('\u2018', "'")
                
                if original_name != normalized_name:
                    player_changes += 1
                    total_items_fixed += 1
                    if user_key not in changes_made:
                        changes_made[user_key] = []
                    changes_made[user_key].append(original_name)
                
                normalized_items.append([normalized_name, shiny])
            
            # Update the player's items
            player_data['unique_items'] = normalized_items
        
        # Save the cleaned records back
        with open(PLAYER_RECORD_FILE, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        
        # Build response
        embed = discord.Embed(
            title="✅ Apostrophe Migration Complete",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="📊 Summary",
            value=f"**Total items fixed:** {total_items_fixed}\n**Players affected:** {len(changes_made)}",
            inline=False
        )
        
        if changes_made:
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
        else:
            embed.add_field(
                name="ℹ️ Status",
                value="All apostrophes were already normalized - no changes needed!",
                inline=False
            )
        
        embed.set_footer(text="All apostrophes converted to regular (U+0027)")
        
        await interaction.followup.send(embed=embed)
        
    except json.JSONDecodeError as e:
        await interaction.followup.send(
            f"❌ Error reading player records: Invalid JSON format.\n{str(e)}",
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(
            f"❌ Unexpected error during migration: {str(e)}",
            ephemeral=True
        )

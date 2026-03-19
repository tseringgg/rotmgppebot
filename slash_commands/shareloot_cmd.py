from discord import app_commands
import discord
from utils.player_records import get_active_ppe_of_user
from utils.role_checks import require_ppe_roles
import csv
from PIL import Image
import os

async def command(interaction: discord.Interaction, include_skins: bool = False, include_limited: bool = False):
    """
    Generate a personalized loot image showing the player's active PPE loot.
    
    Args:
        include_skins: Include skin items in the loot background
        include_limited: Include limited items in the loot background
    """
    
    try:
        # Get active PPE using the same method as other commands
        active_ppe = await get_active_ppe_of_user(interaction)
    except (ValueError, KeyError) as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
    
    try:
        # Determine which variant to use based on parameters
        if include_skins and include_limited:
            variant = "all"
        elif include_skins:
            variant = "normal_skins"
        elif include_limited:
            variant = "normal_limited"
        else:
            variant = "normal"
        
        # Construct file paths
        sprite_csv = f"sprite_positions_{variant}.csv"
        background_file = f"loot_background_{variant}.png"
        
        # Load sprite positions mapping
        if not os.path.exists(sprite_csv):
            await interaction.response.send_message(f"❌ Sprite mapping not found! ({sprite_csv})", ephemeral=True)
            return
        
        sprite_positions = {}
        sprite_images = {}
        
        with open(sprite_csv, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                sprite_positions[row['item_name']] = {
                    'pixel_x': int(row['pixel_x']),
                    'pixel_y': int(row['pixel_y'])
                }
        
        # Load background image
        if not os.path.exists(background_file):
            await interaction.response.send_message(f"❌ Loot background not found! ({background_file})", ephemeral=True)
            return
        
        # Create a copy of the background for this player
        background = Image.open(background_file).copy()
        
        # Load original sprite images
        dungeons_path = "dungeons"
        ignored_folders = {"Forging", "Tiered Garbage", "_misc"}
        
        # Find and load all original sprites
        import glob
        pattern = os.path.join(dungeons_path, "**", "*.png")
        all_png_files = glob.glob(pattern, recursive=True)
        
        for png_file in all_png_files:
            # Filter out ignored folders
            rel_path = os.path.relpath(png_file, dungeons_path)
            folder_parts = rel_path.split(os.sep)
            
            if any(part in ignored_folders for part in folder_parts):
                continue
            
            item_name = os.path.splitext(os.path.basename(png_file))[0]
            # Normalize apostrophes to match CSV data
            item_name = item_name.replace("'", "'")
            try:
                img = Image.open(png_file)
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                
                # Resize to 40x40
                if img.size != (40, 40):
                    img = img.resize((40, 40), Image.Resampling.LANCZOS)
                
                sprite_images[item_name] = img
            except Exception as e:
                print(f"Error loading sprite {png_file}: {e}")
        
        # Defer response since this might take a moment
        await interaction.response.defer()
        
        # Count how many items we're placing
        items_placed = 0
        items_not_found = []
        
        # Place player's loot on the background
        for loot_item in active_ppe.loot:
            item_name = loot_item.item_name
            # Normalize apostrophes
            item_name = item_name.replace("'", "'")
            
            # Check if item is marked as shiny
            if loot_item.shiny:
                shiny_name = f"{item_name} (shiny)"
                # Check if shiny variant exists
                if shiny_name in sprite_positions and shiny_name in sprite_images:
                    # Shiny sprite exists, use it
                    pos = sprite_positions[shiny_name]
                    sprite = sprite_images[shiny_name]
                    background.paste(sprite, (pos['pixel_x'], pos['pixel_y']), sprite)
                    items_placed += 1
                else:
                    # Shiny sprite is missing
                    items_not_found.append(f"{item_name} (shiny)")
            else:
                # Non-shiny item
                if item_name in sprite_positions and item_name in sprite_images:
                    pos = sprite_positions[item_name]
                    sprite = sprite_images[item_name]
                    background.paste(sprite, (pos['pixel_x'], pos['pixel_y']), sprite)
                    items_placed += 1
                else:
                    items_not_found.append(item_name)
        
        # Generate filename
        username = interaction.user.display_name.replace(" ", "_")
        # Remove special characters that might cause file issues
        username = "".join(c for c in username if c.isalnum() or c in "_-")
        filename = f"{username}_ppe{active_ppe.id}_loot.png"
        
        # Save the personalized loot image
        background.save(filename, "PNG")
        
        # Create embed with results
        embed = discord.Embed(
            title="🎒 PPE Loot Share",
            color=0x00ff00,
            description=f"**{active_ppe.name}** PPE #{active_ppe.id}"
        )
        
        embed.add_field(
            name="📊 Summary",
            value=f"**Items Placed:** {items_placed}\n**Total Loot:** {len(active_ppe.loot)}\n**Points:** {active_ppe.points:.1f}",
            inline=True
        )
        
        if items_not_found:
            not_found_text = ", ".join(items_not_found[:5])
            if len(items_not_found) > 5:
                not_found_text += f" (+{len(items_not_found) - 5} more)"
            embed.add_field(
                name="⚠️ Items Not Found",
                value=not_found_text,
                inline=False
            )
        
        embed.set_footer(text=f"Generated for {interaction.user.display_name}")
        
        # Send the image
        with open(filename, 'rb') as f:
            file = discord.File(f, filename=filename)
            await interaction.followup.send(embed=embed, file=file)
        
        # Clean up - remove the generated file
        try:
            os.remove(filename)
        except:
            pass
        
        # Clean up sprite images
        for img in sprite_images.values():
            img.close()
        background.close()
    except Exception as e:
        print(f"Error in shareloot command: {e}")
        if not interaction.response.is_done():
            await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)
from discord import app_commands
import discord
from utils.player_records import get_active_ppe_of_user
from utils.role_checks import require_ppe_roles
import csv
from PIL import Image
import os

async def command(interaction: discord.Interaction):
    """
    Generate a personalized loot image showing the player's active PPE loot.
    """
    
    try:
        # Get active PPE using the same method as other commands
        active_ppe = await get_active_ppe_of_user(interaction)
    except (ValueError, KeyError) as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
    
    try:
        # Load sprite positions mapping
        if not os.path.exists("sprite_positions.csv"):
            await interaction.response.send_message("❌ Sprite mapping not found! Contact an admin.", ephemeral=True)
            return
        
        sprite_positions = {}
        sprite_images = {}
        
        with open("sprite_positions.csv", 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                sprite_positions[row['item_name']] = {
                    'pixel_x': int(row['pixel_x']),
                    'pixel_y': int(row['pixel_y'])
                }
        
        # Load background image
        if not os.path.exists("loot_background.png"):
            await interaction.response.send_message("❌ Loot background not found! Contact an admin.", ephemeral=True)
            return
        
        # Create a copy of the background for this player
        background = Image.open("loot_background.png").copy()
        
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
            
            # Try with shiny suffix if the item is marked as shiny
            lookup_name = item_name
            if loot_item.shiny:
                shiny_name = f"{item_name} (shiny)"
                if shiny_name in sprite_positions and shiny_name in sprite_images:
                    lookup_name = shiny_name
            
            # Check if we have position data for this item
            if lookup_name in sprite_positions and lookup_name in sprite_images:
                pos = sprite_positions[lookup_name]
                sprite = sprite_images[lookup_name]
                
                # Place the colored sprite at the correct position
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
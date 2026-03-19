from discord import app_commands
import discord
from utils.player_records import load_player_records, ensure_player_exists
from utils.calc_points import normalize_item_name
import csv
from PIL import Image
import os

async def command(interaction: discord.Interaction, include_skins: bool = False, include_limited: bool = False):
    """
    Generate a personalized loot image showing all the player's season loot (unique items).
    
    Args:
        include_skins: Include skin items in the loot background
        include_limited: Include limited items in the loot background
    """
    
    try:
        # Load player records
        records = await load_player_records(interaction)
        user_id = interaction.user.id
        key = ensure_player_exists(records, user_id)
        
        # Check if user is member
        if key not in records or not records[key].is_member:
            return await interaction.response.send_message(
                "❌ You're not part of the PPE contest.",
                ephemeral=True
            )
        
        player_data = records[key]
        
        # Check if player has any season loot
        if not player_data.unique_items:
            return await interaction.response.send_message(
                "You haven't collected any season loot yet!\n"
                "Use `/addseasonloot` to start tracking your unique items.",
                ephemeral=True
            )
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

        variant_display_names = {
            "normal": "Normal loot",
            "normal_skins": "Normal + Skins loot",
            "normal_limited": "Normal + Limited loot",
            "all": "All loot",
        }

        variant_summary_prefix = {
            "normal": "Normal",
            "normal_skins": "Normal + Skin",
            "normal_limited": "Normal + Limited",
        }
        
        # Construct file paths
        sprite_csv = f"sprite_positions_{variant}.csv"
        background_file = f"loot_background_{variant}.png"
        
        # Load sprite positions mapping
        if not os.path.exists(sprite_csv):
            await interaction.response.send_message(f"❌ Sprite mapping not found! ({sprite_csv})", ephemeral=True)
            return
        
        sprite_positions = {}
        sprite_images = {}
        item_type_lookup = {}
        
        with open(sprite_csv, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                normalized_name = normalize_item_name(row['item_name'])
                sprite_positions[normalized_name] = {
                    'pixel_x': int(row['pixel_x']),
                    'pixel_y': int(row['pixel_y'])
                }

        # Load loot type metadata so variant inclusion is based on item class
        # (normal/skin/limited), not on whether a sprite row exists.
        with open('rotmg_loot_drops_updated.csv', 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                normalized_name = normalize_item_name(row['Item Name'])
                item_type_lookup[normalized_name] = row['Loot Type'].strip().lower()

        # Build the selected variant item set so we only report missing items
        # that should appear on this specific background variant.
        selected_variant_items = set(sprite_positions.keys())

        # Track which player items are part of this selected variant so the
        # summary can be variant-specific when not using the "all" image.
        def is_in_variant(item_type: str) -> bool:
            if variant == "all":
                return True
            if variant == "normal":
                return item_type not in {"skin", "limited"}
            if variant == "normal_skins":
                return item_type != "limited"
            if variant == "normal_limited":
                return item_type != "skin"
            return True

        total_variant_items = 0
        items_excluded_from_variant = []
        for item_name, shiny in player_data.unique_items:
            normalized_name = normalize_item_name(item_name)
            display_name = f"{item_name} (shiny)" if shiny else item_name

            item_type = item_type_lookup.get(normalized_name, "")
            if is_in_variant(item_type):
                total_variant_items += 1
            else:
                items_excluded_from_variant.append(display_name)
        
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
            item_name = normalize_item_name(item_name)
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
        
        # Place player's season loot on the background
        for item_name, shiny in player_data.unique_items:
            item_name = normalize_item_name(item_name)
            item_type = item_type_lookup.get(item_name, "")

            # Skip items intentionally excluded by selected picture variant.
            if not is_in_variant(item_type):
                continue
            
            # Check if item is marked as shiny
            if shiny:
                shiny_name = f"{item_name} (shiny)"
                # Check if shiny variant exists
                if shiny_name in sprite_positions and shiny_name in sprite_images:
                    # Shiny sprite exists, use it
                    pos = sprite_positions[shiny_name]
                    sprite = sprite_images[shiny_name]
                    background.paste(sprite, (pos['pixel_x'], pos['pixel_y']), sprite)
                    items_placed += 1
                else:
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
        filename = f"{username}_season_loot.png"
        
        # Save the personalized loot image
        background.save(filename, "PNG")
        
        # Create embed with results
        embed = discord.Embed(
            title="🎒 Season Loot Share",
            color=0xFFD700,
            description=f"**{interaction.user.display_name}'s** Season Loot Collection"
        )

        embed.add_field(
            name="🖼️ Picture",
            value=f"**Showing:** {variant_display_names.get(variant, variant)}",
            inline=True
        )

        if variant == "all":
            summary_value = (
                f"**Items Placed:** {items_placed}\n"
                f"**Total Unique Items:** {len(player_data.unique_items)}"
            )
        else:
            summary_prefix = variant_summary_prefix.get(variant, "Selected")
            summary_value = (
                f"**{summary_prefix} Items Placed:** {items_placed}\n"
                f"**Total {summary_prefix} Items:** {total_variant_items}"
            )
        
        embed.add_field(
            name="📊 Summary",
            value=summary_value,
            inline=True
        )

        if variant != "all" and items_excluded_from_variant:
            excluded_text = ", ".join(items_excluded_from_variant[:5])
            if len(items_excluded_from_variant) > 5:
                excluded_text += f" (+{len(items_excluded_from_variant) - 5} more)"
            embed.add_field(
                name="📦 Items Not Shown In This Picture",
                value=excluded_text,
                inline=False
            )
        
        if items_not_found:
            not_found_text = ", ".join(items_not_found[:5])
            if len(items_not_found) > 5:
                not_found_text += f" (+{len(items_not_found) - 5} more)"
            embed.add_field(
                name="⚠️ Items Missing Sprites",
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
        print(f"Error in shareseasonloot command: {e}")
        if not interaction.response.is_done():
            await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)

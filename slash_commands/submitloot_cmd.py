

import os
from anyio import Path
import discord
import cv2
import numpy as np
from utils.autocomplete import get_dungeons
from utils.player_manager import player_manager
from utils.calc_points import calc_points
from utils.find_items import find_items_in_image
from utils.player_records import get_active_ppe_of_user, load_player_records


async def command(
    interaction: discord.Interaction,
    dungeon: str,
    screenshot: discord.Attachment
):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    records = await load_player_records(interaction)
    key = interaction.user.id
    
    # Must be a contest member
    if key not in records or not records[key].is_member:
        return await interaction.response.send_message("❌ You’re not part of the PPE contest. Ask a mod to add you with `/addplayer @you`.")
    player_data = records[key]
    active_id = player_data.active_ppe
    if not active_id:
        return await interaction.response.send_message("❌ You don’t have an active PPE. Use `/newppe` to create one first.")
    # Find the active PPE
    active_ppe = next((p for p in player_data.ppes if p.id == active_id), None)
    if not active_ppe:
        return await interaction.response.send_message("❌ Could not find your active PPE record. Try creating a new one with `/newppe`.")
    
    # --- Validate dungeon ---
    if dungeon not in get_dungeons():
        return await interaction.response.send_message(
            f"❌ `{dungeon}` is not a recognized dungeon.\n"
            f"Use the autocomplete suggestions to select a valid dungeon.",
            ephemeral=True
        )

    # --- Validate screenshot attachment (basic check only) ---
    if not screenshot.filename.lower().endswith((".png", ".jpg", ".jpeg")):
        return await interaction.response.send_message(
            "❌ Please upload a PNG or JPG screenshot.",
            ephemeral=True
        )
    
    await interaction.response.defer(thinking=True)

    # Read screenshot into memory
    image_bytes = await screenshot.read()

    # Decode the image with OpenCV
    image_np = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(image_np, cv2.IMREAD_COLOR)

    if img is None:
        return await interaction.followup.send(
            "❌ I couldn't read that image. Please upload a valid PNG or JPG file.",
            ephemeral=True
        )

    # Validate dimensions
    # h, w = img.shape[:2]
    # if (w, h) != (1920, 1080):
    #     return await interaction.followup.send(
    #         f"❌ Invalid screenshot size: **{w}×{h}**.\n"
    #         f"Please upload a **1920×1080** screenshot.",
    #         ephemeral=True
    #     )
    # allow all dimensions
    

    # --- Prepare download directory ---
    download_dir = "./downloads"
    os.makedirs(download_dir, exist_ok=True)
    file_path = Path(f"./downloads/{screenshot.filename}")
    await screenshot.save(file_path)

    
    # FIRST MESSAGE → send screenshot
    await interaction.followup.send(
        content=f"📷 **Screenshot received!**\nDungeon: **{dungeon}**",
        file= await screenshot.to_file()
    )

    

    found_items = find_items_in_image(file_path, templates_folder=f"./dungeons/{dungeon}")
    if found_items:
        message = "✅ **Detected the following items in your screenshot:**\n"

        for detected_loot in found_items:
            # get item name without tags
            if '(shiny)' in detected_loot["item"]:
                item_name = detected_loot["item"].split(" (")[0].strip()
            else:
                item_name = detected_loot["item"].strip()
            try:
                points = calc_points(item_name, divine=detected_loot["divine"], shiny=detected_loot["shiny"])
                if points == 0:
                    continue
                ppe_id = (await get_active_ppe_of_user(interaction)).id
                user = interaction.user
                if not isinstance(user, discord.Member):
                    raise ValueError("❌ Could not retrieve your member information.")
                final_key, points_added, _active_ppe, _quest_update = await player_manager.add_loot_and_points(
                    interaction, user=user, ppe_id=ppe_id, item_name=item_name, divine=detected_loot["divine"], shiny=detected_loot["shiny"], points=points
                )
                message += f"• **{final_key}** (+{points_added} points)\n"
            except (ValueError, KeyError, LookupError) as e:
                return await interaction.followup.send(str(e), ephemeral=True)

        await interaction.followup.send(message, ephemeral=False)

            # await interaction.response.send_message(
            #     f"✅ Added **{final_key}** to your active PPE for {points} points.",
            #     ephemeral=False
            # )
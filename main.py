import discord
from discord.ext import commands
from dotenv import load_dotenv
import aiosqlite
import os
import cv2
import numpy as np

import cv2
import numpy as np
import os

def find_items_in_image(
    screenshot_path,
    templates_folder="./sprites/",
    threshold=0.9,
    debug_output="./debug/"
):
    """
    Detects loot items in a RotMG screenshot by checking 8 known slots
    within the loot GUI (2x4 grid in bottom-right corner).
    Optimized: crops 70x70 center area from each slot, resizes to 40x40
    to match sprite resolution, and uses alpha masks for accuracy.
    """

    # --- 1. Load screenshot ---
    img = cv2.imread(screenshot_path)
    if img is None:
        print(f"⚠️ Could not read {screenshot_path}")
        return []

    # --- 2. Crop loot GUI (bottom-right corner) ---
    x0, y0, x1, y1 = 1575, 908, 1905, 1072
    loot_gui = img[y0:y1, x0:x1]
    loot_h, loot_w = loot_gui.shape[:2]

    # --- Save cropped source image for debugging ---
    os.makedirs("./cropped", exist_ok=True)
    crop_path = os.path.join("./cropped", os.path.basename(screenshot_path))
    cv2.imwrite(crop_path, loot_gui)
    print(f"🖼️ Saved cropped source: {crop_path}")

    # --- 3. Define 8 slot regions (2 rows x 4 cols) ---
    rows, cols = 2, 4
    cell_w = loot_w // cols   # ≈81 px
    cell_h = loot_h // rows   # ≈80 px

    slots = []
    for row in range(rows):
        for col in range(cols):
            sx = col * (cell_w + 1) # +1 px gap for border
            sy = row * (cell_h + 0)
            slots.append((sx, sy, cell_w, cell_h))

    # --- 4. Load templates (with transparency) ---
    templates = []
    for file in os.listdir(templates_folder):
        if not file.lower().endswith(".png"):
            continue
        tpl_rgba = cv2.imread(os.path.join(templates_folder, file), cv2.IMREAD_UNCHANGED)
        if tpl_rgba is None:
            continue

        # Handle missing alpha
        if tpl_rgba.shape[2] == 4:
            bgr = tpl_rgba[..., :3]
            alpha = tpl_rgba[..., 3]
        else:
            bgr = tpl_rgba
            alpha = np.ones(bgr.shape[:2], dtype=np.uint8) * 255

        templates.append((file.replace(".png", "").replace("_", " ").title(), bgr, alpha))

    os.makedirs(debug_output, exist_ok=True)
    annotated = loot_gui.copy()
    detections = []

    # --- 5. For each slot, run detection ---
    for i, (sx, sy, sw, sh) in enumerate(slots):
        # Extract inner 70x70 area (centered, remove border)
        inner_w, inner_h = 70, 70
        x_pad = (sw - inner_w) // 2
        y_pad = (sh - inner_h) // 2
        slot_crop = loot_gui[sy + y_pad : sy + y_pad + inner_h,
                             sx + x_pad : sx + x_pad + inner_w]

        # Downscale slot to 40x40 (match sprite size)
        slot_img = cv2.resize(slot_crop, (40, 40), interpolation=cv2.INTER_AREA)

        best_item, best_val = None, 0.0

        # --- Loop through templates ---
        for item_name, bgr, alpha in templates:
            # --- Ensure template and mask are exactly 40x40 ---
            if bgr.shape[0] != 40 or bgr.shape[1] != 40:
                bgr = cv2.resize(bgr, (40, 40), interpolation=cv2.INTER_AREA)

            if alpha.shape[0] != 40 or alpha.shape[1] != 40:
                alpha = cv2.resize(alpha, (40, 40), interpolation=cv2.INTER_NEAREST)

            # --- Optional sanity check ---
            if slot_img.shape[0] < bgr.shape[0] or slot_img.shape[1] < bgr.shape[1]:
                print(f"⚠️ Skipping {item_name}: template {bgr.shape[:2]} > slot {slot_img.shape[:2]}")
                continue

            # --- Apply light blur for better aliasing tolerance ---
            slot_blur = cv2.GaussianBlur(slot_img, (3,3), 0.6)
            tpl_blur  = cv2.GaussianBlur(bgr, (3,3), 0.6)


            # Match using alpha mask
            res = cv2.matchTemplate(slot_blur, tpl_blur, cv2.TM_CCOEFF_NORMED, mask=alpha)
            _, max_val, _, _ = cv2.minMaxLoc(res)

            if max_val > best_val:
                best_val = max_val
                best_item = item_name

        # --- Record if above threshold ---
        if best_item and best_val >= threshold:
            detections.append({
                "slot": i + 1,
                "item": best_item,
                "confidence": float(best_val)
            })
            print(f"[DEBUG] Slot {i+1}: {best_item:30s} | Confidence: {best_val:.3f}")

            # Draw rectangle on annotated image
            cv2.rectangle(annotated, (sx, sy), (sx+sw, sy+sh), (0, 0, 255), 2)
            cv2.putText(annotated, f"{best_item} ({best_val:.2f})",
                        (sx+2, sy+15), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)
        else:
            print(f"[DEBUG] Slot {i+1}: No confident match (best={best_val:.3f})")

    save_slot_debug_image(loot_gui, slots)


    # --- 6. Save annotated debug image ---
    debug_path = os.path.join(debug_output, os.path.basename(screenshot_path))
    cv2.imwrite(debug_path, annotated)
    print(f"🖼️ Saved debug annotated image: {debug_path}")

    return detections


# --- Save a debug image showing 40x40 match boxes ---
def save_slot_debug_image(loot_gui, slots, output_path="./debug_slots/"):
    """
    Saves the cropped loot GUI with red 70x70 bounding boxes
    showing the exact areas used for template matching.
    """
    os.makedirs(output_path, exist_ok=True)
    debug_img = loot_gui.copy()

    for (sx, sy, sw, sh) in slots:
        # inner 70x70 region (center crop)
        inner_w, inner_h = 70, 70
        x_pad = (sw - inner_w) // 2
        y_pad = (sh - inner_h) // 2
        x1, y1 = sx + x_pad, sy + y_pad
        x2, y2 = x1 + inner_w, y1 + inner_h

        # draw red rectangle for the 70x70 match area
        cv2.rectangle(debug_img, (x1, y1), (x2, y2), (0, 0, 255), 2)

    out_path = os.path.join(output_path, "loot_gui_slots_debug.png")
    cv2.imwrite(out_path, debug_img)
    print(f"🖼️ Saved slot debug overlay: {out_path}")


load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    async with aiosqlite.connect("data.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS points (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                points INTEGER DEFAULT 0
            )
        """)
        await db.commit()

        
@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return

    for attachment in message.attachments:
        if attachment.filename.lower().endswith((".png", ".jpg", ".jpeg")):
            file_path = f"./downloads/{attachment.filename}"
            await attachment.save(file_path)

            found_items = find_items_in_image(file_path)
            if found_items:
                msg = "💎 **Detected loot:**\n" + "\n".join(
                    [f"Slot {d['slot']}: {d['item']} ({d['confidence']:.2f})" for d in found_items]
                )
            else:
                msg = "🤔 No loot detected."
            await message.channel.send(msg)

    await bot.process_commands(message)

@bot.command()
@commands.has_permissions(administrator=True)
async def removeplayer(ctx, member: discord.Member):
    """Removes a player completely from the points list."""
    async with aiosqlite.connect("data.db") as db:
        await db.execute("DELETE FROM points WHERE user_id = ?", (member.id,))
        await db.commit()
    await ctx.send(f"🗑️ Removed {member.display_name} from the leaderboard.")
    
@bot.command()
async def addpointsfor(ctx, member: discord.Member, amount: int):
    """Adds points to the specified member."""
    user = member
    display_name = user.display_name  # use server display name
    async with aiosqlite.connect("data.db") as db:
        await db.execute("""
            INSERT INTO points (user_id, username, points)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET 
                username = excluded.username,
                points = points + excluded.points;
        """, (user.id, display_name, amount))
        await db.commit()
    await ctx.send(f"✅ {user.mention} gained **{amount} points!**")

@bot.command()
async def addpoints(ctx, amount: int):
    """Adds points to whoever called the command."""
    user = ctx.author
    display_name = user.display_name  # use server display name
    async with aiosqlite.connect("data.db") as db:
        await db.execute("""
            INSERT INTO points (user_id, username, points)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET 
                username = excluded.username,
                points = points + excluded.points;
        """, (user.id, display_name, amount))
        await db.commit()
    await ctx.send(f"✅ {user.mention} gained **{amount} points!**")

@bot.command()
async def leaderboard(ctx):
    """Shows the top 10 players by display name."""
    async with aiosqlite.connect("data.db") as db:
        async with db.execute("SELECT username, points FROM points ORDER BY points DESC LIMIT 10") as cursor:
            rows = await cursor.fetchall()

    if not rows:
        await ctx.send("No points have been added yet!")
        return

    leaderboard_text = "\n".join([
        f"{i+1}. **{name}** — {pts} pts"
        for i, (name, pts) in enumerate(rows)
    ])
    await ctx.send(f"🏆 **Leaderboard** 🏆\n{leaderboard_text}")
bot.run(DISCORD_TOKEN)

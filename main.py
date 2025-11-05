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
    threshold=0.65,
    debug_output="./debug/"
):
    """
    Detects loot items in a RotMG screenshot by checking the 8 known slots
    within the loot GUI (2x4 grid in bottom-right corner).
    """

    # --- 1. Load screenshot ---
    img = cv2.imread(screenshot_path)
    if img is None:
        print(f"⚠️ Could not read {screenshot_path}")
        return []

    h, w = img.shape[:2]
    if w < 1900 or h < 1070:
        print("⚠️ Screenshot size smaller than expected (1920x1080). Skipping.")
        return []

    # --- 2. Crop the loot GUI area ---
    x0, y0 = 1575, 910
    x1, y1 = 1900, 1070
    loot_gui = img[y0:y1, x0:x1]
    loot_h, loot_w = loot_gui.shape[:2]

    # --- 3. Define 8 slot regions (2 rows × 4 cols) ---
    rows, cols = 2, 4
    cell_w = loot_w // cols
    cell_h = loot_h // rows

    slots = []
    for row in range(rows):
        for col in range(cols):
            sx = col * cell_w
            sy = row * cell_h
            slots.append((sx, sy, cell_w, cell_h))

    os.makedirs(debug_output, exist_ok=True)
    annotated = loot_gui.copy()
    detections = []

    # --- 4. Load templates once ---
    templates = []
    for file in os.listdir(templates_folder):
        if not file.lower().endswith(".png"):
            continue
        tpl = cv2.imread(os.path.join(templates_folder, file), cv2.IMREAD_UNCHANGED)
        if tpl is None:
            continue
        templates.append((file.replace(".png", "").replace("_", " ").title(), tpl))

    # --- 5. For each slot, match against all templates ---
    for i, (sx, sy, sw, sh) in enumerate(slots):
        slot_img = loot_gui[sy:sy+sh, sx:sx+sw]
        best_item, best_val = None, 0.0

        for item_name, tpl in templates:
            # Fill transparent pixels with (71,71,71) gray before resizing
            gray_bg = np.array([71, 71, 71], dtype=np.float32)
            alpha = tpl[..., 3:4] / 255.0
            tpl_filled = tpl[..., :3] * alpha + gray_bg * (1 - alpha)
            tpl_filled = tpl_filled.astype(np.uint8)

            # Resize template to slot size
            tpl_resized = cv2.resize(tpl_filled, (sw, sh))

            res = cv2.matchTemplate(slot_img, tpl_resized, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)

            if max_val > best_val:
                best_val = max_val
                best_item = item_name

        # --- 6. Record if above threshold ---
        if best_item and best_val >= threshold:
            detections.append({
                "slot": i + 1,
                "item": best_item,
                "confidence": float(best_val)
            })
            print(f"[DEBUG] Slot {i+1}: {best_item:30s} | Confidence: {best_val:.3f}")
            # Draw rectangle and label
            cv2.rectangle(annotated, (sx, sy), (sx+sw, sy+sh), (0, 0, 255), 2)
            cv2.putText(
                annotated,
                f"{best_item} ({best_val:.2f})",
                (sx+2, sy+15),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (0, 0, 255),
                1
            )
        else:
            print(f"[DEBUG] Slot {i+1}: No confident match (best={best_val:.3f})")

    # --- 7. Save debug image ---
    debug_path = os.path.join(debug_output, os.path.basename(screenshot_path))
    cv2.imwrite(debug_path, annotated)
    print(f"🖼️ Saved debug image: {debug_path}")

    return detections




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

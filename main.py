import math
import discord
from discord.ext import commands
from dotenv import load_dotenv
import aiosqlite
import os
import cv2
import numpy as np
import csv
import json

LOOT_POINTS_CSV = "./rotmg_loot_drops.csv"
PLAYER_RECORD_FILE = "./guild_loot_records.json"

# --- Load points table from CSV ---
def load_loot_points():
    loot_points = {}
    with open(LOOT_POINTS_CSV, newline='', encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["Item Name"].strip().lower()
            points = float(row["Points"])
            loot_points[name] = points
    return loot_points

# --- Load existing guild member records ---
def load_player_records():
    if os.path.exists(PLAYER_RECORD_FILE):
        with open(PLAYER_RECORD_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# --- Save updated records ---
def save_player_records(records):
    with open(PLAYER_RECORD_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)

# --- Compute points for detected loot ---
def calculate_loot_points(player_name, detected_items):
    loot_points = load_loot_points()
    records = load_player_records()

    player_key = player_name.lower()
    if player_key not in records:
        records[player_key] = {"items": [], "total_points": 0}

    player_data = records[player_key]
    results = []

    for item in detected_items:
        item_name = item["item"].lower()
        base_points = loot_points.get(item_name, 0)

        # Always 1 point for top-tier T14/T7
        if "t14" in item_name or "t7" in item_name:
            base_points = 1

        # Skip completely if item not worth any points
        if base_points <= 0:
            continue

        if base_points != 1: # tops can be duplicates

            # Check duplicate
            is_duplicate = item_name in [i.lower() for i in player_data["items"]]
            final_points = base_points / 2 if is_duplicate else base_points

            # --- NEW: round down to nearest 0.5 ---
            final_points = math.floor(final_points * 2) / 2
        else:
            is_duplicate = False
            final_points = base_points

        # Update player data
        if not is_duplicate:
            player_data["items"].append(item_name)
        player_data["total_points"] += final_points

        results.append({
            "item": item["item"],
            "points": final_points,
            "duplicate": is_duplicate
        })

    # Save updated record
    records[player_key] = player_data
    save_player_records(records)

    return results, player_data["total_points"]

def find_items_in_image(
    screenshot_path,
    templates_folder="./sprites/",
    threshold=0.85,
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
            # --- Ensure both are 40x40 (from earlier safety block) ---
            if bgr.shape[:2] != (40, 40):
                bgr = cv2.resize(bgr, (40, 40), interpolation=cv2.INTER_AREA)
            if alpha.shape[:2] != (40, 40):
                alpha = cv2.resize(alpha, (40, 40), interpolation=cv2.INTER_NEAREST)

            crop_h = int(40 * (2/3))  # ≈ 26–27 pixels
            slot_crop_top = slot_img[:crop_h, :, :]
            tpl_crop_top  = bgr[:crop_h, :, :]
            mask_crop_top = alpha[:crop_h, :]

            # --- Structural similarity (template match on top 2/3) ---
            slot_blur = cv2.GaussianBlur(slot_crop_top, (3,3), 0.6)
            tpl_blur  = cv2.GaussianBlur(tpl_crop_top, (3,3), 0.6)

            # --- Before doing matchTemplate() ---
            # Check variance of the slot — if it's basically flat gray, skip it
            slot_var = np.var(slot_img)
            if slot_var < 5:  # tweak threshold (typical empty gray variance ≈ 0–2)
                print(f"[DEBUG] Slot {i}: Empty or flat background detected (variance={slot_var:.3f}) — skipping.")
                break

            res = cv2.matchTemplate(slot_blur, tpl_blur, cv2.TM_CCOEFF_NORMED, mask=mask_crop_top)
            _, structural_val, _, _ = cv2.minMaxLoc(res)

            # --- Color similarity weighting (HSV hue on top 2/3 only) ---
            slot_hsv = cv2.cvtColor(slot_crop_top, cv2.COLOR_BGR2HSV)
            tpl_hsv  = cv2.cvtColor(tpl_crop_top,  cv2.COLOR_BGR2HSV)

            mask_bool = mask_crop_top > 10
            slot_hue = slot_hsv[..., 0][mask_bool]
            tpl_hue  = tpl_hsv[..., 0][mask_bool]

            if len(slot_hue) and len(tpl_hue):
                hue_diff = np.mean(np.abs(slot_hue.astype(np.float32) - tpl_hue.astype(np.float32)))
                hue_diff = np.minimum(hue_diff, 180 - hue_diff)  # handle wraparound (OpenCV hue 0–180)
                color_score = 1.0 - min(hue_diff / 90.0, 1.0)
            else:
                color_score = 0.5  # neutral fallback

            # --- Combine structure + color weighting ---
            final_val = 0.9 * structural_val + 0.1 * color_score

            # --- Update best match if higher confidence ---
            if final_val > best_val:
                best_val = final_val
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

import json, os

PLAYER_RECORD_FILE = "./guild_loot_records.json"

def load_player_records():
    if os.path.exists(PLAYER_RECORD_FILE):
        with open(PLAYER_RECORD_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_player_records(records):
    with open(PLAYER_RECORD_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)

def ensure_player_exists(records, player_name):
    """Ensure a player entry exists with at least one PPE."""
    key = player_name.lower()
    if key not in records:
        records[key] = {"ppes": [], "active_ppe": None}
    return key

def get_active_ppe(player_data):
    """Return the active PPE dict, or None."""
    active_id = player_data.get("active_ppe")
    for ppe in player_data.get("ppes", []):
        if ppe["id"] == active_id:
            return ppe
    return None



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

@bot.command(name="newppe", help="Create a new PPE and make it your active one.")
async def newppe(ctx: commands.Context):
    records = load_player_records()
    key = ensure_player_exists(records, ctx.author.display_name)

    player_data = records[key]
    next_id = max([ppe["id"] for ppe in player_data["ppes"]], default=0) + 1

    new_ppe = {"id": next_id, "name": f"PPE #{next_id}", "points": 0, "items": []}
    player_data["ppes"].append(new_ppe)
    player_data["active_ppe"] = next_id

    save_player_records(records)
    await ctx.reply(f"✅ Created **PPE #{next_id}** and set it as your active PPE.")

@bot.command(name="setactiveppe", help="Set which PPE is active for point tracking.")
async def setactiveppe(ctx: commands.Context, ppe_id: int):
    records = load_player_records()
    key = ensure_player_exists(records, ctx.author.display_name)
    player_data = records[key]

    ppe_ids = [ppe["id"] for ppe in player_data["ppes"]]
    if ppe_id not in ppe_ids:
        return await ctx.reply(f"❌ You don’t have a PPE #{ppe_id}. Use !newppe to create one.")

    player_data["active_ppe"] = ppe_id
    save_player_records(records)
    await ctx.reply(f"✅ Set **PPE #{ppe_id}** as your active PPE.")


        
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
                player_name = str(message.author.display_name)
                loot_results, total = calculate_loot_points(player_name, found_items)

                msg_lines = [f"**{player_name}'s Loot Summary:**"]
                for loot in loot_results:
                    dup_tag = " (Duplicate ⚠️)" if loot["duplicate"] else ""
                    msg_lines.append(f"- {loot['item']}: +{loot['points']} points{dup_tag}")
                msg_lines.append(f"**Total Points:** {total:.1f}")

                await message.channel.send("\n".join(msg_lines))

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

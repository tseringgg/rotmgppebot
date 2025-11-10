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

LOOT_POINTS_CSV = "./rotmg_loot_drops_updated.csv"
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


def calculate_loot_points(player_name, detected_items):
    loot_points = load_loot_points()
    records = load_player_records()
    key = player_name.lower()

    if key not in records or not records[key].get("is_member", False):
        raise ValueError(f"{player_name} is not a contest member.")

    player_data = records[key]
    active_id = player_data.get("active_ppe")
    if not active_id:
        raise ValueError(f"{player_name} has no active PPE.")

    # --- get active PPE object ---
    active_ppe = next((p for p in player_data["ppes"] if p["id"] == active_id), None)
    if not active_ppe:
        raise ValueError(f"Active PPE (#{active_id}) not found for {player_name}.")

    results = []

    for item in detected_items:
        item_name = item["item"].lower()
        base_points = loot_points.get(item_name, 0)

        # Skip items with no point value
        if base_points <= 0:
            continue

        if base_points != 1:

            # --- check duplicate inside this PPE's item list ---
            existing_items = [i.lower() for i in active_ppe.get("items", [])]
            is_duplicate = item_name in existing_items
            final_points = base_points / 2 if is_duplicate else base_points

            # --- round down to nearest 0.5 ---
            import math
            final_points = math.floor(final_points * 2) / 2
        else:
            is_duplicate = False
            final_points = 1

        # --- update PPE items + points ---
        if not is_duplicate:
            active_ppe.setdefault("items", []).append(item_name)
        active_ppe["points"] = active_ppe.get("points", 0) + final_points

        results.append({
            "item": item["item"],
            "points": final_points,
            "duplicate": is_duplicate
        })

    save_player_records(records)
    return results, active_ppe["points"]


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

    slots = slots[:4]   # ✅ Only check the first 4 slots for speed

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

# PLAYER_RECORD_FILE = "./guild_loot_records.json"

# def load_player_records():
#     if os.path.exists(PLAYER_RECORD_FILE):
#         with open(PLAYER_RECORD_FILE, "r", encoding="utf-8") as f:
#             try:
#                 return json.load(f)
#             except json.JSONDecodeError:
#                 return {}
#     return {}

# def save_player_records(records):
#     with open(PLAYER_RECORD_FILE, "w", encoding="utf-8") as f:
#         json.dump(records, f, indent=2)

# def ensure_player_exists(records, player_name):
#     """Ensure a player entry exists with at least one PPE."""
#     key = player_name.lower()
#     if key not in records:
#         records[key] = {"ppes": [], "active_ppe": None}
#     return key

# def get_active_ppe(player_data):
#     """Return the active PPE dict, or None."""
#     active_id = player_data.get("active_ppe")
#     for ppe in player_data.get("ppes", []):
#         if ppe["id"] == active_id:
#             return ppe
#     return None

import os
import json
import asyncio

# Directory to store per-guild player data
DATA_DIR = "./data"
os.makedirs(DATA_DIR, exist_ok=True)

# Dictionary of asyncio Locks — one per guild
_locks = {}

def get_lock(guild_id: int):
    """Return or create a lock for this guild."""
    if guild_id not in _locks:
        _locks[guild_id] = asyncio.Lock()
    return _locks[guild_id]

def get_guild_data_path(guild_id: int) -> str:
    """Return the file path for this guild's data file."""
    return os.path.join(DATA_DIR, f"{guild_id}_loot_records.json")

# -------------------------------------------------------------------------
# Core read/write functions
# -------------------------------------------------------------------------

async def load_player_records(guild_id: int):
    """Load player records for a specific guild safely."""
    path = get_guild_data_path(guild_id)
    if not os.path.exists(path):
        return {}

    async with get_lock(guild_id):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}

async def save_player_records(guild_id: int, records: dict):
    """Save player records for a specific guild safely."""
    path = get_guild_data_path(guild_id)
    async with get_lock(guild_id):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)

# -------------------------------------------------------------------------
# Player utilities
# -------------------------------------------------------------------------

def ensure_player_exists(records: dict, player_name: str):
    """Ensure a player entry exists with at least one PPE."""
    key = player_name.lower()
    if key not in records:
        records[key] = {"ppes": [], "active_ppe": None}
    return key

def get_active_ppe(player_data: dict):
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

@bot.command(name="newppe", help="Create a new PPE (max 10) and make it your active one.")
@commands.has_role("PPE Admin")
async def newppe(ctx: commands.Context):
    records = load_player_records()
    key = ctx.author.display_name.lower()

    # Check membership first
    if key not in records or not records[key].get("is_member", False):
        return await ctx.reply("❌ You’re not part of the PPE contest. Ask a mod to add you with `!addplayer @you`.")

    player_data = records[key]

    # --- PPE limit check ---
    ppe_count = len(player_data.get("ppes", []))
    if ppe_count >= 10:
        return await ctx.reply("⚠️ You’ve reached the limit of **10 PPEs**. Delete or reuse an existing one before making a new one.")

    # --- Create new PPE ---
    next_id = max([ppe["id"] for ppe in player_data["ppes"]], default=0) + 1
    new_ppe = {"id": next_id, "name": f"PPE #{next_id}", "points": 0, "items": []}

    player_data["ppes"].append(new_ppe)
    player_data["active_ppe"] = next_id
    save_player_records(records)

    await ctx.reply(f"✅ Created **PPE #{next_id}** and set it as your active PPE.\n"
                    f"You now have {ppe_count + 1}/10 PPEs.")


@bot.command(name="setactiveppe", help="Set which PPE is active for point tracking.")
@commands.has_role("PPE Player")
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
    
    # --- Only allow in registered PPE channels ---
    allowed_channels = load_ppe_channels()
    if message.channel.id not in allowed_channels:
        # Still allow normal commands to run elsewhere
        return await bot.process_commands(message)

    # --- Only allow PPE Players or PPE Admins ---
    has_ppe_player = discord.utils.get(message.author.roles, name="PPE Player")
    has_ppe_admin = discord.utils.get(message.author.roles, name="PPE Admin")

    if not (has_ppe_player or has_ppe_admin):
        # Optional: politely ignore or respond
        print(f"🚫 Ignored message from {message.author} (no PPE role).")
        return
    
    for attachment in message.attachments:
        if attachment.filename.lower().endswith((".png", ".jpg", ".jpeg")):
            # --- Prepare download directory ---
            download_dir = "./downloads"
            os.makedirs(download_dir, exist_ok=True)
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

# @bot.command()
# @commands.has_permissions(administrator=True)
# async def removeplayer(ctx, member: discord.Member):
#     """Removes a player completely from the points list."""
#     async with aiosqlite.connect("data.db") as db:
#         await db.execute("DELETE FROM points WHERE user_id = ?", (member.id,))
#         await db.commit()
#     await ctx.send(f"🗑️ Removed {member.display_name} from the leaderboard.")
    
@bot.command(name="addpointsfor", help="Add points to another player's active PPE.")
@commands.has_role("PPE Admin")  # both can use
async def addpointsfor(ctx: commands.Context, member: discord.Member, amount: float):
    records = load_player_records()
    key = member.display_name.lower()

    if key not in records or not records[key].get("is_member", False):
        return await ctx.reply(f"❌ {member.display_name} is not part of the PPE contest.")

    player_data = records[key]
    active_id = player_data.get("active_ppe")
    if not active_id:
        return await ctx.reply(f"❌ {member.display_name} does not have an active PPE.")

    active_ppe = next((p for p in player_data["ppes"] if p["id"] == active_id), None)
    if not active_ppe:
        return await ctx.reply(f"❌ Could not find {member.display_name}'s active PPE record.")

    import math
    amount = math.floor(amount * 2) / 2
    active_ppe["points"] += amount
    save_player_records(records)

    await ctx.reply(f"✅ Added **{amount:.1f}** points to **{member.display_name}**’s active PPE (PPE #{active_id}).\n"
                    f"**New total:** {active_ppe['points']:.1f} points.")


@bot.command(name="addpoints", help="Add points to your active PPE.")
@commands.has_role("PPE Player")
async def addpoints(ctx: commands.Context, amount: float):
    records = load_player_records()
    key = ctx.author.display_name.lower()

    # Must be a contest member
    if key not in records or not records[key].get("is_member", False):
        return await ctx.reply("❌ You’re not part of the PPE contest. Ask a mod to add you with `!addplayer @you`.")

    player_data = records[key]
    active_id = player_data.get("active_ppe")
    if not active_id:
        return await ctx.reply("❌ You don’t have an active PPE. Use `!newppe` to create one first.")

    # Find the active PPE
    active_ppe = next((p for p in player_data["ppes"] if p["id"] == active_id), None)
    if not active_ppe:
        return await ctx.reply("❌ Could not find your active PPE record. Try creating a new one with `!newppe`.")

    # Add points (rounded down to nearest 0.5)
    import math
    amount = math.floor(amount * 2) / 2
    active_ppe["points"] += amount
    save_player_records(records)

    await ctx.reply(f"✅ Added **{amount:.1f}** points to your active PPE (PPE #{active_id}).\n"
                    f"**New total:** {active_ppe['points']:.1f} points.")


@bot.command(name="listplayers", help="Show all current participants in the PPE contest.")
@commands.has_role("PPE Admin")
async def listplayers(ctx: commands.Context):
    records = load_player_records()

    # Get all members who are marked as PPE participants
    members = [(name, data) for name, data in records.items() if data.get("is_member", False)]

    if not members:
        return await ctx.reply("❌ No one has been added to the PPE contest yet.")

    lines = ["**🏆 Current PPE Contest Participants 🏆**"]
    for name, data in members:
        ppe_count = len(data.get("ppes", []))
        active_id = data.get("active_ppe")
        lines.append(f"• **{name.title()}** — {ppe_count} PPE(s), Active: PPE #{active_id}")

    await ctx.reply("\n".join(lines))


@bot.command(name="addplayer", help="Add a player to the PPE contest and create their first active PPE.")
@commands.has_role("PPE Admin")
async def addplayer(ctx: commands.Context, member: discord.Member):
    give_ppe_player_role(ctx, member)
    """
    Adds a new member to the PPE contest.
    - Creates their first PPE (PPE #1)
    - Sets it active
    - Gives them access to all PPE commands
    """
    records = load_player_records()
    key = member.display_name.lower()

    if key in records:
        return await ctx.reply(f"⚠️ {member.display_name} is already in the PPE contest.")

    # Create player entry
    records[key] = {
        "ppes": [
            {"id": 1, "name": "PPE #1", "points": 0, "items": []}
        ],
        "active_ppe": 1,
        "is_member": True  # mark as officially added
    }

    save_player_records(records)
    await ctx.reply(f"✅ Added **{member.display_name}** to the PPE contest and created **PPE #1** as their active PPE.")

@bot.command(name="removeplayer", help="Remove a player and all their PPE data from the contest.")
@commands.has_role("PPE Admin")
async def removeplayer(ctx: commands.Context, member: discord.Member):
    remove_ppe_player_role(ctx, member)
    records = load_player_records()
    key = member.display_name.lower()

    if key not in records or not records[key].get("is_member", False):
        return await ctx.reply(f"❌ {member.display_name} is not in the PPE contest.")

    # Confirm removal
    del records[key]
    save_player_records(records)

    await ctx.reply(f"🗑️ Removed **{member.display_name}** and all their PPE data from the contest.")



@bot.command(name="myppe", help="Show all your PPEs and which one is active.")
@commands.has_role("PPE Player")
async def myppe(ctx: commands.Context):
    records = load_player_records()
    key = ctx.author.display_name.lower()

    if key not in records or not records[key]["ppes"]:
        return await ctx.reply("❌ You don’t have any PPEs yet. Use `!newppe` to create one!")

    player_data = records[key]
    active_id = player_data.get("active_ppe")

    lines = [f"**{ctx.author.display_name}'s PPEs:**"]
    for ppe in sorted(player_data["ppes"], key=lambda x: x["id"]):
        id_ = ppe["id"]
        pts = ppe.get("points", 0)
        marker = "✅ (Active)" if id_ == active_id else ""
        lines.append(f"• PPE #{id_}: {pts:.1f} points {marker}")

    await ctx.reply("\n".join(lines))


@bot.command(name="leaderboard", help="Show the best PPE from each player.")
async def leaderboard(ctx: commands.Context):
    records = load_player_records()

    leaderboard_data = []
    for player, data in records.items():
        if not data["ppes"]:
            continue
        best_ppe = max(data["ppes"], key=lambda p: p["points"])
        leaderboard_data.append((player, best_ppe["id"], best_ppe["points"]))

    leaderboard_data.sort(key=lambda x: x[2], reverse=True)

    lines = ["🏆 **Best PPE Leaderboard** 🏆"]
    for rank, (player, ppe_id, pts) in enumerate(leaderboard_data, start=1):
        lines.append(f"{rank}. **{player.title()}** — PPE #{ppe_id}: {pts:.1f} points")

    await ctx.reply("\n".join(lines))


import json, os

######################
#### PPE CHANNELS ####
######################

PPE_CHANNEL_FILE = "./ppe_channels.json"

def load_ppe_channels():
    if os.path.exists(PPE_CHANNEL_FILE):
        with open(PPE_CHANNEL_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                return data.get("ppe_channels", [])
            except json.JSONDecodeError:
                return []
    return []

def save_ppe_channels(channel_ids):
    with open(PPE_CHANNEL_FILE, "w", encoding="utf-8") as f:
        json.dump({"ppe_channels": channel_ids}, f, indent=2)

@bot.command(name="setppechannel", help="Mark this channel as a PPE channel.")
@commands.has_role("PPE Admin")
async def set_ppe_channel(ctx: commands.Context):
    channel_id = ctx.channel.id
    channels = load_ppe_channels()
    if channel_id in channels:
        return await ctx.reply("⚠️ This channel is already set as a PPE channel.")

    channels.append(channel_id)
    save_ppe_channels(channels)
    await ctx.reply(f"✅ Added **#{ctx.channel.name}** as a PPE channel.")


@bot.command(name="unsetppechannel", help="Remove this channel from PPE channels.")
@commands.has_role("PPE Admin")
async def unset_ppe_channel(ctx: commands.Context):
    channel_id = ctx.channel.id
    channels = load_ppe_channels()
    if channel_id not in channels:
        return await ctx.reply("⚠️ This channel is not currently a PPE channel.")

    channels.remove(channel_id)
    save_ppe_channels(channels)
    await ctx.reply(f"🗑️ Removed **#{ctx.channel.name}** from the PPE channel list.")


@bot.command(name="listppechannels", help="Show all channels marked as PPE channels.")
@commands.has_role("PPE Admin")
async def list_ppe_channels(ctx: commands.Context):
    channels = load_ppe_channels()
    if not channels:
        return await ctx.reply("❌ No PPE channels have been set yet. Use `!setppechannel` in one.")
    lines = ["**📜 PPE Channels:**"]
    for cid in channels:
        channel = ctx.guild.get_channel(cid)
        if channel:
            lines.append(f"• #{channel.name} ({cid})")
        else:
            lines.append(f"• (deleted channel) {cid}")
    await ctx.reply("\n".join(lines))


@bot.command(name="ppehelp", help="Show available PPE commands for players and admins.")
async def ppehelp(ctx):

    # --- Commands for everyone ---
    everyone_cmds = {
        "leaderboard": "Show the current PPE leaderboard.",
        "ppehelp": "Show this help message.",
        "listroles": "List all roles in this server.",
    }
    # --- Player Commands ---
    player_cmds = {
        "myppe": "View your current PPE stats or progress.",
        "newppe": "Start a new PPE run and track your progress.",
        "setactiveppe": "Set which of your PPE characters is currently active.",
        "addpoints": "Add points to your active PPE.",
    }

    # --- Admin Commands ---
    admin_cmds = {
        "listppechannels": "List all channels marked as PPE channels.",
        "setppechannel": "Mark this channel as a PPE channel.",
        "unsetppechannel": "Remove this channel from PPE channels.",
        "addplayer": "Add a member to the PPE contest.",
        "removeplayer": "Remove a member from the PPE contest.",
        "listplayers": "List all current participants in the PPE contest.",
        "addpointsfor": "Add points to another player's active PPE.",
    }
    owner_cmds = {
        "giveppeadminrole": "Give the PPE Admin role to a member.",
        "removeppeadminrole": "Remove the PPE Admin role from a member.",
    }

    # --- Create help embed ---
    embed = discord.Embed(
        title="🧙 PPE Bot Help",
        description=(
            "Welcome to the PPE competition bot!\n\n"
            "🟢 **Player Commands** — for everyone with the **PPE Player** role.\n"
            "🔴 **Admin Commands** — for members with the **PPE Admin** role or 'Manage Roles' permission."
        ),
        color=discord.Color.blurple()
    )

    # --- Format everyone commands ---
    everyone_text = "\n".join([f"• `!{cmd}` — {desc}" for cmd, desc in everyone_cmds.items()])
    embed.add_field(name="⚪ Everyone Commands", value=everyone_text or "None available", inline=False)

    # --- Format player commands ---
    player_text = "\n".join([f"• `!{cmd}` — {desc}" for cmd, desc in player_cmds.items()])
    embed.add_field(name="🟢 Player Commands", value=player_text or "None available", inline=False)

    # --- Format admin commands ---
    admin_text = "\n".join([f"• `!{cmd}` — {desc}" for cmd, desc in admin_cmds.items()])
    embed.add_field(name="🔴 Admin Commands", value=admin_text or "None available", inline=False)

    # --- Format owner commands ---
    owner_text = "\n".join([f"• `!{cmd}` — {desc}" for cmd, desc in owner_cmds.items()])
    embed.add_field(name="🔒 Owner Commands", value=owner_text or "None available", inline=False)

    # --- Footer ---
    embed.set_footer(text="PPE Bot by LogicVoid — use !ppehelp anytime for command info")

    await ctx.send(embed=embed)

###############
#### ROLES ####
###############

# --- Give PPE Admin role ---
@bot.command(name="giveppeadminrole", help="Give the PPE Admin role to a member. Admin only.")
@commands.has_permissions(manage_roles=True)
async def give_ppe_admin_role(ctx, member: discord.Member):
    role = discord.utils.get(ctx.guild.roles, name="PPE Admin")
    if not role:
        await ctx.send("❌ PPE Admin role not found. Create it first.")
        return

    try:
        await member.add_roles(role)
        await ctx.send(f"✅ Gave **PPE Admin** role to **{member.display_name}**.")
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to manage that role. Move my bot role higher in the hierarchy.")

# --- Give PPE Player role ---
# @bot.command(name="giveppeplayerrole", help="Give the PPE Player role to a member. Admin only.")
# @commands.has_role("PPE Admin")
async def give_ppe_player_role(ctx, member: discord.Member):
    role = discord.utils.get(ctx.guild.roles, name="PPE Player")
    if not role:
        await ctx.send("❌ PPE Player role not found. Create it first.")
        return

    try:
        await member.add_roles(role)
        await ctx.send(f"✅ Gave **PPE Player** role to **{member.display_name}**.")
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to manage that role. Move my bot role higher in the hierarchy.")

# --- Remove PPE Admin role ---
@bot.command(name="removeppeadminrole", help="Remove the PPE Admin role from a member. Admin only.")
@commands.has_permissions(manage_roles=True)
async def remove_ppe_admin_role(ctx, member: discord.Member):
    role = discord.utils.get(ctx.guild.roles, name="PPE Admin")
    if not role:
        await ctx.send("❌ PPE Admin role not found.")
        return

    try:
        await member.remove_roles(role)
        await ctx.send(f"✅ Removed **PPE Admin** role from **{member.display_name}**.")
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to manage that role. Move my bot role higher in the hierarchy.")


# --- Remove PPE Player role ---
# @bot.command(name="removeppeplayerrole", help="Remove the PPE Player role from a member. Admin only.")
# @commands.has_role("PPE Admin")
async def remove_ppe_player_role(ctx, member: discord.Member):
    role = discord.utils.get(ctx.guild.roles, name="PPE Player")
    if not role:
        await ctx.send("❌ PPE Player role not found.")
        return

    try:
        await member.remove_roles(role)
        await ctx.send(f"✅ Removed **PPE Player** role from **{member.display_name}**.")
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to manage that role. Move my bot role higher in the hierarchy.")

# --- Command: list roles ---
@bot.command(name="listroles", help="List all roles in this server.")
async def list_roles(ctx):
    roles = [r.name for r in ctx.guild.roles if r.name != "@everyone"]
    await ctx.send("🎭 Available roles:\n" + "\n".join(f"- {r}" for r in roles))




bot.run(DISCORD_TOKEN)

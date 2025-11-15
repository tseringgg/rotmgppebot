import discord
from discord.ext import commands
from dotenv import load_dotenv
import aiosqlite
import os
import json

from utils.find_items import find_items_in_image
from utils.calc_points import calculate_loot_points
from utils.player_records import load_player_records, save_player_records, ensure_player_exists


load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
from utils.role_checks import require_ppe_roles

@bot.event
async def on_guild_join(guild: discord.Guild):
    """Called when the bot joins a new server."""
    required_roles = ["PPE Player", "PPE Admin"]
    existing_roles = {role.name for role in guild.roles}
    created_roles = []

    # Try to create any missing roles
    for role_name in required_roles:
        if role_name not in existing_roles:
            try:
                new_role = await guild.create_role(
                    name=role_name,
                    reason="Automatically created required PPE roles."
                )
                created_roles.append(new_role.name)
            except discord.Forbidden:
                print(f"[WARN] Missing permission to create roles in {guild.name}.")
            except Exception as e:
                print(f"[ERROR] Failed to create role '{role_name}' in {guild.name}: {e}")

    # Send setup message in system channel (or fallback)
    setup_msg = "👋 **PPE Bot Setup Complete!**\n\n"
    if created_roles:
        setup_msg += f"✅ Created roles: {', '.join(created_roles)}\n"
    else:
        setup_msg += "ℹ️ Required roles already existed.\n"
    setup_msg += (
        "\n**Assign roles:**\n"
        "- `PPE Admin`: Can manage PPEs, reset leaderboards, and configure the bot.\n"
        "- `PPE Player`: Can register PPEs, post loot, and view leaderboards."
    )

    # Find a channel to send the message
    channel = (
        guild.system_channel
        or next(
            (c for c in guild.text_channels if c.permissions_for(guild.me).send_messages),
            None
        )
    )
    if channel:
        try:
            await channel.send(setup_msg)
        except Exception as e:
            print(f"[WARN] Could not send setup message in {guild.name}: {e}")
    else:
        print(f"[INFO] Joined {guild.name}, but no suitable text channel found for setup message.")

@bot.command(name="setuproles", help="Check and create required PPE roles in this server.")
@commands.has_permissions(manage_roles=True)
async def setup_roles(ctx):
    await on_guild_join(ctx.guild)
    await ctx.send("🔁 Setup roles check complete.")


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
# @commands.has_role("PPE Admin")
@require_ppe_roles(player_required=True)
# async def newppe(interaction: discord.Interaction):
async def newppe(ctx: commands.Context):
    # ctx = interaction
    guild_id = ctx.guild.id
    records = await load_player_records(guild_id)
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
    await save_player_records(guild_id=guild_id, records=records)

    await ctx.reply(f"✅ Created **PPE #{next_id}** and set it as your active PPE.\n"
                    f"You now have {ppe_count + 1}/10 PPEs.")


@bot.command(name="setactiveppe", help="Set which PPE is active for point tracking.")
# @commands.has_role("PPE Player")
@require_ppe_roles(player_required=True)
async def setactiveppe(ctx: commands.Context, ppe_id: int):
    guild_id = ctx.guild.id
    records = await load_player_records(guild_id)
    key = ensure_player_exists(records, ctx.author.display_name)
    player_data = records[key]

    ppe_ids = [ppe["id"] for ppe in player_data["ppes"]]
    if ppe_id not in ppe_ids:
        return await ctx.reply(f"❌ You don’t have a PPE #{ppe_id}. Use !newppe to create one.")

    player_data["active_ppe"] = ppe_id
    await save_player_records(guild_id=guild_id, records=records)
    await ctx.reply(f"✅ Set **PPE #{ppe_id}** as your active PPE.")


        
@bot.event
async def on_message(message: discord.Message):
    guild_id = message.guild.id
    if message.author == bot.user:
        return
    
    # --- Only allow in registered PPE channels ---
    ppe_channels = load_ppe_channels()
    if message.channel.id not in ppe_channels:
        # Still allow normal commands to run elsewhere
        return await bot.process_commands(message)

    # --- Only allow PPE Players or PPE Admins ---
    has_ppe_player = discord.utils.get(message.author.roles, name="PPE Player")
    has_ppe_admin = discord.utils.get(message.author.roles, name="PPE Admin")

    if has_ppe_player and message.channel.id in ppe_channels:
        # --- Process attachments for loot detection ---
    
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
                    loot_results, total = await calculate_loot_points(guild_id, player_name, found_items)

                    msg_lines = [f"**{player_name}'s Loot Summary:**"]
                    for loot in loot_results:
                        dup_tag = " (Duplicate ⚠️)" if loot["duplicate"] else ""
                        msg_lines.append(f"- {loot['item']}: +{loot['points']} points{dup_tag}")
                    msg_lines.append(f"**Total Points:** {total:.1f}")

                    await message.channel.send("\n".join(msg_lines))

    await bot.process_commands(message)

    
@bot.command(name="addpointsfor", help="Add points to another player's active PPE.")
# @commands.has_role("PPE Admin")  # both can use
@require_ppe_roles(admin_required=True)
async def addpointsfor(ctx: commands.Context, member: discord.Member, amount: float):
    guild_id = ctx.guild.id
    records = await load_player_records(guild_id)
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
    await save_player_records(guild_id=guild_id, records=records)

    await ctx.reply(f"✅ Added **{amount:.1f}** points to **{member.display_name}**’s active PPE (PPE #{active_id}).\n"
                    f"**New total:** {active_ppe['points']:.1f} points.")


@bot.command(name="addpoints", help="Add points to your active PPE.")
# @commands.has_role("PPE Player")
@require_ppe_roles(player_required=True)
async def addpoints(ctx: commands.Context, amount: float):
    guild_id = ctx.guild.id
    records = await load_player_records(guild_id)
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
    await save_player_records(guild_id=guild_id, records=records)

    await ctx.reply(f"✅ Added **{amount:.1f}** points to your active PPE (PPE #{active_id}).\n"
                    f"**New total:** {active_ppe['points']:.1f} points.")


@bot.command(name="listplayers", help="Show all current participants in the PPE contest.")
# @commands.has_role("PPE Admin")
@require_ppe_roles(admin_required=True)
async def listplayers(ctx: commands.Context):
    guild_id = ctx.guild.id
    records = await load_player_records(guild_id)

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
# @commands.has_role("PPE Admin")
@require_ppe_roles(admin_required=True)
async def addplayer(ctx: commands.Context, member: discord.Member):
    await give_ppe_player_role(ctx, member)
    """
    Adds a new member to the PPE contest.
    - Creates their first PPE (PPE #1)
    - Sets it active
    - Gives them access to all PPE commands
    """
    guild_id = ctx.guild.id
    records = await load_player_records(guild_id)
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

    await save_player_records(guild_id=guild_id, records=records)
    await ctx.reply(f"✅ Added **{member.display_name}** to the PPE contest and created **PPE #1** as their active PPE.")

@bot.command(name="removeplayer", help="Remove a player and all their PPE data from the contest.")
# @commands.has_role("PPE Admin")
@require_ppe_roles(admin_required=True)
async def removeplayer(ctx: commands.Context, member: discord.Member):
    await remove_ppe_player_role(ctx, member)
    guild_id = ctx.guild.id
    records = await load_player_records(guild_id)
    key = member.display_name.lower()

    if key not in records or not records[key].get("is_member", False):
        return await ctx.reply(f"❌ {member.display_name} is not in the PPE contest.")

    # Confirm removal
    del records[key]
    await save_player_records(guild_id=guild_id, records=records)

    await ctx.reply(f"🗑️ Removed **{member.display_name}** and all their PPE data from the contest.")



@bot.command(name="myppe", help="Show all your PPEs and which one is active.")
# @commands.has_role("PPE Player")
@require_ppe_roles(player_required=True)
async def myppe(ctx: commands.Context):
    guild_id = ctx.guild.id
    records = await load_player_records(guild_id)
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
    guild_id = ctx.guild.id
    records = await load_player_records(guild_id)

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
# @commands.has_role("PPE Admin")
@require_ppe_roles(admin_required=True)
async def set_ppe_channel(ctx: commands.Context):
    channel_id = ctx.channel.id
    channels = load_ppe_channels()
    if channel_id in channels:
        return await ctx.reply("⚠️ This channel is already set as a PPE channel.")

    channels.append(channel_id)
    save_ppe_channels(channels)
    await ctx.reply(f"✅ Added **#{ctx.channel.name}** as a PPE channel.")


@bot.command(name="unsetppechannel", help="Remove this channel from PPE channels.")
# @commands.has_role("PPE Admin")
@require_ppe_roles(admin_required=True)
async def unset_ppe_channel(ctx: commands.Context):
    channel_id = ctx.channel.id
    channels = load_ppe_channels()
    if channel_id not in channels:
        return await ctx.reply("⚠️ This channel is not currently a PPE channel.")

    channels.remove(channel_id)
    save_ppe_channels(channels)
    await ctx.reply(f"🗑️ Removed **#{ctx.channel.name}** from the PPE channel list.")


@bot.command(name="listppechannels", help="Show all channels marked as PPE channels.")
# @commands.has_role("PPE Admin")
@require_ppe_roles(admin_required=True)
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
        "setuproles": "Check and create required PPE roles in this server.",
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
@require_ppe_roles()
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
@require_ppe_roles(admin_required=True)
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
@require_ppe_roles(admin_required=True)
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

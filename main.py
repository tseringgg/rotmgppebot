import io

from IPython import embed
from anyio import Path
from dataclass import Loot, PPEData, ROTMGClass
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import aiosqlite
import os
import json

from utils.find_items import find_items_in_image
from utils.calc_points import calc_points, calculate_loot_points, load_loot_points
from utils.player_records import get_active_ppe, load_player_records, save_player_records, ensure_player_exists
from utils.role_checks import require_ppe_roles



DUNGEONS = [
    "Pirate Cave", "Forest Maze", "Spider Den", "Forbidden Jungle", "The Hive",
    "Snake Pit", "Sprite World", "Cave of a Thousand Treasures", "Ancient Ruins", "Magic Woods", 
    "Candyland Hunting Grounds", "Undead Lair", "Puppet Master's Theatre", "Toxic Sewers", "Cursed Library", "Mad Lab","Abyss of Demons",
    "Manor of the Immortals", "Haunted Cemetery", "The Machine", "Davy Jones' Locker", "Ocean Trench", "The Crawling Depths", "Woodland Labyrinth",
    "Deadwater Docks", "Puppet Master's Encore", "Cnidarian Reef", "Parasite Chambers", "The Tavern", "Sulfurous Wetlands", "Mountain Temple", 
    "Lair of Draconis", "Tomb of the Ancients", "The Third Dimension", "Lair of Shaitan", "Secluded Thicket", "High Tech Terror", "Ice Citadel", "Moonlight Village",
    "The Nest", "Cultist Hideout", "Fungal Cavern", "Crystal Cavern", "Spectral Penitentiary", "Kogbold Steamworks", "Lost Halls", "The Void", "The Shatters",
    "Heroic Undead Lair", "Infernal Abyss of Demons", "Plagued Nest", "Advanced Kogbold Steamworks", 
    "Oryx's Castle", "Oryx's Chamber", "Wine Cellar", "Oryx's Sanctuary",
    "Malogia", "Untaris", "Katalund", "Forax",
    "Legacy Heroic Undead Lair", "Legacy Heroic Abyss of Demons",
    "Rainbow Road", "Santa's Workshop", "Ice Tomb", "Battle for the Nexus", "Stromwell's Rift I", "Stromwell's Rift II", "Stromwell's Rift III",
    "Belladonna's Garden", "Queen Bunny Chamber", "Mad God Mayhem", "The Trials of Cronus", "Hidden Interregnum", "Oryxmania", "White Snake Invasion",
    "The Realm"
]

LOOT = [

]

# Autocomplete function
async def class_autocomplete(interaction: discord.Interaction, current: str):
    # Filter based on what the user typed
    matches = [
        c.value for c in ROTMGClass
        if current.lower() in c.value.lower()
    ]

    # Discord only allows up to 25 choices
    return [
        app_commands.Choice(name=m, value=m)
        for m in matches[:25]
    ]

async def dungeon_autocomplete(interaction: discord.Interaction, current: str):
    current = current.lower()

    matches = [
        d for d in DUNGEONS
        if current in d.lower()
    ]

    return [
        app_commands.Choice(name=m, value=m)
        for m in matches[:25]
    ]

async def item_name_autocomplete(interaction: discord.Interaction, current: str):

    current_lower = current.lower()

    matches = [
        app_commands.Choice(name=pretty, value=pretty)
        for pretty in LOOT
        if current_lower in pretty.lower()
    ]

    return matches[:25]



SERVER1_ID = 879497062117412924 # Last Oasis
SERVER2_ID = 1435436110829326459 # Test Server

guilds = [discord.Object(id=SERVER1_ID), discord.Object(id=SERVER2_ID)]

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

class PPEBot(commands.Bot):
    async def setup_hook(self):
        # Print to confirm commands are loaded BEFORE syncing
        print("Loaded commands:", [cmd.name for cmd in self.tree.get_commands()])

        # Sync to guilds (FAST commands)
        for guild in guilds:
            print(f"Syncing commands to guild {guild.id}...")
            try:
                await self.tree.sync(guild=guild)
            except Exception as e:
                print(f"[ERROR] Failed to sync commands to guild {guild.id}: {e}")

        print("Guild commands synced!")

        EXCEPTIONS = {"of", "the"}

        loot_points = load_loot_points()  # load once at startup

        for internal_name in loot_points.keys():

            # exclude shiny variants
            if "(shiny)" in internal_name:
                continue

            # normalize capitalization
            words = internal_name.split(" ")
            pretty = " ".join(
                word.lower() if word.lower() in EXCEPTIONS
                else word.capitalize()
                for word in words
            )

            LOOT.append(pretty)


intents = discord.Intents.default()
intents.message_content = True



# bot = commands.Bot(command_prefix="!", intents=intents)
bot = PPEBot(command_prefix="!", intents=intents)

@bot.event
async def on_guild_join(guild: discord.Guild | None):
    if not guild:
        print("[WARN] on_guild_join called with no guild.")
        return
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
    setup_msg = "👋 `PPE Bot Setup Complete!`\n\n"
    if created_roles:
        setup_msg += f"✅ Created roles: {', '.join(created_roles)}\n"
    else:
        setup_msg += "ℹ️ Required roles already existed.\n"
    setup_msg += (
        "\n`Assign roles:`\n"
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

@bot.tree.command(name="setuproles", description="Check and create required PPE roles in this server.", guilds=guilds)
@commands.has_permissions(manage_roles=True)
async def setup_roles(interaction: discord.Interaction):
    await on_guild_join(interaction.guild)
    await interaction.response.send_message("🔁 Setup roles check complete.")


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


# @bot.tree.command(name="ping", description="Replies with Pong!", guilds=guilds)
# async def ping(interaction: discord.Interaction):
#     await interaction.response.send_message("Pong!")

@bot.tree.command(name="newppe", description="Create a new PPE (max 10) and make it your active one.", guilds=guilds)
@app_commands.describe(class_name="Choose your class")
@app_commands.autocomplete(class_name=class_autocomplete)
@require_ppe_roles(player_required=True)
async def newppe(interaction: discord.Interaction, class_name: str):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    # --- Validate class name ---
    if class_name not in [c.value for c in ROTMGClass]:
        return await interaction.response.send_message(
            f"❌ `{class_name}` is not a valid RotMG class.\n"
            f"Use the autocomplete list to choose one.",
            ephemeral=True
        )
    else:
        class_name = [c for c in ROTMGClass if c.value == class_name][0]

    guild_id = interaction.guild.id
    records = await load_player_records(guild_id)
    key = ensure_player_exists(records, interaction.user.display_name.lower())
    # players can make ppe

    # # if key not in records, make new entry
    # if key not in records:
    #     records[key] = {"ppes": [], "active_ppe": None, "is_member": True}
    player_data = records[key]

    # --- PPE limit check ---
    ppe_count = len(player_data.ppes)
    if ppe_count >= 10:
        return await interaction.response.send_message(
            "⚠️ You’ve reached the limit of `10 PPEs`. "
            "Delete or reuse an existing one before making a new one."
        )


    # --- Create new PPE ---
    next_id = max((ppe.id for ppe in player_data.ppes), default=0) + 1

    new_ppe = PPEData(
        id=next_id,
        name=class_name,
        points=0,
        loot=[]
    )

    player_data.ppes.append(new_ppe)
    player_data.active_ppe = next_id

    await save_player_records(guild_id=guild_id, records=records)

    await interaction.response.send_message(
        f"✅ Created `PPE #{next_id}` for your `{class_name.value}` "
        f"and set it as your active PPE.\n"
        f"You now have {ppe_count + 1}/10 PPEs."
    )


@bot.tree.command(name="setactiveppe", description="Set which PPE is active for point tracking.", guilds=guilds)
@require_ppe_roles(player_required=True)
async def setactiveppe(interaction: discord.Interaction, ppe_id: int):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    guild_id = interaction.guild.id
    records = await load_player_records(guild_id)
    key = ensure_player_exists(records, interaction.user.display_name)
    player_data = records[key]

    ppe_ids = [ppe.id for ppe in player_data.ppes]
    if ppe_id not in ppe_ids:
        return await interaction.response.send_message(f"❌ You don’t have a PPE #{ppe_id}. Use `/newppe` to create one.")

    player_data.active_ppe = ppe_id
    active_ppe = get_active_ppe(player_data)
    if not active_ppe:
        return await interaction.response.send_message("❌ Could not find your active PPE record. Try creating a new one with `/newppe`.")
    await save_player_records(guild_id=guild_id, records=records)
    # await interaction.response.send_message(f"> ✅ Set **PPE #{ppe_id}** ({active_ppe.name}) as your active PPE.")

    player_data = records[key]
    active_id = player_data.active_ppe
    # lines = [f"`{interaction.user.display_name}'s` PPEs:"]
    lines = []
    for ppe in sorted(player_data.ppes, key=lambda x: x.id):
        id_ = ppe.id
        pts = ppe.points  # ✅
        marker = " (Active)"
        pts_str = f"{int(pts)}" if pts == int(pts) else f"{pts:.1f}"

        if id_ == active_id:
            # Format points without decimal if whole number
            lines.append(f"**#{id_} {ppe.name}: {pts_str} points {marker}**")
        else:
            lines.append(f"*#{id_} {ppe.name}: {pts_str} points*")

    embed = discord.Embed(
        title=f"{interaction.user.display_name}'s PPEs",
        description="\n".join(lines),
        color=discord.Color.blue()
    )
    # for line in lines:
    #     embed.add_field(name="", value=line, inline=False)

    await interaction.response.send_message(content=f"> ✅ Set **PPE #{ppe_id}** ({active_ppe.name}) as your active PPE.",
                                    embed=embed, ephemeral=False)  # public response



        
@bot.event
async def on_message(message: discord.Message):
    if message.guild is None:
        return # Ignore DMs
    guild_id = message.guild.id
    if message.author == bot.user:
        return

    await bot.process_commands(message)

import cv2
import numpy as np


@bot.tree.command(name="submitloot", description="Submit loot for point tracking.", guilds=guilds)
@app_commands.describe(dungeon="Choose the dungeon you completed", screenshot="Upload a screenshot of your loot")
@app_commands.autocomplete(dungeon=dungeon_autocomplete)
@require_ppe_roles(player_required=True)
async def submitloot(
    interaction: discord.Interaction,
    dungeon: str,
    screenshot: discord.Attachment
):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    guild_id = interaction.guild.id
    records = await load_player_records(guild_id)
    key = interaction.user.display_name.lower()
    
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
    if dungeon not in DUNGEONS:
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
                final_key, points = await add_loot_to_player(interaction=interaction, item_name=item_name, divine=detected_loot["divine"], shiny=detected_loot["shiny"])
                message += f"• **{final_key}** (+{points} points)\n"
            except (ValueError, KeyError) as e:
                return await interaction.followup.send(str(e), ephemeral=True)

        await interaction.followup.send(message, ephemeral=False)

            # await interaction.response.send_message(
            #     f"✅ Added **{final_key}** to your active PPE for {points} points.",
            #     ephemeral=False
            # )
    
    
@bot.tree.command(name="addloot", description="Add an item to your active PPE's loot.", guilds=guilds)
@app_commands.describe(item_name="Name of the item to add", divine="Is the item divine?", shiny="Is the item shiny?")
@app_commands.autocomplete(item_name=item_name_autocomplete)
@require_ppe_roles(player_required=True)
async def addloot(

        interaction: discord.Interaction,
        item_name: str,
        divine: bool = False,
        shiny: bool = False
    ):
        try:
            final_key, points = await add_loot_to_player(interaction, item_name, divine, shiny)
        except (ValueError, KeyError) as e:
            return await interaction.response.send_message(str(e), ephemeral=True)

        # await interaction.response.send_message(
        #     f"> ✅ Added **{final_key}** to your active PPE for {points} points.",
        #     ephemeral=False
        # )

        # member is the command caller
        member = interaction.user
    
        guild = interaction.guild

        if guild is None:
            await interaction.response.send_message(
                "❌ This command can only be used inside a server.",
                ephemeral=True
            )
            return

        # Load PPE records
        guild_id = guild.id
        records = await load_player_records(guild_id)

        # Normalize key
        key = ensure_player_exists(records, member.display_name.lower())

        # ------------------------------------------------------------
        # GUARD 3: Member has no PPE records
        # ------------------------------------------------------------
        if key not in records:
            await interaction.response.send_message(
                f"❌ {member.mention} has no PPE data in this server.",
                ephemeral=True
            )
            return

        player_data = records[key]

        # ------------------------------------------------------------
        # GUARD 4: Member has PPE records but no PPE runs
        # ------------------------------------------------------------
        if not player_data.ppes:
            await interaction.response.send_message(
                f"ℹ️ {member.mention} exists in PPE data but has **no PPE runs**.",
                ephemeral=True
            )
            return

        # ------------------------------------------------------------
        # GUARD 5: Member has no active PPE
        # ------------------------------------------------------------
        active_ppe = get_active_ppe(player_data)
        if not active_ppe:
            await interaction.response.send_message(
                f"ℹ️ {member.mention} has **no active PPE**.",
                ephemeral=True
            )
            return

        # ------------------------------------------------------------
        # GUARD 6: Active PPE has no loot
        # ------------------------------------------------------------
        loot_dict = active_ppe.loot
        if not loot_dict:
            await interaction.response.send_message(
                f"ℹ️ {member.mention}'s active PPE has **no loot recorded**.",
                ephemeral=True
            )
            return

        # Build loot listing (sorted alphabetically)
        loot_lines = []
        for loot in loot_dict:
            if loot.item_name == final_key:
                loot_lines.append(f"• **{loot.item_name} × {loot.quantity}**")
            else:
                loot_lines.append(f"• *{loot.item_name} × {loot.quantity}*")

        embed = discord.Embed(
            title=f"Loot for your {active_ppe.name} (PPE #{active_ppe.id}) ({int(active_ppe.points) if active_ppe.points == int(active_ppe.points) else f'{active_ppe.points:.1f}'} points)",
            description="\n".join(loot_lines),
            color=discord.Color.blue()
        )

        await interaction.response.send_message(content=f"> ✅ Added **{final_key}** to your active PPE for {points} points.",
                                                embed=embed, ephemeral=False) # public response, not ephemeral

async def add_loot_to_player(
        interaction: discord.Interaction,
        item_name: str,
        divine: bool = False,
        shiny: bool = False
):
    if item_name not in LOOT:
        raise NameError(
            f"❌ `{item_name}` is not a recognized item name.\n"
            f"Use the autocomplete suggestions to select a valid item."
        )
    guild = interaction.guild
    user = interaction.user

    # GUARD 1: Must be used in a guild
    if guild is None:
        raise KeyError(
            "❌ This command can only be used in a server."
        )

    guild_id = guild.id

    # item_name = item_name.strip().lower()

    try:
        points = await calc_points(guild_id, user.display_name, item_name, divine, shiny)
    except ValueError as e:
        raise e


    records = await load_player_records(guild_id)
    key = ensure_player_exists(records, user.display_name.lower())


    # GUARD 2: Player must exist in PPE records
    if key not in records:
        raise KeyError(
            "❌ You are not registered in the PPE system."
        )

    player_data = records[key]

    # GUARD 3: Player must have an active PPE
    active_ppe = get_active_ppe(player_data)
    if not active_ppe:
        raise KeyError(
            "❌ You do not have an active PPE."
        )


    # Normalize item name
    base_name = item_name.strip()

    # Generate variant suffix
    suffix_parts = []
    if divine:
        suffix_parts.append("(divine)")
    if shiny:
        suffix_parts.append("(shiny)")

    if suffix_parts:
        final_key = f"{base_name} " + " ".join(suffix_parts)
    else:
        final_key = base_name

    # Increment loot count
    match = next((loot for loot in active_ppe.loot if loot.item_name == final_key), None)
    if match:
        match.quantity += 1
    else:
        active_ppe.loot.append(Loot(item_name=final_key, quantity=1))
    await save_player_records(guild_id, records)


    try:
        await addpoints(interaction, points)
    except (ValueError, KeyError, LookupError) as e:
        raise e
    return final_key, points
    

@bot.tree.command(name="removeloot", description="Remove an item from your active PPE's loot.", guilds=guilds)
@app_commands.describe(item_name="Name of the item to remove", divine="Is the item divine?", shiny="Is the item shiny?")
@app_commands.autocomplete(item_name=item_name_autocomplete)
@require_ppe_roles(player_required=True)
async def removeloot(
        interaction: discord.Interaction,
        item_name: str,
        divine: bool = False,
        shiny: bool = False
    ):
        if item_name not in LOOT:
            await interaction.response.send_message(
                f"❌ `{item_name}` is not a recognized item name.\n"
                f"Use the autocomplete suggestions to select a valid item.",
                ephemeral=True
            )
            return
        guild = interaction.guild
        user = interaction.user

        #  Guard 1 — must be in guild
        if guild is None:
            await interaction.response.send_message(
                "❌ This command can only be used in a server.",
                ephemeral=True
            )
            return

        records = await load_player_records(guild.id)
        key = ensure_player_exists(records, user.display_name.lower())

        #  Guard 2 — player must exist
        if key not in records:
            await interaction.response.send_message(
                "❌ You are not registered in the PPE system.",
                ephemeral=True
            )
            return

        player_data = records[key]

        #  Guard 3 — active PPE must exist
        active_ppe = get_active_ppe(player_data)
        if not active_ppe:
            await interaction.response.send_message(
                "❌ You do not have an active PPE.",
                ephemeral=True
            )
            return


        #  Build final loot key
        final_key = item_name.strip()  # pretty base name

        suffixes = []
        if divine:
            suffixes.append("(divine)")
        if shiny:
            suffixes.append("(shiny)")

        if suffixes:
            final_key = final_key + " " + " ".join(suffixes)


        item = next((loot for loot in active_ppe.loot if loot.item_name == final_key), None)
        #  Guard 4 — item must exist
        if not item:
            await interaction.response.send_message(
                f"❌ Your active PPE does not contain any **{final_key}**.",
                ephemeral=True
            )
            return

        #  Guard 5 — count must be > 0
        if item.quantity <= 0:
            await interaction.response.send_message(
                f"❌ No remaining copies of **{final_key}** to remove.",
                ephemeral=True
            )
            return

        #  Remove one
        item.quantity -= 1

        # If count hits 0, remove entry
        if item.quantity <= 0:
            active_ppe.loot.remove(item)
        await save_player_records(guild.id, records)

        try:
            points = await calc_points(guild.id, user.display_name, item_name, divine, shiny)
        except ValueError as e:
            return await interaction.response.send_message(str(e), ephemeral=True)

        try:
            await addpoints(interaction, -points)
        except (ValueError, KeyError, LookupError) as e:
            return await interaction.response.send_message(str(e), ephemeral=True)

        # await interaction.response.send_message(
        #     f"> 🗑️ Removed **1x {final_key}** from your active PPE and took away {points} points.",
        #     ephemeral=False
        # )

        member = interaction.user
    
        guild = interaction.guild

        if guild is None:
            await interaction.response.send_message(
                "❌ This command can only be used inside a server.",
                ephemeral=True
            )
            return

        # Load PPE records
        guild_id = guild.id
        records = await load_player_records(guild_id)

        # Normalize key
        key = ensure_player_exists(records, member.display_name.lower())

        # ------------------------------------------------------------
        # GUARD 3: Member has no PPE records
        # ------------------------------------------------------------
        if key not in records:
            await interaction.response.send_message(
                f"❌ {member.mention} has no PPE data in this server.",
                ephemeral=True
            )
            return

        player_data = records[key]

        # ------------------------------------------------------------
        # GUARD 4: Member has PPE records but no PPE runs
        # ------------------------------------------------------------
        if not player_data.ppes:
            await interaction.response.send_message(
                f"ℹ️ {member.mention} exists in PPE data but has **no PPE runs**.",
                ephemeral=True
            )
            return

        # ------------------------------------------------------------
        # GUARD 5: Member has no active PPE
        # ------------------------------------------------------------
        active_ppe = get_active_ppe(player_data)
        if not active_ppe:
            await interaction.response.send_message(
                f"ℹ️ {member.mention} has **no active PPE**.",
                ephemeral=True
            )
            return

        # ------------------------------------------------------------
        # GUARD 6: Active PPE has no loot
        # ------------------------------------------------------------
        loot_dict = active_ppe.loot
        if not loot_dict:
            await interaction.response.send_message(
                f"ℹ️ {member.mention}'s active PPE has **no loot recorded**.",
                ephemeral=True
            )
            return

        # Build loot listing (sorted alphabetically)
        loot_lines = []
        for loot in loot_dict:
            if loot.item_name == final_key:
                loot_lines.append(f"• **{loot.item_name} × {loot.quantity}**")
            else:
                loot_lines.append(f"• *{loot.item_name} × {loot.quantity}*")

        embed = discord.Embed(
            title=f"Loot for your {active_ppe.name} (PPE #{active_ppe.id}) ({int(active_ppe.points) if active_ppe.points == int(active_ppe.points) else f'{active_ppe.points:.1f}'} points)",
            description="\n".join(loot_lines),
            color=discord.Color.blue()
        )

        await interaction.response.send_message(content=f"> 🗑️ Removed **1x {final_key}** from your active PPE and took away {points} points.",
                                                embed=embed, ephemeral=False) # public response, not ephemeral


    
@bot.tree.command(name="addpointsfor", description="Add points to another player's active PPE.", guilds=guilds)
# @commands.has_role("PPE Admin")  # both can use
@require_ppe_roles(admin_required=True)
async def addpointsfor(interaction: discord.Interaction, member: discord.Member, amount: float):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    guild_id = interaction.guild.id
    records = await load_player_records(guild_id)
    key = member.display_name.lower()

    if key not in records or not records[key].is_member:
        return await interaction.response.send_message(f"❌ {member.display_name} is not part of the PPE contest.")

    player_data = records[key]
    active_id = player_data.active_ppe
    if not active_id:
        return await interaction.response.send_message(f"❌ {member.display_name} does not have an active PPE.")

    active_ppe = next((p for p in player_data.ppes if p.id == active_id), None)
    if not active_ppe:
        return await interaction.response.send_message(f"❌ Could not find {member.display_name}'s active PPE record.")
    import math
    amount = math.floor(amount * 2) / 2
    active_ppe.points += amount
    await save_player_records(guild_id=guild_id, records=records)

    await interaction.response.send_message(f"✅ Added `{amount:.1f}` points to `{member.display_name}`’s active PPE (PPE #{active_id}).\n"
                    f"`New total:` {active_ppe.points:.1f} points.")

# @bot.tree.command(name="addpoints", description="Add points to your active PPE.", guilds=guilds)
# # @commands.has_role("PPE Player")
# @require_ppe_roles(player_required=True)
async def addpoints(interaction: discord.Interaction, amount: float):
    if not interaction.guild:
        raise KeyError("❌ This command can only be used in a server.")
    if amount == 0:
        raise ValueError("⚠️ No points were added or subtracted since the amount was `0`.")
    guild_id = interaction.guild.id
    records = await load_player_records(guild_id)
    key = interaction.user.display_name.lower()

    # Must be a contest member
    if key not in records or not records[key].is_member:
        raise KeyError("❌ You’re not part of the PPE contest. Ask a mod to add you with `/addplayer @you`.")
    player_data = records[key]
    active_id = player_data.active_ppe
    if not active_id:
        raise LookupError("❌ You don’t have an active PPE. Use `/newppe` to create one first.")
    # Find the active PPE
    active_ppe = next((p for p in player_data.ppes if p.id == active_id), None)
    if not active_ppe:
        raise LookupError("❌ Could not find your active PPE record. Try creating a new one with `/newppe`.")
    # Add points (rounded down to nearest 0.5)
    import math
    amount = math.floor(amount * 2) / 2
    active_ppe.points += amount
    await save_player_records(guild_id=guild_id, records=records)

    # if amount > 0:
    #     return await interaction.response.send_message(f"✅ Added `{amount:.1f}` points to your `{active_ppe.name}` (PPE #{active_id}).\n"
    #                 f"New total: `{active_ppe.points:.1f}` points.")

    # elif amount < 0:
    #     return await interaction.response.send_message(f"✅ Subtracted `{amount:.1f}` points from your `{active_ppe.name}` (PPE #{active_id}).\n"
    #                 f"New total: `{active_ppe.points:.1f}` points.")
    # else:
    #     return await interaction.followup.send(f"⚠️ No points were added or subtracted since the amount was `0`.")


@bot.tree.command(name="listplayers", description="Show all current participants in the PPE contest.", guilds=guilds)
# @commands.has_role("PPE Admin")
@require_ppe_roles(admin_required=True)
async def listplayers(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    guild_id = interaction.guild.id
    records = await load_player_records(guild_id)

    # Get all members who are marked as PPE participants
    members = [(name, data) for name, data in records.items() if data.is_member]

    if not members:
        return await interaction.response.send_message("❌ No one has been added to the PPE contest yet.")

    lines = ["`🏆 Current PPE Contest Participants 🏆`"]
    for name, data in members:
        ppe_count = len(data.ppes)
        active_id = data.active_ppe if data.active_ppe is not None else "None"
        lines.append(f"• `{name.title()}` — {ppe_count} PPE(s), Active: PPE #{active_id}")

    await interaction.response.send_message("\n".join(lines))

@bot.tree.command(name="myloot", description="Show all loot for your active PPE.", guilds=guilds)
@require_ppe_roles(player_required=True)
async def myloot(interaction: discord.Interaction):
        # member is the command caller
        member = interaction.user
    
        guild = interaction.guild

        if guild is None:
            await interaction.response.send_message(
                "❌ This command can only be used inside a server.",
                ephemeral=True
            )
            return

        # Load PPE records
        guild_id = guild.id
        records = await load_player_records(guild_id)

        # Normalize key
        key = ensure_player_exists(records, member.display_name.lower())

        # ------------------------------------------------------------
        # GUARD 3: Member has no PPE records
        # ------------------------------------------------------------
        if key not in records:
            await interaction.response.send_message(
                f"❌ {member.mention} has no PPE data in this server.",
                ephemeral=True
            )
            return

        player_data = records[key]

        # ------------------------------------------------------------
        # GUARD 4: Member has PPE records but no PPE runs
        # ------------------------------------------------------------
        if not player_data.ppes:
            await interaction.response.send_message(
                f"ℹ️ {member.mention} exists in PPE data but has **no PPE runs**.",
                ephemeral=True
            )
            return

        # ------------------------------------------------------------
        # GUARD 5: Member has no active PPE
        # ------------------------------------------------------------
        active_ppe = get_active_ppe(player_data)
        if not active_ppe:
            await interaction.response.send_message(
                f"ℹ️ {member.mention} has **no active PPE**.",
                ephemeral=True
            )
            return

        # ------------------------------------------------------------
        # GUARD 6: Active PPE has no loot
        # ------------------------------------------------------------
        loot_dict = active_ppe.loot
        if not loot_dict:
            await interaction.response.send_message(
                f"ℹ️ {member.mention}'s active PPE has **no loot recorded**.",
                ephemeral=True
            )
            return

        # Build loot listing (sorted alphabetically)
        loot_lines = []
        for loot in loot_dict:
            loot_lines.append(f"• {loot.item_name} × {loot.quantity}")

        embed = discord.Embed(
            title=f"Loot for your {active_ppe.name} (PPE #{active_ppe.id})",
            description="\n".join(loot_lines),
            color=discord.Color.blue()
        )

        await interaction.response.send_message(embed=embed, ephemeral=False) # public response, not ephemeral


@bot.tree.command(name="addplayer", description="Add a player to the PPE contest.", guilds=guilds)
# @commands.has_role("PPE Admin")
@require_ppe_roles(admin_required=True)
async def addplayer(interaction: discord.Interaction, member: discord.Member):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    """Gives the PPE Player role silently and lets the caller handle responses."""
    role = discord.utils.get(interaction.guild.roles, name="PPE Player")
    if not role:
        return await interaction.response.send_message("❌ PPE Player role not found. Create it first.")

    guild_id = interaction.guild.id
    records = await load_player_records(guild_id)
    key = ensure_player_exists(records, member.display_name.lower())

    if role in member.roles:
        records[key].is_member = True
        await save_player_records(guild_id=guild_id, records=records)

        return await interaction.response.send_message(f"⚠️ `{member.display_name}` already has the `PPE Player` role.")

    try:
        await member.add_roles(role)
    
        # Confirm removal
        # del records[key]
        records[key].is_member = True
        await save_player_records(guild_id=guild_id, records=records)
        return await interaction.response.send_message(f"✅ Added `{member.display_name}` to the PPE contest. They can now use PPE commands.")
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to manage that role. Move my bot role higher in the hierarchy.")


@bot.tree.command(name="removeplayer", description="Remove a player and all their PPE data from the contest.", guilds=guilds)
# @commands.has_role("PPE Admin")
@require_ppe_roles(admin_required=True)
async def removeplayer(interaction: discord.Interaction, member: discord.Member):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    role = discord.utils.get(interaction.guild.roles, name="PPE Player")
    if not role:
        await interaction.response.send_message("❌ PPE Player role not found. Create it first.")

    guild_id = interaction.guild.id
    records = await load_player_records(guild_id)
    key = member.display_name.lower()

    if role not in member.roles:
        records[key].is_member = False
        await save_player_records(guild_id=guild_id, records=records)

        return await interaction.response.send_message(f"⚠️ `{member.display_name}` already does not have the `PPE Player` role.")

    try:
        if role is not None:
            await member.remove_roles(role)
    
        # Confirm removal
        # del records[key]
        records[key].is_member = False
        await save_player_records(guild_id=guild_id, records=records)
        return await interaction.response.send_message(f"✅ Removed `{member.display_name}` from the PPE contest. They will no longer show on leaderboards or be able to use PPE commands.")
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to manage that role. Move my bot role higher in the hierarchy.")

    



@bot.tree.command(name="myppes", description="Show all your PPEs and which one is active.", guilds=guilds)
# @commands.has_role("PPE Player")
@require_ppe_roles(player_required=True)
async def myppes(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    guild_id = interaction.guild.id
    records = await load_player_records(guild_id)
    key = interaction.user.display_name.lower()

    if key not in records or not records[key].ppes:
        return await interaction.response.send_message("❌ You don’t have any PPEs yet. Use `/newppe` to create one!")

    player_data = records[key]
    active_id = player_data.active_ppe
    # lines = [f"`{interaction.user.display_name}'s` PPEs:"]
    lines = []
    for ppe in sorted(player_data.ppes, key=lambda x: x.id):
        id_ = ppe.id
        pts = ppe.points  # ✅
        marker = " (Active)"
        pts_str = f"{int(pts)}" if pts == int(pts) else f"{pts:.1f}"

        if id_ == active_id:
            # Format points without decimal if whole number
            lines.append(f"**#{id_} {ppe.name}: {pts_str} points {marker}**")
        else:
            lines.append(f"*#{id_} {ppe.name}: {pts_str} points*")

    embed = discord.Embed(
        title=f"{interaction.user.display_name}'s PPEs",
        description="\n".join(lines),
        color=discord.Color.blue()
    )
    # for line in lines:
    #     embed.add_field(name="", value=line, inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=False)  # public response

# delete all ppes for a user
@bot.tree.command(name="deleteallppes", description="Delete all your PPEs.", guilds=guilds)
@require_ppe_roles(admin_required=True)
async def delete_all_ppes(interaction: discord.Interaction, member: discord.Member):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    guild_id = interaction.guild.id
    records = await load_player_records(guild_id)
    key = member.display_name.lower()

    if key not in records or not records[key].ppes:
        return await interaction.response.send_message("❌ You don’t have any PPEs to delete.")

    # Clear all PPEs for the user
    records[key].ppes = []
    records[key].active_ppe = None
    await save_player_records(guild_id=guild_id, records=records)
    await interaction.response.send_message("✅ All your PPEs have been deleted.")

@bot.tree.command(name="leaderboard", description="Show the best PPE from each player.", guilds=guilds)
async def leaderboard(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    guild_id = interaction.guild.id
    records = await load_player_records(guild_id)

    leaderboard_data = []
    for player, data in records.items():
        # if player is not a contest member, skip
        if not data.is_member:
            continue
        if not data.ppes:
            continue
        best_ppe = max(data.ppes, key=lambda p: p.points)
        leaderboard_data.append((player, best_ppe.name, best_ppe.points))

    leaderboard_data.sort(key=lambda x: x[2], reverse=True)

    # if leaderboard is empty
    if not leaderboard_data:
        return await interaction.response.send_message("❌ No PPE data available yet.")

    lines = ["🏆 `PPE Leaderboard` 🏆"]
    for rank, (player, ppe_id, pts) in enumerate(leaderboard_data, start=1):
        lines.append(f"{rank}. `{player.title()}` — `{ppe_id}`: `{pts:.1f}` points")

    await interaction.response.send_message("\n".join(lines))


import json, os


@bot.tree.command(name="ppehelp", description="Show available PPE commands for players and admins.", guilds=guilds)
async def ppehelp(interaction: discord.Interaction):
    # --- Commands for everyone ---
    everyone_cmds = {
        "leaderboard": "Show the current PPE leaderboard.",
        "ppehelp": "Show this help message.",
        "listroles": "List all roles in this server.",
    }
    # --- Player Commands ---
    player_cmds = {
        "myppes": "View your current PPE stats or progress.",
        "newppe": "Start a new PPE run and track your progress.",
        "setactiveppe": "Set which of your PPE characters is currently active.",
        "addloot": "Add loot to your active PPE manually.",
        "removeloot": "Remove loot from your active PPE manually.",
        "myloot": "Show all loot recorded for your active PPE.",
        "submitloot": "Submit a loot screenshot for point tracking automatically.",
    }

    # --- Admin Commands ---
    admin_cmds = {
        # "listppechannels": "List all channels marked as PPE channels.",
        # "setppechannel": "Mark this channel as a PPE channel.",
        # "unsetppechannel": "Remove this channel from PPE channels.",
        "addplayer": "Add a member to the PPE contest.",
        "removeplayer": "Remove a member from the PPE contest.",
        "listplayers": "List all current participants in the PPE contest.",
        "addpointsfor": "Add points to another player's active PPE.",
        "deleteallppes": "Delete all PPEs for a specified player.",
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
        ),
        color=discord.Color.blurple()
    )

    # --- Format everyone commands ---
    everyone_text = "\n".join([f"`/{cmd}` — {desc}" for cmd, desc in everyone_cmds.items()])
    embed.add_field(name="⚪ Everyone Commands", value=everyone_text or "None available", inline=False)

    # --- Format player commands ---
    player_text = "\n".join([f"`/{cmd}` — {desc}" for cmd, desc in player_cmds.items()])
    embed.add_field(name="🟢 PPE Player Commands", value=player_text or "None available", inline=False)

    # --- Format admin commands ---
    admin_text = "\n".join([f"`/{cmd}` — {desc}" for cmd, desc in admin_cmds.items()])
    embed.add_field(name="🔴 PPE Admin Commands", value=admin_text or "None available", inline=False)

    # --- Format owner commands ---
    owner_text = "\n".join([f"`/{cmd}` — {desc}" for cmd, desc in owner_cmds.items()])
    embed.add_field(name="🔒 Owner Commands", value=owner_text or "None available", inline=False)

    # --- Footer ---
    embed.set_footer(text="PPE Bot by LogicVoid — use /ppehelp anytime for command info")
    await interaction.response.send_message(embed=embed, ephemeral=True)

###############
#### ROLES ####
###############

# --- Give PPE Admin role ---
@bot.tree.command(name="giveppeadminrole", description="Give the PPE Admin role to a member. Admin only.", guilds=guilds)
@commands.has_permissions(manage_roles=True)
@require_ppe_roles()
async def give_ppe_admin_role(interaction: discord.Interaction, member: discord.Member):
    if not interaction.guild:
        await interaction.response.send_message("❌ This command can only be used in a server.")
        return
    role = discord.utils.get(interaction.guild.roles, name="PPE Admin")
    if not role:
        await interaction.response.send_message("❌ PPE Admin role not found. Create it first.")
        return

    try:
        await member.add_roles(role)
        await interaction.response.send_message(f"✅ Gave `PPE Admin` role to `{member.display_name}`.")
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to manage that role. Move my bot role higher in the hierarchy.")


# --- Remove PPE Admin role ---
@bot.tree.command(name="removeppeadminrole", description="Remove the PPE Admin role from a member. Admin only.", guilds=guilds)
@commands.has_permissions(manage_roles=True)
async def remove_ppe_admin_role(interaction: discord.Interaction, member: discord.Member):
    if not interaction.guild:
        await interaction.response.send_message("❌ This command can only be used in a server.")
        return
    role = discord.utils.get(interaction.guild.roles, name="PPE Admin")
    if not role:
        await interaction.response.send_message("❌ PPE Admin role not found.")
        return

    try:
        await member.remove_roles(role)
        await interaction.response.send_message(f"✅ Removed `PPE Admin` role from `{member.display_name}`.")
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to manage that role. Move my bot role higher in the hierarchy.")


# --- Command: list roles ---
@bot.tree.command(name="listroles", description="List all roles in this server.", guilds=guilds)
async def list_roles(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("❌ This command can only be used in a server.")
        return
    roles = [r.name for r in interaction.guild.roles if r.name != "@everyone"]
    await interaction.response.send_message("🎭 Available roles:\n" + "\n".join(f"- {r}" for r in roles))


if not DISCORD_TOKEN:
    print("Error: DISCORD_TOKEN environment variable not set.")
    exit(1)
bot.run(DISCORD_TOKEN)

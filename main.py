from slash_commands import addbonus_cmd, addbonusfor_cmd, addloot_cmd, addlootfor_cmd, addpenalties_cmd, addpenaltiesfor_cmd, addplayer_cmd, addpointsfor_cmd, deleteallppes_cmd, giveppeadminrole_cmd, inspectloot_cmd, leaderboard_cmd, listplayers_cmd, listroles_cmd, myloot_cmd, myppes_cmd, newppe_cmd, ppehelp_cmd, refreshallpoints_cmd, refreshpointsfor_cmd, removebonus_cmd, removebonusfrom_cmd, removeloot_cmd, removelootfrom_cmd, removeplayer_cmd, removeppeadminrole_cmd, setactiveppe_cmd, submitloot_cmd, deleteppe_cmd, listadmins_cmd, shareloot_cmd, shareseasonloot_cmd, addseasonloot_cmd, addseasonlootfor_cmd, removeseasonloot_cmd, removeseasonlootfor_cmd, showseasonloot_cmd, seasonleaderboard_cmd, resetseason_cmd, migrateapostrophes_cmd, addteam_cmd, addplayer_team_cmd, leaveteam_cmd, teamleaderboard_cmd, myteam_cmd, updateteam_cmd, deleteteam_cmd, characterleaderboard_cmd, listcharactersfor_cmd
import discord 
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import aiosqlite
import os
from utils.role_checks import require_ppe_roles
from utils.loot_data import init_loot_data
from create_loot_table import create_loot_background_and_mapping

from utils.autocomplete import class_autocomplete, item_name_autocomplete, bonus_autocomplete, user_bonus_autocomplete, target_user_bonus_autocomplete, target_user_ppe_id_autocomplete, team_name_autocomplete

SERVER1_ID = 879497062117412924 # Last Oasis
# SERVER2_ID = 1435436110829326459 # Test Server

guilds = [discord.Object(id=SERVER1_ID)] #, discord.Object(id=SERVER2_ID)]

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

class PPEBot(commands.Bot):
    async def setup_hook(self):

        # Initialize global loot data for autocomplete
        init_loot_data()
        
        # Generate background image and sprite mapping for shareloot system
        try:
            print("Generating loot background and sprite mapping...")
            result = create_loot_background_and_mapping()
            if result:
                background_path, csv_path = result
            else:
                background_path, csv_path = None, None
                print("[WARN] create_loot_background_and_mapping() returned None")
            print(f"✅ Background: {background_path}, Mapping: {csv_path}")
        except Exception as e:
            print(f"[ERROR] Failed to generate loot background: {e}")
        
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


intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Enable members intent

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


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.event
async def on_message(message: discord.Message):
    if message.guild is None:
        return # Ignore DMs
    guild_id = message.guild.id
    if message.author == bot.user:
        return

    await bot.process_commands(message)

@bot.tree.command(name="setuproles", description="Check and create required PPE roles in this server.", guilds=guilds)
@commands.has_permissions(manage_roles=True)
async def setup_roles(interaction: discord.Interaction):
    await on_guild_join(interaction.guild)
    await interaction.response.send_message("🔁 Setup roles check complete.")


######################
### COMMANDS BELOW ###
######################

@bot.tree.command(name="newppe", description="Create a new PPE (max 10) and make it your active one.", guilds=guilds)
@app_commands.describe(class_name="Choose your class")
@app_commands.describe(pet_level="Level of your max pet ability -1st one (0-100)")
@app_commands.describe(num_exalts="Number of exalts (0-40)")
@app_commands.describe(percent_loot="Percent loot boost from exalts (0-25%)")
@app_commands.describe(incombat_reduction="In-combat damage reduction seconds (0, .2, .4, .6, .8, 1)")
@app_commands.autocomplete(class_name=class_autocomplete)
@require_ppe_roles(player_required=True)
async def newppe(interaction: discord.Interaction, class_name: str, pet_level: int, num_exalts: int, percent_loot: float, incombat_reduction: float):
    await newppe_cmd.command(interaction, class_name, pet_level, num_exalts, percent_loot, incombat_reduction)

@bot.tree.command(name="setactiveppe", description="Set which PPE is active for point tracking.", guilds=guilds)
@require_ppe_roles(player_required=True)
async def setactiveppe(interaction: discord.Interaction, ppe_id: int):
    await setactiveppe_cmd.command(interaction, ppe_id)


# @bot.tree.command(name="submitloot", description="Submit loot for point tracking.", guilds=guilds)
# @app_commands.describe(dungeon="Choose the dungeon you completed", screenshot="Upload a screenshot of your loot")
# @app_commands.autocomplete(dungeon=dungeon_autocomplete)
# @require_ppe_roles(player_required=True)
# async def submitloot(
#     interaction: discord.Interaction,
#     dungeon: str,
#     screenshot: discord.Attachment
# ):
#     await submitloot_cmd.command(interaction, dungeon, screenshot)
    
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
    await addloot_cmd.command(interaction, item_name, divine, shiny)

@bot.tree.command(name="addlootfor", description="Add an item to another player's specific PPE. Admin only.", guilds=guilds)
@app_commands.describe(user="The player to add loot to", id="The PPE ID to target", item_name="Name of the item to add", divine="Is the item divine?", shiny="Is the item shiny?")
@app_commands.autocomplete(item_name=item_name_autocomplete)
@require_ppe_roles(admin_required=True)
async def addlootfor(
        interaction: discord.Interaction,
        user: discord.Member,
        id: int,
        item_name: str,
        divine: bool = False,
        shiny: bool = False
    ):
    await addlootfor_cmd.command(interaction, user, id, item_name, divine, shiny)

@bot.tree.command(name="addbonus", description="Add a bonus to your active PPE.", guilds=guilds)
@app_commands.describe(bonus_name="Name of the bonus to add")
@app_commands.autocomplete(bonus_name=bonus_autocomplete)
@require_ppe_roles(player_required=True)
async def addbonus(
        interaction: discord.Interaction,
        bonus_name: str
    ):
    await addbonus_cmd.command(interaction, bonus_name)

@bot.tree.command(name="removebonus", description="Remove a bonus from your active PPE.", guilds=guilds)
@app_commands.describe(bonus_name="Name of the bonus to remove")
@app_commands.autocomplete(bonus_name=user_bonus_autocomplete)
@require_ppe_roles(player_required=True)
async def removebonus(
        interaction: discord.Interaction,
        bonus_name: str
    ):
    await removebonus_cmd.command(interaction, bonus_name)

@bot.tree.command(name="addbonusfor", description="Add a bonus to another player's specific PPE. Admin only.", guilds=guilds)
@app_commands.describe(user="The player to add bonus to", id="The PPE ID to target", bonus_name="Name of the bonus to add")
@app_commands.autocomplete(bonus_name=bonus_autocomplete)
@require_ppe_roles(admin_required=True)
async def addbonusfor(
        interaction: discord.Interaction,
        user: discord.Member,
        id: int,
        bonus_name: str
    ):
    await addbonusfor_cmd.command(interaction, user, id, bonus_name)

@bot.tree.command(name="removebonusfrom", description="Remove a bonus from another player's specific PPE. Admin only.", guilds=guilds)
@app_commands.describe(user="The player to remove bonus from", id="The PPE ID to target", bonus_name="Name of the bonus to remove")
@app_commands.autocomplete(bonus_name=target_user_bonus_autocomplete)
@require_ppe_roles(admin_required=True)
async def removebonusfrom(
        interaction: discord.Interaction,
        user: discord.Member,
        id: int,
        bonus_name: str
    ):
    await removebonusfrom_cmd.command(interaction, user, id, bonus_name)

@bot.tree.command(name="addpenalties", description="Add penalty bonuses to your active PPE.", guilds=guilds)
@app_commands.describe(
    pet_level="Pet level (0-100)", 
    num_exalts="Number of exalts (0-40)", 
    percent_loot="Loot boost percentage (0-25)", 
    incombat_reduction="In-combat damage reduction (0, 0.2, 0.4, 0.6, 0.8, 1.0)"
)
@require_ppe_roles(player_required=True)
async def addpenalties(
        interaction: discord.Interaction,
        pet_level: int,
        num_exalts: int,
        percent_loot: float,
        incombat_reduction: float
    ):
    await addpenalties_cmd.command(interaction, pet_level, num_exalts, percent_loot, incombat_reduction)

@bot.tree.command(name="addpenaltiesfor", description="Add penalty bonuses to another player's specific PPE. Admin only.", guilds=guilds)
@app_commands.describe(
    user="The player whose PPE to add penalties to", 
    id="The PPE ID to target", 
    pet_level="Pet level (0-100)", 
    num_exalts="Number of exalts (0-40)", 
    percent_loot="Loot boost percentage (0-25)", 
    incombat_reduction="In-combat damage reduction (0, 0.2, 0.4, 0.6, 0.8, 1.0)"
)
@require_ppe_roles(admin_required=True)
async def addpenaltiesfor(
        interaction: discord.Interaction,
        user: discord.Member,
        id: int,
        pet_level: int,
        num_exalts: int,
        percent_loot: float,
        incombat_reduction: float
    ):
    await addpenaltiesfor_cmd.command(interaction, user, id, pet_level, num_exalts, percent_loot, incombat_reduction)

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
    await removeloot_cmd.command(interaction, item_name, divine, shiny)

@bot.tree.command(name="removelootfrom", description="Remove an item from another player's specific PPE. Admin only.", guilds=guilds)
@app_commands.describe(user="The player to remove loot from", id="The PPE ID to target", item_name="Name of the item to remove", divine="Is the item divine?", shiny="Is the item shiny?")
@app_commands.autocomplete(item_name=item_name_autocomplete)
@require_ppe_roles(admin_required=True)
async def removelootfrom(
        interaction: discord.Interaction,
        user: discord.Member,
        id: int,
        item_name: str,
        divine: bool = False,
        shiny: bool = False
    ):
    await removelootfrom_cmd.command(interaction, user, id, item_name, divine, shiny)

@bot.tree.command(name="addpointsfor", description="Add points to another player's active PPE.", guilds=guilds)
# @commands.has_role("PPE Admin")  # both can use
@require_ppe_roles(admin_required=True)
async def addpointsfor(interaction: discord.Interaction, member: discord.Member, ppe_id: int, amount: float):
    await addpointsfor_cmd.command(interaction, member, ppe_id, amount)

@bot.tree.command(name="refreshpointsfor", description="Recalculate and fix the point total for a specific PPE. Admin only.", guilds=guilds)
@app_commands.describe(user="The player whose PPE to refresh", id="The PPE ID to recalculate")
@require_ppe_roles(admin_required=True)
async def refreshpointsfor(interaction: discord.Interaction, user: discord.Member, id: int):
    await refreshpointsfor_cmd.command(interaction, user, id)

@bot.tree.command(name="refreshallpoints", description="Recalculate and fix point totals for ALL PPEs in the server. Admin only.", guilds=guilds)
@require_ppe_roles(admin_required=True)
async def refreshallpoints(interaction: discord.Interaction):
    await refreshallpoints_cmd.command(interaction)

@bot.tree.command(name="listplayers", description="Show all current participants in the PPE contest.", guilds=guilds)
# @commands.has_role("PPE Admin")
@require_ppe_roles(admin_required=True)
async def listplayers(interaction: discord.Interaction):
    await listplayers_cmd.command(interaction)

@bot.tree.command(name="listcharactersfor", description="Show all characters and their IDs for a specific player. Admin only.", guilds=guilds)
@app_commands.describe(member="The player whose characters to list")
@require_ppe_roles(admin_required=True)
async def listcharactersfor(interaction: discord.Interaction, member: discord.Member):
    await listcharactersfor_cmd.command(interaction, member)

@bot.tree.command(name="myloot", description="Show all loot for your active PPE.", guilds=guilds)
@require_ppe_roles(player_required=True)
async def myloot(interaction: discord.Interaction):
    await myloot_cmd.command(interaction)

@bot.tree.command(name="shareloot", description="Generate a visual loot table showing your active PPE's items.", guilds=guilds)
@require_ppe_roles(player_required=True)
async def shareloot(interaction: discord.Interaction):
    await shareloot_cmd.command(interaction)

@bot.tree.command(name="inspectloot", description="Inspect the loot of another player's specific PPE. Admin only.", guilds=guilds)
@app_commands.describe(user="The player to inspect", id="The PPE ID to inspect")
@app_commands.autocomplete(id=target_user_ppe_id_autocomplete)
@require_ppe_roles(admin_required=True)
async def inspectloot(interaction: discord.Interaction, user: discord.Member, id: int):
    await inspectloot_cmd.command(interaction, user, id)

@bot.tree.command(name="addplayer", description="Add a player to the PPE contest.", guilds=guilds)
@require_ppe_roles(admin_required=True)
async def addplayer(interaction: discord.Interaction, member: discord.Member):
    await addplayer_cmd.command(interaction, member)

@bot.tree.command(name="removeplayer", description="Remove a player and all their PPE data from the contest.", guilds=guilds)
@require_ppe_roles(admin_required=True)
async def removeplayer(interaction: discord.Interaction, member: discord.Member):
    await removeplayer_cmd.command(interaction, member)

@bot.tree.command(name="myppes", description="Show all your PPEs and which one is active.", guilds=guilds)
# @commands.has_role("PPE Player")
@require_ppe_roles(player_required=True)
async def myppes(interaction: discord.Interaction):
    await myppes_cmd.command(interaction)

@bot.tree.command(name="deleteallppes", description="Delete all your PPEs.", guilds=guilds)
@require_ppe_roles(admin_required=True)
async def delete_all_ppes(interaction: discord.Interaction, member: discord.Member):
    await deleteallppes_cmd.command(interaction, member)

@bot.tree.command(name="deleteppe", description="Delete a specific PPE for a member.", guilds=guilds)
@require_ppe_roles(admin_required=True)
async def delete_ppe(interaction: discord.Interaction, member: discord.Member, ppe_id: int):
    await deleteppe_cmd.command(interaction, member, ppe_id)

@bot.tree.command(name="leaderboard", description="Show the best PPE from each player.", guilds=guilds)
async def leaderboard(interaction: discord.Interaction):
    await leaderboard_cmd.command(interaction)

@bot.tree.command(name="characterleaderboard", description="Show the highest point characters of a specific class.", guilds=guilds)
@app_commands.describe(class_name="Choose the class to filter by")
@app_commands.autocomplete(class_name=class_autocomplete)
async def characterleaderboard(interaction: discord.Interaction, class_name: str):
    await characterleaderboard_cmd.command(interaction, class_name)

@bot.tree.command(name="ppehelp", description="Show available PPE commands for players and admins.", guilds=guilds)
async def ppehelp(interaction: discord.Interaction):
    await ppehelp_cmd.command(interaction)

#####################
### SEASON LOOT #####
#####################

@bot.tree.command(name="addseasonloot", description="Add a unique item to your season loot collection.", guilds=guilds)
@app_commands.describe(item_name="Name of the item to add", shiny="Is the item shiny?")
@app_commands.autocomplete(item_name=item_name_autocomplete)
@require_ppe_roles(player_required=True)
async def addseasonloot(
        interaction: discord.Interaction,
        item_name: str,
        shiny: bool = False
    ):
    await addseasonloot_cmd.command(interaction, item_name, shiny)

@bot.tree.command(name="addseasonlootfor", description="Add a unique item to another player's season loot. Admin only.", guilds=guilds)
@app_commands.describe(user="The player to add loot to", item_name="Name of the item to add", shiny="Is the item shiny?")
@app_commands.autocomplete(item_name=item_name_autocomplete)
@require_ppe_roles(admin_required=True)
async def addseasonlootfor(
        interaction: discord.Interaction,
        user: discord.Member,
        item_name: str,
        shiny: bool = False
    ):
    await addseasonlootfor_cmd.command(interaction, user, item_name, shiny)

@bot.tree.command(name="removeseasonloot", description="Remove a unique item from your season loot collection.", guilds=guilds)
@app_commands.describe(item_name="Name of the item to remove", shiny="Is the item shiny?")
@app_commands.autocomplete(item_name=item_name_autocomplete)
@require_ppe_roles(player_required=True)
async def removeseasonloot(
        interaction: discord.Interaction,
        item_name: str,
        shiny: bool = False
    ):
    await removeseasonloot_cmd.command(interaction, item_name, shiny)

@bot.tree.command(name="removeseasonlootfor", description="Remove a unique item from another player's season loot. Admin only.", guilds=guilds)
@app_commands.describe(user="The player to remove loot from", item_name="Name of the item to remove", shiny="Is the item shiny?")
@app_commands.autocomplete(item_name=item_name_autocomplete)
@require_ppe_roles(admin_required=True)
async def removeseasonlootfor(
        interaction: discord.Interaction,
        user: discord.Member,
        item_name: str,
        shiny: bool = False
    ):
    await removeseasonlootfor_cmd.command(interaction, user, item_name, shiny)

@bot.tree.command(name="showseasonloot", description="Show all unique items in your season loot collection.", guilds=guilds)
@require_ppe_roles(player_required=True)
async def showseasonloot(interaction: discord.Interaction):
    await showseasonloot_cmd.command(interaction)

@bot.tree.command(name="shareseasonloot", description="Generate a visual loot table showing all your season loot items.", guilds=guilds)
@require_ppe_roles(player_required=True)
async def shareseasonloot(interaction: discord.Interaction):
    await shareseasonloot_cmd.command(interaction)

@bot.tree.command(name="seasonleaderboard", description="Show leaderboard ranked by unique items collected.", guilds=guilds)
async def seasonleaderboard(interaction: discord.Interaction):
    await seasonleaderboard_cmd.command(interaction)

@bot.tree.command(name="resetseason", description="Reset the season by clearing all unique items for all players. Server owner/admin only.", guilds=guilds)
@commands.has_permissions(administrator=True)
async def resetseason(interaction: discord.Interaction):
    await resetseason_cmd.command(interaction)

# --- Migrate apostrophes ---
@bot.tree.command(name="migrateapostrophes", description="Normalize all apostrophes in player records. Admin only.", guilds=guilds)
@require_ppe_roles(admin_required=True)
async def migrate_apostrophes(interaction: discord.Interaction):
    await migrateapostrophes_cmd.command(interaction)

##################
#### TEAMS ####
##################

# --- Add team ---
@bot.tree.command(name="addteam", description="Create a new team for the PPE contest. Admin only.", guilds=guilds)
@app_commands.describe(team_name="Name of the team", team_leader="The team leader")
@require_ppe_roles(admin_required=True)
async def addteam(interaction: discord.Interaction, team_name: str, team_leader: discord.Member):
    await addteam_cmd.command(interaction, team_name, team_leader)

# --- Add player to team ---
@bot.tree.command(name="addplayer_team", description="Add a player to a team. Team leaders and admins only.", guilds=guilds)
@app_commands.describe(player="The player to add to the team", team_name="Name of the team")
@app_commands.autocomplete(team_name=team_name_autocomplete)
@require_ppe_roles()
async def addplayer_team(interaction: discord.Interaction, player: discord.Member, team_name: str):
    await addplayer_team_cmd.command(interaction, player, team_name)

# --- Remove player from team ---
@bot.tree.command(name="leaveteam", description="Remove a player from their team. Admin only.", guilds=guilds)
@app_commands.describe(player="The player to remove from teams")
@require_ppe_roles(admin_required=True)
async def leaveteam(interaction: discord.Interaction, player: discord.Member):
    await leaveteam_cmd.command(interaction, player)

# --- Team leaderboard ---
@bot.tree.command(name="teamleaderboard", description="Show the team leaderboard.", guilds=guilds)
async def teamleaderboard(interaction: discord.Interaction):
    await teamleaderboard_cmd.command(interaction)

# --- My team ---
@bot.tree.command(name="myteam", description="Show your team members and their rankings. Optional: specify a team name to view.", guilds=guilds)
@app_commands.describe(team_name="Optional: Team name to view (defaults to your team)")
@app_commands.autocomplete(team_name=team_name_autocomplete)
async def myteam(interaction: discord.Interaction, team_name: str = None):
    await myteam_cmd.command(interaction, team_name)

# --- Update team name ---
@bot.tree.command(name="updateteam", description="Update a team's name. Team leaders and admins only.", guilds=guilds)
@app_commands.describe(old_name="Current team name", new_name="New team name")
@app_commands.autocomplete(old_name=team_name_autocomplete)
@require_ppe_roles()
async def updateteam(interaction: discord.Interaction, old_name: str, new_name: str):
    await updateteam_cmd.command(interaction, old_name, new_name)

# --- Delete team ---
@bot.tree.command(name="deleteteam", description="Delete a team and remove all its members. Admin only.", guilds=guilds)
@app_commands.describe(team_name="Name of the team to delete")
@app_commands.autocomplete(team_name=team_name_autocomplete)
@require_ppe_roles(admin_required=True)
async def deleteteam(interaction: discord.Interaction, team_name: str):
    await deleteteam_cmd.command(interaction, team_name)

###############
#### ROLES ####
###############

# --- Give PPE Admin role ---
@bot.tree.command(name="giveppeadminrole", description="Give the PPE Admin role to a member. Admin only.", guilds=guilds)
@commands.has_permissions(manage_roles=True)
@require_ppe_roles()
async def give_ppe_admin_role(interaction: discord.Interaction, member: discord.Member):
    await giveppeadminrole_cmd.command(interaction, member)

# --- Remove PPE Admin role ---
@bot.tree.command(name="removeppeadminrole", description="Remove the PPE Admin role from a member. Admin only.", guilds=guilds)
@commands.has_permissions(manage_roles=True)
async def remove_ppe_admin_role(interaction: discord.Interaction, member: discord.Member):
    await removeppeadminrole_cmd.command(interaction, member)

# --- Command: list roles ---
@bot.tree.command(name="listroles", description="List all roles in this server.", guilds=guilds)
async def list_roles(interaction: discord.Interaction):
    await listroles_cmd.list_roles(interaction)

@bot.tree.command(name="listadmins", description="List all PPE Admins in the server.", guilds=guilds)
async def list_admins_cmd_handler(interaction: discord.Interaction):
    await listadmins_cmd.list_admins(interaction)

if not DISCORD_TOKEN:
    print("Error: DISCORD_TOKEN environment variable not set.")
    exit(1)
bot.run(DISCORD_TOKEN)

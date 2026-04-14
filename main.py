from slash_commands import (
    addadmin_cmd,
    addbonus_cmd,
    addbonusfor_cmd,
    addloot_cmd,
    addlootfor_cmd,
    addplayer_cmd,
    addpointsfor_cmd,
    addseasonloot_cmd,
    addseasonlootfor_cmd,
    addtoteam_cmd,
    forcereset_cmd,
    leaderboard_cmd,
    listadmins_cmd,
    listplayers_cmd,
    listroles_cmd,
    manageplayer_cmd,
    managequests_cmd,
    manageseason_cmd,
    managesniffer_cmd,
    manageteams_cmd,
    myinfo_cmd,
    myloot_cmd,
    myquests_cmd,
    mysniffer_cmd,
    myteam_cmd,
    newppe_cmd,
    ppehelp_cmd,
    refreshallpoints_cmd,
    refreshpointsfor_cmd,
    removebonus_cmd,
    removebonusfrom_cmd,
    removefromteam_cmd,
    removeloot_cmd,
    removelootfrom_cmd,
    removeseasonloot_cmd,
    removeseasonlootfrom_cmd,
    setactiveppe_cmd,
    submitloot_cmd,
)
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import os
import asyncio
import random
import json
import time
from utils.role_checks import require_ppe_roles, require_server_owner
from utils.loot_data import init_loot_data
from utils.settings.channel_settings import get_item_suggestions_enabled
from utils.item_suggestion import handle_item_suggestion
from utils.contest_join_embed import handle_join_contest_reaction, handle_leave_contest_reaction
from create_loot_table import create_loot_background_and_mapping
from utils.ppe_types import DEFAULT_PPE_TYPE, normalize_allowed_ppe_types, ppe_type_label
from utils.guild_config import load_guild_config
from utils.sniffer_helpers.realmshark_ingest_server import start_realmshark_ingest_server
from utils.sniffer_helpers.realmshark_notifier import build_realmshark_notifier

from utils.autocomplete import class_autocomplete, item_name_autocomplete, bonus_autocomplete, user_bonus_autocomplete, target_user_bonus_autocomplete, team_name_autocomplete, rarity_autocomplete

SERVER1_ID = 879497062117412924 # Last Oasis
SERVER2_ID = 1435436110829326459 # Test Server
SERVER3_ID = 1485395885666992248 # My Testing Server

guilds = [discord.Object(id=SERVER1_ID), discord.Object(id=SERVER2_ID), discord.Object(id=SERVER3_ID)]

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")


def _env_flag(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return max(minimum, default)

    try:
        parsed = int(raw_value)
    except ValueError:
        return max(minimum, default)

    return max(minimum, parsed)


SYNC_COMMANDS_ON_STARTUP = _env_flag("PPE_SYNC_COMMANDS_ON_STARTUP", default=True)
SYNC_MAX_RETRIES = _env_int("PPE_SYNC_MAX_RETRIES", default=2, minimum=1)
SYNC_COOLDOWN_SECONDS = _env_int("PPE_SYNC_COOLDOWN_SECONDS", default=300, minimum=0)
SYNC_STATE_PATH = os.getenv("PPE_SYNC_STATE_PATH", "/data/ppe_command_sync_state.json")

class PPEBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._startup_sync_attempted = False
        self.realmshark_ingest_runner = None

    async def _sync_app_commands_to_guilds(self) -> None:
        if self._startup_sync_attempted:
            print("Skipping startup slash-command sync (already attempted in this process).")
            return

        self._startup_sync_attempted = True

        if not SYNC_COMMANDS_ON_STARTUP:
            print("Skipping startup slash-command sync (PPE_SYNC_COMMANDS_ON_STARTUP=false).")
            return

        if SYNC_COOLDOWN_SECONDS > 0:
            last_sync_epoch = self._load_last_sync_epoch()
            if last_sync_epoch is not None:
                elapsed = time.time() - last_sync_epoch
                if elapsed < SYNC_COOLDOWN_SECONDS:
                    remaining = max(0.0, SYNC_COOLDOWN_SECONDS - elapsed)
                    print(
                        "Skipping startup slash-command sync "
                        f"(cooldown active, {remaining:.0f}s remaining)."
                    )
                    return

        print("Loaded commands:", [cmd.name for cmd in self.tree.get_commands()])

        any_sync_succeeded = False

        for guild in guilds:
            for sync_attempt in range(1, SYNC_MAX_RETRIES + 1):
                print(
                    f"Syncing commands to guild {guild.id} "
                    f"(attempt {sync_attempt}/{SYNC_MAX_RETRIES})..."
                )
                try:
                    await self.tree.sync(guild=guild)
                    any_sync_succeeded = True
                    break
                except discord.errors.HTTPException as e:
                    if not _is_global_rate_limit_error(e):
                        print(f"[ERROR] Failed to sync commands to guild {guild.id}: {e}")
                        break

                    retry_after = _extract_retry_after_seconds(e)
                    wait_time = retry_after if retry_after is not None else max(2.0, 2.0 * sync_attempt)

                    if sync_attempt >= SYNC_MAX_RETRIES:
                        print(
                            f"[ERROR] Global rate limit while syncing guild {guild.id}; "
                            "skipping further sync attempts for this guild."
                        )
                        break

                    print(
                        f"[WARN] Global rate limit while syncing guild {guild.id}. "
                        f"Waiting {wait_time:.1f}s before retry."
                    )
                    await asyncio.sleep(wait_time)
                except Exception as e:
                    print(f"[ERROR] Failed to sync commands to guild {guild.id}: {e}")
                    break

        if any_sync_succeeded:
            self._save_last_sync_epoch(time.time())

        print("Startup slash-command sync completed.")

    def _load_last_sync_epoch(self) -> float | None:
        try:
            with open(SYNC_STATE_PATH, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception:
            return None

        if not isinstance(payload, dict):
            return None

        raw_value = payload.get("last_sync_epoch")
        try:
            parsed = float(raw_value)
        except (TypeError, ValueError):
            return None

        return parsed if parsed > 0 else None

    def _save_last_sync_epoch(self, epoch: float) -> None:
        payload = {"last_sync_epoch": float(epoch)}
        sync_dir = os.path.dirname(SYNC_STATE_PATH)
        temp_path = f"{SYNC_STATE_PATH}.tmp"

        try:
            if sync_dir:
                os.makedirs(sync_dir, exist_ok=True)
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f)
            os.replace(temp_path, SYNC_STATE_PATH)
        except Exception as e:
            print(f"[WARN] Failed to persist command sync timestamp: {e}")

    async def setup_hook(self):

        # Initialize global loot data for autocomplete
        init_loot_data()
        
        # Generate 4 background images and sprite mappings for shareloot system
        try:
            print("Generating 4 loot background variants and sprite mappings...")
            create_loot_background_and_mapping()
            print("✅ All loot backgrounds and mappings generated successfully!")
        except Exception as e:
            print(f"[ERROR] Failed to generate loot backgrounds: {e}")

        await self._sync_app_commands_to_guilds()

        if self.realmshark_ingest_runner is None:
            self.realmshark_ingest_runner = await start_realmshark_ingest_server(
                notifier=build_realmshark_notifier(self)
            )

    async def close(self):
        runner = getattr(self, "realmshark_ingest_runner", None)
        if runner is not None:
            await runner.cleanup()
            self.realmshark_ingest_runner = None
        await super().close()


intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Enable members intent

bot = PPEBot(command_prefix="!", intents=intents)


async def ppe_type_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    if interaction.guild is None:
        return [app_commands.Choice(name=ppe_type_label(DEFAULT_PPE_TYPE), value=DEFAULT_PPE_TYPE)]

    guild_config = await load_guild_config(interaction)
    ppe_settings = guild_config.get("ppe_settings", {}) if isinstance(guild_config.get("ppe_settings", {}), dict) else {}
    if not bool(ppe_settings.get("enable_ppe_types", True)):
        return [app_commands.Choice(name=ppe_type_label(DEFAULT_PPE_TYPE), value=DEFAULT_PPE_TYPE)]

    allowed = normalize_allowed_ppe_types(ppe_settings.get("allowed_ppe_types"))
    current_text = str(current or "").casefold().strip()
    matches: list[app_commands.Choice[str]] = []

    for ppe_type in allowed:
        label = ppe_type_label(ppe_type)
        if current_text and current_text not in label.casefold() and current_text not in ppe_type.casefold():
            continue
        matches.append(app_commands.Choice(name=label, value=ppe_type))

    return matches[:25]

@bot.event
async def on_guild_join(
    guild: discord.Guild | None,
    announce_channel: discord.abc.Messageable | None = None,
):
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

    # Find a channel to send the message.
    channel = announce_channel
    if channel is None:
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
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    await handle_join_contest_reaction(bot, payload)


@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    await handle_leave_contest_reaction(bot, payload)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    # Role/permission checks already provide user-facing feedback in the predicate.
    if isinstance(error, app_commands.CheckFailure):
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "🚫 You do not have permission to use this command.",
                ephemeral=True,
            )

@bot.event
async def on_message(message: discord.Message):
    if message.guild is None:
        return # Ignore DMs
    guild_id = message.guild.id
    if message.author.bot:
        return
    # print("Message received")
    # --- Image attachment listener ---
    # Collect all image attachments (png, jpg, jpeg, webp)
    attachments = [
        a for a in message.attachments
        if a.filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
    ]
    if not attachments:
        return

    channel_id = message.channel.id
    print(
        f"[listener] received message with {len(attachments)} image attachment(s) "
        f"guild={guild_id} channel={channel_id}"
    )

    # Check whether item suggestions are enabled for this channel
    enabled = await get_item_suggestions_enabled(str(guild_id), str(channel_id))
    print(
        f"[listener] item_suggestions_enabled={enabled} "
        f"guild={guild_id} channel={channel_id}"
    )
    if not enabled:
        return

    await handle_item_suggestion(message, attachments)

@bot.tree.command(name="setuproles", description="Check and create required PPE roles in this server.", guilds=guilds)
@commands.has_permissions(manage_roles=True)
async def setup_roles(interaction: discord.Interaction):
    await on_guild_join(interaction.guild, announce_channel=interaction.channel)
    await interaction.response.send_message("🔁 Setup roles check complete.")


######################
### COMMANDS BELOW ###
######################

@bot.tree.command(name="newppe", description="Create a new PPE and make it your active one.", guilds=guilds)
@app_commands.describe(class_name="Choose your class")
@app_commands.describe(pet_level="Level of your max pet ability -1st one (0-100)")
@app_commands.describe(num_exalts="Number of exalts (0-40)")
@app_commands.describe(percent_loot="Percent loot boost from exalts (0-25%)")
@app_commands.describe(incombat_reduction="In-combat damage reduction seconds (0, 0.2, 0.4, 0.6, 0.8, 1.0)")
@app_commands.describe(ppe_type="Optional PPE type (defaults to Regular PPE)")
@app_commands.autocomplete(class_name=class_autocomplete)
@app_commands.autocomplete(ppe_type=ppe_type_autocomplete)
@require_ppe_roles(player_required=True)
async def newppe(
    interaction: discord.Interaction,
    class_name: str,
    pet_level: int,
    num_exalts: int,
    percent_loot: float,
    incombat_reduction: float,
    ppe_type: str | None = None,
):
    await newppe_cmd.command(interaction, class_name, pet_level, num_exalts, percent_loot, incombat_reduction, ppe_type)

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
@app_commands.describe(item_name="Name of the item to add", shiny="Is the item shiny?", rarity="Item rarity (defaults to common)")
@app_commands.autocomplete(item_name=item_name_autocomplete, rarity=rarity_autocomplete)
@require_ppe_roles(player_required=True)
async def addloot(
        interaction: discord.Interaction,
        item_name: str,
        shiny: bool = False,
        rarity: str = "common"
    ):
    await addloot_cmd.command(interaction, item_name, shiny, rarity)

@bot.tree.command(name="addlootfor", description="Add an item to another player's specific PPE. Admin only.", guilds=guilds)
@app_commands.describe(user="The player to add loot to", id="The PPE ID to target", item_name="Name of the item to add", shiny="Is the item shiny?", rarity="Item rarity (defaults to common)")
@app_commands.autocomplete(item_name=item_name_autocomplete, rarity=rarity_autocomplete)
@require_ppe_roles(admin_required=True)
async def addlootfor(
        interaction: discord.Interaction,
        user: discord.Member,
        id: int,
        item_name: str,
        shiny: bool = False,
        rarity: str = "common"
    ):
    await addlootfor_cmd.command(interaction, user, id, item_name, shiny, rarity)

@bot.tree.command(name="addbonus", description="Add a bonus to your active PPE.", guilds=guilds)
@app_commands.describe(bonus_name="Name of the bonus to add")
@app_commands.autocomplete(bonus_name=bonus_autocomplete)
@require_ppe_roles(player_required=True)
async def addbonus(interaction: discord.Interaction, bonus_name: str):
    await addbonus_cmd.command(interaction, bonus_name)

@bot.tree.command(name="removebonus", description="Remove a bonus from your active PPE.", guilds=guilds)
@app_commands.describe(bonus_name="Name of the bonus to remove")
@app_commands.autocomplete(bonus_name=user_bonus_autocomplete)
@require_ppe_roles(player_required=True)
async def removebonus(interaction: discord.Interaction, bonus_name: str):
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



@bot.tree.command(name="removeloot", description="Remove an item from your active PPE's loot.", guilds=guilds)
@app_commands.describe(item_name="Name of the item to remove", rarity="Item rarity", shiny="Is the item shiny?")
@app_commands.autocomplete(item_name=item_name_autocomplete, rarity=rarity_autocomplete)
@require_ppe_roles(player_required=True)
async def removeloot(
        interaction: discord.Interaction,
        item_name: str,
        rarity: str,
        shiny: bool = False
    ):
    await removeloot_cmd.command(interaction, item_name, rarity, shiny)

@bot.tree.command(name="removelootfrom", description="Remove an item from another player's specific PPE. Admin only.", guilds=guilds)
@app_commands.describe(user="The player to remove loot from", id="The PPE ID to target", item_name="Name of the item to remove", rarity="Item rarity", shiny="Is the item shiny?")
@app_commands.autocomplete(item_name=item_name_autocomplete, rarity=rarity_autocomplete)
@require_ppe_roles(admin_required=True)
async def removelootfrom(
        interaction: discord.Interaction,
        user: discord.Member,
        id: int,
        item_name: str,
        rarity: str,
        shiny: bool = False
    ):
    await removelootfrom_cmd.command(interaction, user, id, item_name, rarity, shiny)

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



@bot.tree.command(name="myquests", description="Show your current and completed account quests.", guilds=guilds)
@require_ppe_roles(player_required=True)
async def myquests(interaction: discord.Interaction):
    await myquests_cmd.command(interaction)

@bot.tree.command(name="myinfo", description="Open your PPE info dashboard and quick actions.", guilds=guilds)
@require_ppe_roles(player_required=True)
async def myinfo(interaction: discord.Interaction):
    await myinfo_cmd.command(interaction)

@bot.tree.command(name="manageplayer", description="Open admin menu to manage a player's PPE data. Admin only.", guilds=guilds)
@app_commands.describe(member="The player to manage (if in server)", user_id="The discord ID of the player to manage (if not in server)")
@require_ppe_roles(admin_required=True)
async def manageplayer(interaction: discord.Interaction, member: discord.Member | None = None, user_id: str | None = None):
    await manageplayer_cmd.command(interaction, member=member, user_id=user_id)

@bot.tree.command(name="addplayer", description="Add a player to the PPE contest.", guilds=guilds)
@require_ppe_roles(admin_required=True)
async def addplayer(interaction: discord.Interaction, member: discord.Member):
    await addplayer_cmd.command(interaction, member)


@bot.tree.command(name="addadmin", description="Add PPE Admin role to a member.", guilds=guilds)
@require_ppe_roles(admin_required=True)
async def addadmin(interaction: discord.Interaction, member: discord.Member):
    await addadmin_cmd.command(interaction, member)


@bot.tree.command(name="forcereset", description="Force wipe all stored bot data for this guild (server owner only).", guilds=guilds)
@require_server_owner()
async def forcereset(interaction: discord.Interaction):
    await forcereset_cmd.command(interaction)







@bot.tree.command(name="leaderboard", description="Open the leaderboard menu.", guilds=guilds)
async def leaderboard(interaction: discord.Interaction):
    await leaderboard_cmd.command(interaction)

@bot.tree.command(name="ppehelp", description="Show available PPE commands for players and admins.", guilds=guilds)
async def ppehelp(interaction: discord.Interaction):
    await ppehelp_cmd.command(interaction)

#####################
### SEASON LOOT #####
#####################

@bot.tree.command(name="addseasonloot", description="Add a unique item to your season loot collection.", guilds=guilds)
@app_commands.describe(item_name="Name of the item to add", shiny="Is the item shiny?", rarity="Item rarity (defaults to common)")
@app_commands.autocomplete(item_name=item_name_autocomplete, rarity=rarity_autocomplete)
@require_ppe_roles(player_required=True)
async def addseasonloot(
        interaction: discord.Interaction,
        item_name: str,
        shiny: bool = False,
        rarity: str = "common"
    ):
    await addseasonloot_cmd.command(interaction, item_name, shiny, rarity)

@bot.tree.command(name="addseasonlootfor", description="Add a unique item to another player's season loot. Admin only.", guilds=guilds)
@app_commands.describe(user="The player to add loot to", item_name="Name of the item to add", shiny="Is the item shiny?", rarity="Item rarity (defaults to common)")
@app_commands.autocomplete(item_name=item_name_autocomplete, rarity=rarity_autocomplete)
@require_ppe_roles(admin_required=True)
async def addseasonlootfor(
        interaction: discord.Interaction,
        user: discord.Member,
        item_name: str,
        shiny: bool = False,
        rarity: str = "common"
    ):
    await addseasonlootfor_cmd.command(interaction, user, item_name, shiny, rarity)

@bot.tree.command(name="removeseasonloot", description="Remove a unique item from your season loot collection.", guilds=guilds)
@app_commands.describe(item_name="Name of the item to remove", shiny="Is the item shiny?", rarity="Item rarity (defaults to common)")
@app_commands.autocomplete(item_name=item_name_autocomplete, rarity=rarity_autocomplete)
@require_ppe_roles(player_required=True)
async def removeseasonloot(
        interaction: discord.Interaction,
        item_name: str,
        shiny: bool = False,
        rarity: str = "common"
    ):
    await removeseasonloot_cmd.command(interaction, item_name, shiny, rarity)

@bot.tree.command(name="removeseasonlootfrom", description="Remove a unique item from another player's season loot. Admin only.", guilds=guilds)
@app_commands.describe(user="The player to remove loot from", item_name="Name of the item to remove", shiny="Is the item shiny?", rarity="Item rarity (defaults to common)")
@app_commands.autocomplete(item_name=item_name_autocomplete, rarity=rarity_autocomplete)
@require_ppe_roles(admin_required=True)
async def removeseasonlootfrom(
        interaction: discord.Interaction,
        user: discord.Member,
        item_name: str,
        shiny: bool = False,
        rarity: str = "common"
    ):
    await removeseasonlootfrom_cmd.command(interaction, user, item_name, shiny, rarity)

@bot.tree.command(name="myloot", description="Show all loot for your active PPE.", guilds=guilds)
@require_ppe_roles(player_required=True)
async def myloot(interaction: discord.Interaction):
    await myloot_cmd.command(interaction)

@bot.tree.command(name="managequests", description="View or update quest settings and leaderboard points. Admin only.", guilds=guilds)
@require_ppe_roles(admin_required=True)
async def managequests(interaction: discord.Interaction):
    await managequests_cmd.command(interaction)

@bot.tree.command(name="manageseason", description="Open season admin controls (reset season, point settings, contests, picture suggestions).", guilds=guilds)
@require_ppe_roles(admin_required=True)
async def manageseason(interaction: discord.Interaction):
    await manageseason_cmd.command(interaction)

@bot.tree.command(name="mysniffer", description="Open your sniffer setup and character configuration menu.", guilds=guilds)
@require_ppe_roles(player_required=True)
async def mysniffer(interaction: discord.Interaction):
    await mysniffer_cmd.command(interaction)

@bot.tree.command(name="managesniffer", description="Open admin sniffer controls for this guild.", guilds=guilds)
@require_ppe_roles(admin_required=True)
async def managesniffer(interaction: discord.Interaction):
    await managesniffer_cmd.command(interaction)

##################
#### TEAMS ####
##################

@bot.tree.command(name="manageteams", description="Open admin menu to create and manage teams. Admin only.", guilds=guilds)
@require_ppe_roles(admin_required=True)
async def manageteams(interaction: discord.Interaction):
    await manageteams_cmd.command(interaction)

# --- My team ---
@bot.tree.command(name="myteam", description="Show your team members and their rankings. Optional: specify a team name to view.", guilds=guilds)
@app_commands.describe(team_name="Optional: Team name to view (defaults to your team)")
@app_commands.autocomplete(team_name=team_name_autocomplete)
async def myteam(interaction: discord.Interaction, team_name: str = None):
    await myteam_cmd.command(interaction, team_name)

# --- Add player to team ---
@bot.tree.command(name="addtoteam", description="Add a player to a team. Admin only.", guilds=guilds)
@app_commands.describe(
    team_name="Name of the team to add to",
    player="The Discord user to add (mention or name)",
    player_id="Alternative: Discord ID of player (if not using player parameter)"
)
@app_commands.autocomplete(team_name=team_name_autocomplete)
@require_ppe_roles(admin_required=True)
async def addtoteam(
    interaction: discord.Interaction,
    team_name: str,
    player: discord.User | None = None,
    player_id: int | None = None,
):
    await addtoteam_cmd.command(interaction, team_name, player, player_id)

# --- Remove player from team ---
@bot.tree.command(name="removefromteam", description="Remove a player from a team. Admin only.", guilds=guilds)
@app_commands.describe(
    team_name="Name of the team to remove from",
    player="The Discord user to remove (mention or name)",
    player_id="Alternative: Discord ID of player (if not using player parameter)"
)
@app_commands.autocomplete(team_name=team_name_autocomplete)
@require_ppe_roles(admin_required=True)
async def removefromteam(
    interaction: discord.Interaction,
    team_name: str,
    player: discord.User | None = None,
    player_id: int | None = None,
):
    await removefromteam_cmd.command(interaction, team_name, player, player_id)

###############
#### ROLES ####
###############

# --- Command: list roles ---
@bot.tree.command(name="listroles", description="List all roles in this server.", guilds=guilds)
async def list_roles(interaction: discord.Interaction):
    await listroles_cmd.list_roles(interaction)

@bot.tree.command(name="listadmins", description="List all PPE Admins in the server.", guilds=guilds)
async def list_admins_cmd_handler(interaction: discord.Interaction):
    await listadmins_cmd.list_admins(interaction)

def _is_global_rate_limit_error(exc: discord.errors.HTTPException) -> bool:
    if getattr(exc, "status", None) == 429:
        return True
    message = str(exc)
    return "You are being blocked from accessing our API" in message or "global rate limit" in message.lower()


def _decode_http_exception_payload(exc: discord.errors.HTTPException) -> dict | None:
    raw_text = getattr(exc, "text", None)
    if not isinstance(raw_text, str) or not raw_text:
        return None

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return None

    return payload if isinstance(payload, dict) else None


def _extract_retry_after_seconds(exc: discord.errors.HTTPException) -> float | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers:
        retry_after_value = headers.get("Retry-After") or headers.get("X-RateLimit-Reset-After")
        if retry_after_value is not None:
            try:
                return max(0.0, float(retry_after_value))
            except (TypeError, ValueError):
                pass

    # Some Discord errors include retry metadata in the response JSON body.
    payload = _decode_http_exception_payload(exc)
    if isinstance(payload, dict):
        body_retry_after = payload.get("retry_after")
        try:
            if body_retry_after is not None:
                return max(0.0, float(body_retry_after))
        except (TypeError, ValueError):
            pass

    return None


def _format_discord_rate_limit_details(
    exc: discord.errors.HTTPException,
    *,
    attempt: int,
    computed_wait_time: float,
    retry_after_seconds: float | None,
) -> list[str]:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    payload = _decode_http_exception_payload(exc) or {}

    def _header(name: str) -> str | None:
        if not headers:
            return None
        return headers.get(name)

    lines = [
        "[WARN] Discord global rate limit encountered.",
        f"[WARN] attempt={attempt} status={getattr(exc, 'status', 'unknown')} code={getattr(exc, 'code', 'unknown')}",
        f"[WARN] wait_seconds={computed_wait_time:.3f} retry_after_seconds={retry_after_seconds if retry_after_seconds is not None else 'unknown'}",
        f"[WARN] exception_message={str(exc)}",
    ]

    if response is not None:
        response_method = getattr(response, "method", None)
        response_url = getattr(response, "url", None)
        response_reason = getattr(response, "reason", None)
        lines.append(
            "[WARN] response="
            f"method={response_method or 'unknown'} url={response_url or 'unknown'} reason={response_reason or 'unknown'}"
        )

    rate_limit_header_keys = [
        "Retry-After",
        "X-RateLimit-Reset-After",
        "X-RateLimit-Reset",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Bucket",
        "X-RateLimit-Scope",
        "Via",
        "CF-Ray",
    ]

    for key in rate_limit_header_keys:
        value = _header(key)
        if value is not None:
            lines.append(f"[WARN] header[{key}]={value}")

    # Discord typically returns retry_after/global/message in the body for 429 responses.
    body_keys = [
        "message",
        "global",
        "retry_after",
        "code",
        "method",
        "path",
        "route",
    ]
    for key in body_keys:
        if key in payload:
            lines.append(f"[WARN] body[{key}]={payload.get(key)}")

    if payload:
        lines.append(f"[WARN] raw_body={json.dumps(payload, ensure_ascii=True, separators=(',', ':'))}")

    return lines


async def _cleanup_bot_after_failed_login() -> None:
    # Ensure every partially opened Discord/aiohttp resource gets closed before retrying.
    try:
        await bot.close()
    except Exception:
        pass

    try:
        bot.clear()
    except Exception:
        pass


async def run_bot_with_backoff(token: str, max_retries: int = 3):
    """
    Run the bot with exponential backoff on 429 global rate limit errors.
    
    Args:
        token: Discord bot token
        max_retries: Retained for backward compatibility and ignored.
    """
    del max_retries
    base_delay = 5.0  # Start with 5 second delay
    max_backoff_seconds = 300.0
    attempt = 0

    while True:
        attempt += 1
        try:
            print(f"\n[Attempt {attempt}] Logging in to Discord...")
            await bot.start(token)
            return  # Successful connection; run indefinitely
        except discord.errors.LoginFailure:
            await _cleanup_bot_after_failed_login()
            print("[FATAL] Invalid Discord token. Check DISCORD_TOKEN and restart.")
            raise
        except discord.errors.HTTPException as e:
            if _is_global_rate_limit_error(e):
                # Global rate limit hit
                await _cleanup_bot_after_failed_login()

                retry_after = _extract_retry_after_seconds(e)
                delay = min(max_backoff_seconds, base_delay * (2 ** min(8, attempt - 1)))
                jitter = delay * 0.2 * (2 * random.random() - 1)  # ±20% jitter
                fallback_wait_time = max(1.0, delay + jitter)
                wait_time = max(retry_after or 0.0, fallback_wait_time)

                diagnostic_lines = _format_discord_rate_limit_details(
                    e,
                    attempt=attempt,
                    computed_wait_time=wait_time,
                    retry_after_seconds=retry_after,
                )
                for line in diagnostic_lines:
                    print(line)

                print(f"[WARN] Backing off for {wait_time:.1f}s before retry...")
                await asyncio.sleep(wait_time)
            else:
                # Some other HTTP error; re-raise immediately
                await _cleanup_bot_after_failed_login()
                print(f"[FATAL] Discord HTTP error during startup: {e}")
                raise
        except Exception as e:
            # Non-HTTP errors; don't retry
            await _cleanup_bot_after_failed_login()
            print(f"[FATAL] Unexpected startup error: {e}")
            raise


if not DISCORD_TOKEN:
    print("Error: DISCORD_TOKEN environment variable not set.")
    exit(1)

# Run the bot with rate-limit-aware retry logic
asyncio.run(run_bot_with_backoff(DISCORD_TOKEN))

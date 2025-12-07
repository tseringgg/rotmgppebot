

import discord


async def command(interaction: discord.Interaction):
    # --- Commands for everyone ---
    everyone_cmds = {
        "leaderboard": "Show the current PPE leaderboard.",
        "ppehelp": "Show this help message.",
        "listroles": "List all roles in this server.",
        "listadmins": "Show all admins (who can register you to contest).",
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
        "deleteppe": "Delete one ppe from a specific player.",
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
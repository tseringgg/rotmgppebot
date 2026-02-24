

import discord


async def command(interaction: discord.Interaction):
    # --- Commands for everyone ---
    general_cmds = {
        "leaderboard": "Show the current PPE leaderboard.",
        "characterleaderboard": "Show highest points for specific class.",
        "seasonleaderboard": "Show season leaderboard by unique items.",
        "teamleaderboard": "Show team leaderboard by combined points.",
        "ppehelp": "Show this help message.",
        "listroles": "List all roles in this server.",
        "listadmins": "Show all admins.",
    }
    
    # --- PPE Management (Player) ---
    ppe_mgmt_cmds = {
        "newppe": "Start a new PPE run (max 10).",
        "setactiveppe": "Set which PPE is active.",
        "myppes": "View all your PPEs.",
        "addpenalties": "Apply penalties to active PPE.",
    }
    
    # --- Loot & Bonuses (Player) ---
    loot_cmds = {
        "addloot": "Add item to active PPE.",
        "removeloot": "Remove item from active PPE.",
        "myloot": "Show active PPE's loot.",
        "shareloot": "Generate visual loot table.",
        "addbonus": "Add bonus to active PPE.",
        "removebonus": "Remove bonus from active PPE.",
    }
    
    # --- Season Tracking (Player) ---
    season_cmds = {
        "addseasonloot": "Add unique item to season collection.",
        "removeseasonloot": "Remove unique item from season.",
        "showseasonloot": "Show all season unique items.",
        "shareseasonloot": "Generate season loot table.",
    }
    
    # --- Team Commands (Player/Leader) ---
    team_cmds = {
        "teamleaderboard": "View team rankings.",
    }
    
    # --- Admin: Player Management ---
    admin_player_cmds = {
        "addplayer": "Add member to contest.",
        "removeplayer": "Remove member from contest.",
        "listplayers": "List all participants.",
        "listcharactersfor": "Show all characters for a player.",
        "deleteallppes": "Delete all PPEs for player.",
        "deleteppe": "Delete specific PPE.",
    }
    
    # --- Admin: Loot & Data Management ---
    admin_data_cmds = {
        "addlootfor": "Add loot to player's PPE.",
        "removelootfrom": "Remove loot from player's PPE.",
        "addbonusfor": "Add bonus to player's PPE.",
        "removebonusfrom": "Remove bonus from player's PPE.",
        "addpenaltiesfor": "Add penalties to player's PPE.",
        "addseasonlootfor": "Add to player's season loot.",
        "removeseasonlootfor": "Remove from player's season.",
        "inspectloot": "View player's PPE loot.",
        "addpointsfor": "Manually add points.",
        "refreshpointsfor": "Recalculate PPE points.",
        "refreshallpoints": "Recalculate all PPE points.",
    }
    
    # --- Admin: Team Management ---
    admin_team_cmds = {
        "addteam": "Create new team.",
        "deleteteam": "Delete team.",
        "leaveteam": "Remove player from team.",
    }
    
    # --- Team Leader Commands ---
    leader_cmds = {
        "addplayer_team": "Add player to team (Leader/Admin).",
        "updateteam": "Rename team (Leader/Admin).",
    }
    
    # --- Admin: Utility ---
    admin_util_cmds = {
        "migrateapostrophes": "Fix apostrophes in records.",
    }
    
    owner_cmds = {
        "resetseason": "Clear all season data & teams.",
        "giveppeadminrole": "Grant PPE Admin role.",
        "removeppeadminrole": "Remove PPE Admin role.",
        "setuproles": "Create required roles.",
    }

    # --- Create help embed ---
    embed = discord.Embed(
        title="🧙 PPE Bot Help",
        description="Welcome to the PPE competition bot!",
        color=discord.Color.blurple()
    )

    # Format and add fields (keeping under 1024 char limit per field)
    def format_cmds(cmds_dict):
        return "\n".join([f"`/{cmd}` — {desc}" for cmd, desc in cmds_dict.items()])
    
    embed.add_field(name="⚪ General Commands", value=format_cmds(general_cmds), inline=False)
    embed.add_field(name="🟢 PPE Management", value=format_cmds(ppe_mgmt_cmds), inline=False)
    embed.add_field(name="📦 Loot & Bonuses", value=format_cmds(loot_cmds), inline=False)
    embed.add_field(name="🌟 Season Tracking", value=format_cmds(season_cmds), inline=False)
    embed.add_field(name="👥 Team Commands", value=format_cmds(team_cmds), inline=False)
    embed.add_field(name="👔 Team Leader", value=format_cmds(leader_cmds), inline=False)
    embed.add_field(name="🔴 Admin: Players", value=format_cmds(admin_player_cmds), inline=False)
    embed.add_field(name="🔴 Admin: Loot & Data", value=format_cmds(admin_data_cmds), inline=False)
    embed.add_field(name="🔴 Admin: Teams", value=format_cmds(admin_team_cmds), inline=False)
    embed.add_field(name="🔴 Admin: Utility", value=format_cmds(admin_util_cmds), inline=False)
    embed.add_field(name="🔒 Owner Only", value=format_cmds(owner_cmds), inline=False)

    embed.set_footer(text="PPE Bot by LogicVoid — use /ppehelp anytime")
    await interaction.response.send_message(embed=embed, ephemeral=True)
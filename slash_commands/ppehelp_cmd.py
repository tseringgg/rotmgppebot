

import discord
from utils.pagination import LootPaginationView


async def command(interaction: discord.Interaction):
    # --- Commands for everyone ---
    general_cmds = {
        "leaderboard": "Show the current PPE leaderboard.",
        "characterleaderboard": "Show highest points for specific class.",
        "seasonleaderboard": "Show season leaderboard by unique items.",
        "questleaderboard": "Show leaderboard by weighted quest points.",
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
        "myquests": "Show your current and completed quests.",
        "resetquests": "Reset parts of your own quests (limited attempts).",
    }
    
    # --- Team Commands (Player/Leader) ---
    team_cmds = {
        "teamleaderboard": "View team rankings.",
        "myteam": "View your team members and rankings (optional: specify team name).",
    }
    
    # --- Admin: Player Management ---
    admin_player_cmds = {
        "addplayer": "Add member to contest.",
        "removeplayer": "Remove member (or Discord user ID) from contest and team data.",
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
        "viewquestsfor": "View quest state for a player.",
        "resetquestfor": "Reset quest sections for a player.",
        "resetallquests": "Reset all quest data for all players (with confirmation).",
        "managequests": "View/update quest targets, reset attempts, and quest leaderboard point weights.",
    }
    
    # --- Admin: Team Management ---
    admin_team_cmds = {
        "addteam": "Create new team.",
        "deleteteam": "Delete team.",
        "leaveteam": "Remove player from team (works even if player was removed from contest).",
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

    def split_field_lines(lines: list[str], max_chars: int = 1000) -> list[str]:
        chunks = []
        current_lines = []
        current_len = 0

        for line in lines:
            additional = len(line) + (1 if current_lines else 0)
            if current_lines and current_len + additional > max_chars:
                chunks.append("\n".join(current_lines))
                current_lines = [line]
                current_len = len(line)
            else:
                current_lines.append(line)
                current_len += additional

        if current_lines:
            chunks.append("\n".join(current_lines))

        return chunks or ["No commands available."]

    categories = [
        ("⚪ General Commands", general_cmds),
        ("🟢 PPE Management", ppe_mgmt_cmds),
        ("📦 Loot & Bonuses", loot_cmds),
        ("🌟 Season Tracking", season_cmds),
        ("👥 Team Commands", team_cmds),
        ("👔 Team Leader", leader_cmds),
        ("🔴 Admin: Players", admin_player_cmds),
        ("🔴 Admin: Loot & Data", admin_data_cmds),
        ("🔴 Admin: Teams", admin_team_cmds),
        ("🔴 Admin: Utility", admin_util_cmds),
        ("🔒 Owner Only", owner_cmds),
    ]

    expanded_fields: list[tuple[str, str]] = []
    for category_name, cmds_dict in categories:
        lines = [f"`/{cmd}` — {desc}" for cmd, desc in cmds_dict.items()]
        chunks = split_field_lines(lines)
        for idx, chunk in enumerate(chunks):
            suffix = "" if idx == 0 else f" (cont. {idx + 1})"
            expanded_fields.append((f"{category_name}{suffix}", chunk))

    embeds: list[discord.Embed] = []
    max_fields_per_embed = 8
    max_embed_chars = 5500
    pages: list[list[tuple[str, str]]] = []
    current_page_fields: list[tuple[str, str]] = []
    current_page_chars = 0

    for field_name, field_value in expanded_fields:
        field_chars = len(field_name) + len(field_value)
        would_exceed_field_count = len(current_page_fields) >= max_fields_per_embed
        would_exceed_char_budget = current_page_fields and (current_page_chars + field_chars > max_embed_chars)

        if would_exceed_field_count or would_exceed_char_budget:
            pages.append(current_page_fields)
            current_page_fields = [(field_name, field_value)]
            current_page_chars = field_chars
        else:
            current_page_fields.append((field_name, field_value))
            current_page_chars += field_chars

    if current_page_fields:
        pages.append(current_page_fields)

    for page_fields in pages:
        embed = discord.Embed(
            title="🧙 PPE Bot Help",
            description="Welcome to the PPE competition bot!",
            color=discord.Color.blurple(),
        )
        for field_name, field_value in page_fields:
            embed.add_field(name=field_name, value=field_value, inline=False)
        embeds.append(embed)

    for page_num, embed in enumerate(embeds, start=1):
        if len(embeds) > 1:
            embed.set_footer(text=f"PPE Bot by LogicVoid — Page {page_num}/{len(embeds)}")
        else:
            embed.set_footer(text="PPE Bot by LogicVoid — use /ppehelp anytime")

    if len(embeds) == 1:
        await interaction.response.send_message(embed=embeds[0], ephemeral=True)
    else:
        view = LootPaginationView(embeds=embeds, user_id=interaction.user.id)
        await interaction.response.send_message(embed=embeds[0], view=view, ephemeral=True)


import discord
from utils.pagination import LootPaginationView


async def command(interaction: discord.Interaction):
    # --- Commands for everyone ---
    general_cmds = {
        "leaderboard": "Open leaderboard menu (PPE, Quest, Character-by-class, Season Loot, Team).",
        "ppehelp": "Show this help message.",
        "listroles": "List all roles in this server.",
        "listadmins": "Show all admins.",
    }
    
    # --- PPE Management (Player) ---
    ppe_mgmt_cmds = {
        "newppe": "Start a new PPE run (max set by server config).",
        "myinfo": "Open the My Info home menu (characters, season loot, quest menu, and utility actions).",
        "setactiveppe": "Set which PPE is active.",
        "addbonus": "Add a bonus to your active PPE.",
        "removebonus": "Remove a bonus from your active PPE.",
    }
    
    # --- Loot & Bonuses (Player) ---
    loot_cmds = {
        "addloot": "Add item to active PPE.",
        "removeloot": "Remove item from active PPE.",
        "myinfo": "Use My Info -> Manage Characters -> Show Loot for loot image/list and Modify PPE for bonus edits.",
    }
    
    # --- Season Tracking (Player) ---
    season_cmds = {
        "addseasonloot": "Add unique item to season collection.",
        "removeseasonloot": "Remove unique item from season.",
        "myinfo": "Use My Info -> Show Season Loot to generate season loot images and view your season list.",
        "myquests": "Open your quest menu (same shared menu opened from My Info -> Show Quests).",
    }
    
    # --- Team Commands (Player/Leader) ---
    team_cmds = {
        "myteam": "View your team members and rankings (optional: specify team name).",
    }
    
    # --- Admin: Player Management ---
    admin_player_cmds = {
        "addplayer": "Add member to contest.",
        "listplayers": "List all participants.",
        "manageplayer": "Comprehensive admin menu to manage any player's data: view/edit PPEs, manage penalties, delete PPEs, view quests, manage loot, remove from contest, team actions, and owner-only PPE Admin toggles.",
    }
    
    # --- Admin: Loot & Data Management ---
    admin_data_cmds = {
        "addlootfor": "Add loot to player's PPE.",
        "removelootfrom": "Remove loot from player's PPE.",
        "addbonusfor": "Add bonus to player's PPE.",
        "removebonusfrom": "Remove bonus from player's PPE.",
        "addseasonlootfor": "Add to player's season loot.",
        "removeseasonlootfrom": "Remove from player's season.",
        "addpointsfor": "Manually add points.",
        "refreshpointsfor": "Recalculate PPE points.",
        "refreshallpoints": "Recalculate all PPE points.",
        "manageplayer": "Use Manage Player -> Show Quests -> Reset Quests to reset quest sections for a player.",
        "managequests": "View/update quest targets, reset attempts, quest leaderboard point weights, and run Reset All Quests from the menu.",
        "pointsettings": "View guild points modifier settings.",
        "pointsettingsglobal": "Set global percent modifiers for loot/bonus/penalty/total.",
        "pointsettingsclass": "Set class-specific percent modifiers and minimum total.",
    }
    
    # --- Admin: Team Management ---
    admin_team_cmds = {
        "manageteams": "Open team admin menu (create, rename, set leader, add/remove members, delete, team leaderboard).",
        "manageplayer": "Use Manage Player -> Team actions to add/remove a player from teams.",
    }

    owner_cmds = {
        "resetseason": "Clear season data and teams; optionally unlink all RealmShark links/mappings.",
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
        ("🔴 Admin: Players", admin_player_cmds),
        ("🔴 Admin: Loot & Data", admin_data_cmds),
        ("🔴 Admin: Teams", admin_team_cmds),
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
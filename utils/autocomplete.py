import discord
from dataclass import ROTMGClass
from discord import app_commands
from .loot_data import get_loot_data
from .bonus_data import get_bonus_names
from .player_records import load_teams


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
    
    # Get the loot data from the shared module
    loot_items = get_loot_data()
    
    matches = [
        app_commands.Choice(name=pretty, value=pretty)
        for pretty in loot_items
        if current_lower in pretty.lower()
    ]

    return matches[:25]

async def bonus_autocomplete(interaction: discord.Interaction, current: str):
    current_lower = current.lower()
    
    # Get the bonus names from the bonus data
    bonus_names = get_bonus_names()
    
    matches = [
        app_commands.Choice(name=bonus, value=bonus)
        for bonus in bonus_names
        if current_lower in bonus.lower()
    ]

    return matches[:25]

async def user_bonus_autocomplete(interaction: discord.Interaction, current: str):
    """Autocomplete function for bonuses that the user currently has"""
    from utils.player_records import load_player_records, ensure_player_exists
    
    current_lower = current.lower()
    
    try:
        # Load player records
        records = await load_player_records(interaction)
        key = ensure_player_exists(records, interaction.user.id)
        player_data = records[key]
        
        # Check if player has an active PPE
        if player_data.active_ppe is None:
            return []
        
        # Find the active PPE
        active_ppe = None
        for ppe in player_data.ppes:
            if ppe.id == player_data.active_ppe:
                active_ppe = ppe
                break
        
        if not active_ppe or not active_ppe.bonuses:
            return []
        
        # Get bonus names from the user's active PPE
        user_bonus_names = [bonus.name for bonus in active_ppe.bonuses]
        
        matches = [
            app_commands.Choice(name=bonus_name, value=bonus_name)
            for bonus_name in user_bonus_names
            if current_lower in bonus_name.lower()
        ]

        return matches[:25]
    except Exception:
        # If any error occurs, return empty list
        return []

async def target_user_bonus_autocomplete(interaction: discord.Interaction, current: str):
    """Autocomplete function for bonuses - shows all available bonuses since we can't determine target user during autocomplete"""
    # Since we can't reliably get the target user during autocomplete,
    # we'll just show all available bonuses for now
    return await bonus_autocomplete(interaction, current)

async def target_user_ppe_id_autocomplete(interaction: discord.Interaction, current: str):
    """Autocomplete function for PPE IDs of a target user during inspection"""
    from .player_records import load_player_records, ensure_player_exists
    
    try:
        # Get the target user from the interaction options
        target_user = None
        if hasattr(interaction, 'namespace') and hasattr(interaction.namespace, 'user'):
            target_user = interaction.namespace.user
        
        if not target_user:
            return []
        
        # Load player records
        records = await load_player_records(interaction)
        key = ensure_player_exists(records, target_user.id)
        player_data = records[key]
        
        if not player_data.ppes:
            return []
        
        # Create choices for each PPE
        choices = []
        for ppe in player_data.ppes:
            # Create display text with PPE ID and class name
            display_name = f"#{ppe.id} - {ppe.name}"
            if current.lower() in display_name.lower() or current in str(ppe.id):
                choices.append(app_commands.Choice(name=display_name, value=ppe.id))
        
        return choices[:25]  # Discord limit
        
    except Exception:
        # If anything goes wrong, return empty list
        return []

def get_dungeons() -> list[str]:
    return DUNGEONS

async def team_name_autocomplete(interaction: discord.Interaction, current: str):
    """Autocomplete function for team names"""
    current_lower = current.lower()
    
    try:
        # Load team data
        teams = await load_teams(interaction)
        
        # Get team names that match the current input
        matches = [
            app_commands.Choice(name=team_name, value=team_name)
            for team_name in teams.keys()
            if current_lower in team_name.lower()
        ]
        
        return matches[:25]  # Discord limit
    except Exception:
        # If any error occurs, return empty list
        return []

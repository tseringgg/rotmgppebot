import discord
from dataclass import ROTMGClass
from utils.calc_points import load_loot_points
from discord import app_commands


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

def get_dungeons() -> list[str]:
    return DUNGEONS
def get_loot_items() -> list[str]:
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
    return LOOT
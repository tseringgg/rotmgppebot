"""
Shared loot data module to avoid circular imports.
This module provides a centralized way to store and access loot data
that needs to be shared between main.py and other modules.
"""

# Global variable to store the loot data
from utils.calc_points import load_loot_points


LOOT = []

def init_loot_data():
    """
    Set the global LOOT data.
    This should be called once during bot startup.
    
    Args:
        loot_list (list): List of loot items
    """
    EXCEPTIONS = {"of", "the", "in", "and", "for", "to", "a", "an"}
        
    # Create temporary list for loot items
    loot_items = []

    loot_points = load_loot_points()  # load once at startup

    for internal_name in loot_points.keys():

        # exclude shiny variants
        if "(shiny)" in internal_name:
            continue

        # normalize capitalization
        words = internal_name.split(" ")
        pretty = " ".join(
            word.lower() if word.lower() in EXCEPTIONS and i != 0
            else word
            for i, word in enumerate(words)
        )

        loot_items.append(pretty)

    global LOOT
    LOOT.clear()
    LOOT.extend(loot_items)
    print(f"Loaded {len(loot_items)} loot items for autocomplete")


def get_loot_data():
    """
    Get the current LOOT data.
    
    Returns:
        list: The current loot data
    """
    return LOOT

def is_loot_loaded():
    """
    Check if loot data has been loaded.
    
    Returns:
        bool: True if loot data is available, False otherwise
    """
    return len(LOOT) > 0
"""
Shared loot data module to avoid circular imports.
This module provides a centralized way to store and access loot data
that needs to be shared between main.py and other modules.
"""

# Global variable to store the loot data
LOOT = []

def set_loot_data(loot_list):
    """
    Set the global LOOT data.
    This should be called once during bot startup.
    
    Args:
        loot_list (list): List of loot items
    """
    global LOOT
    LOOT.clear()
    LOOT.extend(loot_list)

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